#!/usr/bin/env bash
# docker/entrypoint.sh - Autonomous Along container entrypoint
set -euo pipefail

# 1. Initialize firewall if privileges exist
if [ -x /usr/local/bin/init-firewall.sh ]; then
    if [ "$(id -u)" -eq 0 ]; then
        /usr/local/bin/init-firewall.sh || true
    elif sudo -n /usr/local/bin/init-firewall.sh >/dev/null 2>&1; then
        sudo -n /usr/local/bin/init-firewall.sh || true
    fi
fi

# 2. Clone or initialize repository if workspace is empty
WORKSPACE_DIR="/workspace"
if [ -d "$WORKSPACE_DIR" ] && [ -n "${ALONG_REPO_URL:-}" ]; then
    if [ ! -d "$WORKSPACE_DIR/.git" ]; then
        echo "-> Workspace repository not found; cloning from $ALONG_REPO_URL..."
        CLONE_URL="$ALONG_REPO_URL"
        if [ -n "${GITHUB_TOKEN:-}" ] && [[ "$CLONE_URL" == https://github.com/* ]]; then
            CLONE_URL="https://x-access-token:${GITHUB_TOKEN}@${CLONE_URL#https://}"
        fi
        git clone --branch "${ALONG_REPO_BRANCH:-main}" "$CLONE_URL" "$WORKSPACE_DIR" || {
            echo "[Warning] Failed to clone $ALONG_REPO_URL on branch ${ALONG_REPO_BRANCH:-main}"
        }
    fi
fi

# 3. Execute requested command or default to bash
if [ "$#" -eq 0 ]; then
    exec /bin/bash
else
    exec "$@"
fi
