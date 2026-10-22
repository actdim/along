# Production-grade isolated autonomous container image for Along Protocol
# Base: Ubuntu 24.04 LTS (Noble Numbat)
FROM ubuntu:24.04

ENV DEBIAN_FRONTEND=noninteractive \
    LANG=C.UTF-8 \
    LC_ALL=C.UTF-8 \
    PYTHONUNBUFFERED=1 \
    NODE_VERSION=20.x \
    HOME=/home/along

# Install base dependencies, Python 3.12, networking/firewall utilities, and git
RUN apt-get update && apt-get install -y --no-install-recommends \
    bash \
    ca-certificates \
    curl \
    git \
    gnupg \
    iptables \
    iproute2 \
    dnsutils \
    jq \
    sudo \
    build-essential \
    python3 \
    python3-pip \
    python3-venv \
    python3-dev \
    && rm -rf /var/lib/apt/lists/*

# Install Node.js 20 LTS via official NodeSource repository
RUN mkdir -p /etc/apt/keyrings \
    && curl -fsSL https://deb.nodesource.com/gpgkey/nodesource-repo.gpg.key | gpg --dearmor -o /etc/apt/keyrings/nodesource.gpg \
    && echo "deb [signed-by=/etc/apt/keyrings/nodesource.gpg] https://deb.nodesource.com/node_20.x nodistro main" | tee /etc/apt/sources.list.d/nodesource.list \
    && apt-get update && apt-get install -y --no-install-recommends nodejs \
    && rm -rf /var/lib/apt/lists/*

# Install CLI agent runtimes: Claude Code (@anthropic-ai/claude-code) and OpenCode (opencode)
RUN npm install -g @anthropic-ai/claude-code opencode-ai \
    && npm cache clean --force

# Install Along Protocol package
RUN pip3 install --no-cache-dir --break-system-packages actdim-along

# Create non-root along user with UID/GID 1000
RUN groupadd -g 1000 along \
    && useradd -u 1000 -g along -m -s /bin/bash along \
    && echo "along ALL=(ALL) NOPASSWD: /usr/local/bin/init-firewall.sh" >> /etc/sudoers.d/along-firewall \
    && chmod 0440 /etc/sudoers.d/along-firewall

# Setup mount directories with proper permissions
RUN mkdir -p /workspace /home/along/.claude /home/along/.opencode /home/along/.cache /home/along/.along \
    && chown -R along:along /workspace /home/along

# Copy firewall initialization and entrypoint scripts
COPY docker/init-firewall.sh /usr/local/bin/init-firewall.sh
COPY docker/entrypoint.sh /usr/local/bin/entrypoint.sh
RUN chmod +x /usr/local/bin/init-firewall.sh /usr/local/bin/entrypoint.sh

# Declare volume mount points
VOLUME ["/workspace", "/home/along/.claude", "/home/along/.opencode", "/home/along/.cache"]

WORKDIR /workspace
USER along

ENTRYPOINT ["/usr/local/bin/entrypoint.sh"]
CMD ["bash"]
