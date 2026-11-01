#!/usr/bin/env bash
# docker/entrypoint.sh - Autonomous Along container entrypoint
set -euo pipefail

FIREWALL_SCRIPT=/usr/local/bin/init-firewall.sh

if [ "${ALONG_FIREWALL:-}" = "off" ]; then
    echo "[Warning] firewall disabled by ALONG_FIREWALL=off" >&2
elif [ "$(id -u)" -ne 0 ]; then
    echo "[Error] firewall: entrypoint must run as root" >&2
    exit 1
else
    RUN_DIR="${ALONG_RUN_DIR:-/run/along}"
    if ! mkdir -p "$RUN_DIR" 2>/dev/null; then
        RUN_DIR="${TMPDIR:-/tmp}/along-run"
        mkdir -p "$RUN_DIR"
    fi
    EGRESS_LIST="$RUN_DIR/egress.list"
    > "$EGRESS_LIST"
    chmod 0644 "$EGRESS_LIST"
    if [ -n "${ALONG_EXTRA_EGRESS:-}" ]; then
        IFS=',' read -ra ADDS <<< "$ALONG_EXTRA_EGRESS"
        for host in "${ADDS[@]}"; do
            trimmed="$(echo "$host" | xargs)"
            if [ -n "$trimmed" ]; then
                echo "$trimmed" >> "$EGRESS_LIST"
            fi
        done
    fi

    if ! "$FIREWALL_SCRIPT" --allow-file "$EGRESS_LIST"; then
        echo "[Error] firewall could not be applied; refusing to start (set ALONG_FIREWALL=off to override)" >&2
        exit 1
    fi

    ( while sleep "${ALONG_FIREWALL_REFRESH:-300}"; do
        "$FIREWALL_SCRIPT" --refresh --allow-file "$EGRESS_LIST" || echo "[Warning] firewall refresh failed" >&2
      done ) &
fi

WORKSPACE_DIR="/workspace"
if [ -d "$WORKSPACE_DIR" ] && [ -n "${ALONG_REPO_URL:-}" ]; then
    if [ ! -d "$WORKSPACE_DIR/.git" ]; then
        echo "-> Workspace repository not found; cloning from $ALONG_REPO_URL..."
        if [ "$(id -u)" -eq 0 ]; then
            setpriv --reuid=1000 --regid=1000 --init-groups --no-new-privs \
                git clone --branch "${ALONG_REPO_BRANCH:-main}" "$ALONG_REPO_URL" "$WORKSPACE_DIR" || {
                echo "[Warning] Failed to clone $ALONG_REPO_URL on branch ${ALONG_REPO_BRANCH:-main}" >&2
            }
        else
            git clone --branch "${ALONG_REPO_BRANCH:-main}" "$ALONG_REPO_URL" "$WORKSPACE_DIR" || {
                echo "[Warning] Failed to clone $ALONG_REPO_URL on branch ${ALONG_REPO_BRANCH:-main}" >&2
            }
        fi
    fi
fi

if [ "$#" -eq 0 ]; then
    set -- /bin/bash
fi

if [ "$(id -u)" -eq 0 ]; then
    exec setpriv --reuid=1000 --regid=1000 --init-groups --no-new-privs -- "$@"
else
    exec "$@"
fi
