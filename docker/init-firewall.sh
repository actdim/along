#!/usr/bin/env bash
# docker/init-firewall.sh - Egress allowlist firewall for autonomous Along environment
set -euo pipefail

# Mandatory allowlisted destinations
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

# Merge default allowlist with any additions from ALONG_EXTRA_EGRESS
EXTRA_HOSTS="${ALONG_EXTRA_EGRESS:-}"
ALLOWLIST=("${DEFAULT_ALLOWLIST[@]}")
if [ -n "$EXTRA_HOSTS" ]; then
    IFS=',' read -ra ADDS <<< "$EXTRA_HOSTS"
    for host in "${ADDS[@]}"; do
        trimmed="$(echo "$host" | xargs)"
        if [ -n "$trimmed" ]; then
            ALLOWLIST+=("$trimmed")
        fi
    done
fi

echo "-> Initializing egress allowlist firewall..."

# Check iptables capability
if ! command -v iptables >/dev/null 2>&1; then
    echo "[Warning] iptables command not found; firewall initialization skipped."
    exit 0
fi

if ! iptables -L -n >/dev/null 2>&1; then
    echo "[Warning] Insufficient privileges or missing NET_ADMIN capability; firewall initialization skipped."
    exit 0
fi

# Flush existing rules and delete custom chains
iptables -F
iptables -X
iptables -t nat -F || true
iptables -t nat -X || true

# Set default policies: DROP everything except what is explicitly accepted
iptables -P INPUT DROP
iptables -P FORWARD DROP
iptables -P OUTPUT DROP

# 1. Allow loopback traffic
iptables -A INPUT -i lo -j ACCEPT
iptables -A OUTPUT -o lo -j ACCEPT

# 2. Allow established and related connections
iptables -A INPUT -m state --state ESTABLISHED,RELATED -j ACCEPT
iptables -A OUTPUT -m state --state ESTABLISHED,RELATED -j ACCEPT

# 3. Allow DNS queries (UDP and TCP port 53)
iptables -A OUTPUT -p udp --dport 53 -j ACCEPT
iptables -A OUTPUT -p tcp --dport 53 -j ACCEPT

# 4. Resolve allowlisted hosts and allow outbound HTTP/HTTPS/SSH traffic
for host in "${ALLOWLIST[@]}"; do
    ips=$(getent ahosts "$host" 2>/dev/null | awk '{print $1}' | sort -u || true)
    if [ -z "$ips" ]; then
        if command -v dig >/dev/null 2>&1; then
            ips=$(dig +short A "$host" 2>/dev/null || true)
        fi
    fi

    if [ -n "$ips" ]; then
        for ip in $ips; do
            if [[ "$ip" =~ ^[0-9]+\.[0-9]+\.[0-9]+\.[0-9]+$ ]]; then
                # HTTPS (port 443)
                iptables -A OUTPUT -p tcp -d "$ip" --dport 443 -j ACCEPT
                # HTTP (port 80)
                iptables -A OUTPUT -p tcp -d "$ip" --dport 80 -j ACCEPT
                # SSH (port 22) for GitHub
                if [ "$host" = "github.com" ]; then
                    iptables -A OUTPUT -p tcp -d "$ip" --dport 22 -j ACCEPT
                fi
            fi
        done
        echo "   [ALLOW] $host"
    else
        echo "   [WARN] Could not resolve host: $host"
    fi
done

echo "-> Egress firewall successfully configured. All unauthorized outbound traffic dropped."
