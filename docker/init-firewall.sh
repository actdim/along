#!/usr/bin/env bash
# docker/init-firewall.sh - Egress allowlist firewall for autonomous Along environment
set -euo pipefail

lockdown() {
    echo "[Error] Firewall failure; engaging lockdown (dropping all traffic)..." >&2
    iptables -F 2>/dev/null || true
    iptables -P INPUT DROP 2>/dev/null || true
    iptables -P FORWARD DROP 2>/dev/null || true
    iptables -P OUTPUT DROP 2>/dev/null || true
    if command -v ip6tables >/dev/null 2>&1; then
        ip6tables -F 2>/dev/null || true
        ip6tables -P INPUT DROP 2>/dev/null || true
        ip6tables -P FORWARD DROP 2>/dev/null || true
        ip6tables -P OUTPUT DROP 2>/dev/null || true
    fi
}

trap 'lockdown; exit 1' ERR

# Check mandatory capabilities and tools
if ! command -v iptables >/dev/null 2>&1 || ! command -v ip6tables >/dev/null 2>&1 || ! command -v ipset >/dev/null 2>&1; then
    echo "[Error] firewall: missing required tools (iptables, ip6tables, ipset)" >&2
    exit 1
fi

if ! iptables -N ALONG_PROBE 2>/dev/null || ! iptables -X ALONG_PROBE 2>/dev/null; then
    echo "[Error] firewall: capability probe failed (insufficient privileges or missing NET_ADMIN)" >&2
    lockdown
    exit 1
fi

REFRESH_MODE=false
ALLOW_FILE=""

while [ "$#" -gt 0 ]; do
    case "$1" in
        --refresh)
            REFRESH_MODE=true
            shift
            ;;
        --allow-file)
            ALLOW_FILE="${2:-}"
            shift 2
            ;;
        *)
            echo "[Error] firewall: unrecognized argument '$1'" >&2
            exit 1
            ;;
    esac
done

# Mandatory allowlisted destinations (must match alongkit.environment.DEFAULT_EGRESS_ALLOWLIST)
DEFAULT_ALLOWLIST=(
    "api.anthropic.com"
    "api.openai.com"
    "generativelanguage.googleapis.com"
    "github.com"
    "pypi.org"
    "files.pythonhosted.org"
    "registry.npmjs.org"
    "api.telegram.org"
)

HOSTS=("${DEFAULT_ALLOWLIST[@]}")
if [ -n "$ALLOW_FILE" ] && [ -f "$ALLOW_FILE" ]; then
    while IFS= read -r line || [ -n "$line" ]; do
        trimmed="$(echo "$line" | xargs)"
        if [ -n "$trimmed" ]; then
            HOSTS+=("$trimmed")
        fi
    done < "$ALLOW_FILE"
fi

HOST_RE='^[A-Za-z0-9.-]+$'
CIDR_RE='^[0-9]+\.[0-9]+\.[0-9]+\.[0-9]+(/[0-9]+)?$'

for h in "${HOSTS[@]}"; do
    if [[ ! "$h" =~ $HOST_RE ]] && [[ ! "$h" =~ $CIDR_RE ]]; then
        echo "[Error] firewall: invalid allowlist host '$h'" >&2
        exit 1
    fi
done

ALLOW_IPS=()
GITHUB_IPS=()

for h in "${HOSTS[@]}"; do
    if [[ "$h" =~ $CIDR_RE ]]; then
        ALLOW_IPS+=("$h")
    else
        resolved=$(getent ahostsv4 "$h" 2>/dev/null | awk '{print $1}' | sort -u || true)
        if [ -z "$resolved" ]; then
            echo "[Warning] firewall: could not resolve host: $h" >&2
        else
            for ip in $resolved; do
                ALLOW_IPS+=("$ip")
                if [ "$h" = "github.com" ]; then
                    GITHUB_IPS+=("$ip")
                fi
            done
        fi
    fi
done

if [ "${#ALLOW_IPS[@]}" -eq 0 ]; then
    echo "[Error] firewall: zero resolved IPs for allowlist" >&2
    exit 1
fi

if [ "$REFRESH_MODE" = "true" ]; then
    ipset create along-allow-tmp hash:net -exist
    ipset create along-allow-ssh-tmp hash:net -exist
    ipset flush along-allow-tmp
    ipset flush along-allow-ssh-tmp
    for ip in "${ALLOW_IPS[@]}"; do
        ipset add along-allow-tmp "$ip" -exist
    done
    for ip in "${GITHUB_IPS[@]}"; do
        ipset add along-allow-ssh-tmp "$ip" -exist
    done
    ipset swap along-allow-tmp along-allow
    ipset swap along-allow-ssh-tmp along-allow-ssh
    ipset destroy along-allow-tmp
    ipset destroy along-allow-ssh-tmp
    echo "-> Egress firewall rules refreshed."
    exit 0
fi

# Initial ipset creation
ipset create along-allow hash:net -exist
ipset create along-allow-ssh hash:net -exist
ipset flush along-allow
ipset flush along-allow-ssh
for ip in "${ALLOW_IPS[@]}"; do
    ipset add along-allow "$ip" -exist
done
for ip in "${GITHUB_IPS[@]}"; do
    ipset add along-allow-ssh "$ip" -exist
done

# Note: Never touch the nat table so Docker's embedded DNS (127.0.0.11) DNAT rules
# in DOCKER_OUTPUT and DOCKER_POSTROUTING remain intact.
# If a nat flush is ever needed (e.g. Anthropic devcontainer pattern):
# save `iptables-save -t nat | grep 127.0.0.11`, flush, recreate the two chains, replay.

iptables -F INPUT
iptables -F OUTPUT
iptables -F FORWARD

iptables -P INPUT DROP
iptables -P FORWARD DROP
iptables -P OUTPUT DROP

# Loopback
iptables -A INPUT -i lo -j ACCEPT
iptables -A OUTPUT -o lo -j ACCEPT

# Established / Related connections
iptables -A INPUT -m state --state ESTABLISHED,RELATED -j ACCEPT
iptables -A OUTPUT -m state --state ESTABLISHED,RELATED -j ACCEPT

# DNS queries to configured nameservers only
RESOLV_CONF="${ALONG_RESOLV_CONF:-/etc/resolv.conf}"
NAMESERVERS=()
if [ -f "$RESOLV_CONF" ]; then
    while read -r _keyword ns rest; do
        if [ "$_keyword" = "nameserver" ] && [ -n "$ns" ]; then
            NAMESERVERS+=("$ns")
        fi
    done < "$RESOLV_CONF"
fi

for ns in "${NAMESERVERS[@]}"; do
    iptables -A OUTPUT -p udp -d "$ns" --dport 53 -j ACCEPT
    iptables -A OUTPUT -p tcp -d "$ns" --dport 53 -j ACCEPT
done

# Outbound HTTP/HTTPS to allowlisted hosts
iptables -A OUTPUT -p tcp -m set --match-set along-allow dst -m multiport --dports 80,443 -j ACCEPT

# Outbound SSH for GitHub
iptables -A OUTPUT -p tcp -m set --match-set along-allow-ssh dst --dport 22 -j ACCEPT

# Reject remaining outbound traffic
iptables -A OUTPUT -j REJECT --reject-with icmp-admin-prohibited

# IPv6 filtering
IPV6_DISABLED=false
if [ ! -f /proc/net/if_inet6 ]; then
    IPV6_DISABLED=true
elif [ -f /proc/sys/net/ipv6/conf/all/disable_ipv6 ] && [ "$(cat /proc/sys/net/ipv6/conf/all/disable_ipv6 2>/dev/null || echo 0)" = "1" ]; then
    IPV6_DISABLED=true
fi

if [ "$IPV6_DISABLED" = "false" ]; then
    ip6tables -F INPUT
    ip6tables -F OUTPUT
    ip6tables -F FORWARD
    ip6tables -P INPUT DROP
    ip6tables -P FORWARD DROP
    ip6tables -P OUTPUT DROP
    ip6tables -A INPUT -i lo -j ACCEPT
    ip6tables -A OUTPUT -o lo -j ACCEPT
    ip6tables -A INPUT -m state --state ESTABLISHED,RELATED -j ACCEPT
    ip6tables -A OUTPUT -m state --state ESTABLISHED,RELATED -j ACCEPT
    ip6tables -A OUTPUT -j REJECT --reject-with icmp6-adm-prohibited
else
    echo "-> IPv6 disabled in environment; treated as blocked."
fi

# Self-check
if command -v curl >/dev/null 2>&1; then
    if curl -s -f --max-time 5 https://example.com >/dev/null 2>&1; then
        echo "[Error] firewall self-check failed: blocked destination example.com is reachable" >&2
        exit 1
    fi
fi

echo "-> Egress firewall successfully configured. All unauthorized outbound traffic dropped."
