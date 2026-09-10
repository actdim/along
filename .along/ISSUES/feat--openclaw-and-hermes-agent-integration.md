---
protocol: along
slug: openclaw-and-hermes-agent-integration
type: feat
status: open
priority: medium
created: 2026-08-27
updated: 2026-09-10
agent: antigravity
tags: [providers, openclaw, hermes-agent, agent-integration, cli, backlog]
milestone: ~
blocked_by: []
related: []
---

# Support & Integration for OpenClaw / OpenClaude and Hermes Agent Providers

## Goal
Expand the provider-agnostic compatibility of `Along` to support emerging open-source AI agent frameworks: **OpenClaw / OpenClaude** and **Hermes Agent** (Nous Research), ensuring native protocol ingestion (`AGENTS.md` / `CLAUDE.md`), automated skill deployment, and MCP server configuration across both ecosystems.

## Problem Statement
While `Along` natively supports Claude Code, Codex, OpenCode, and Antigravity, developers increasingly utilize self-hosted and open-weights agent frameworks such as OpenClaw/OpenClaude and Hermes Agent. Without explicit installer support and discovery rules, these agents do not automatically register `along-*` skills or configuration files.

## Proposed Integration Details

### 1. Provider Ecosystem Analysis & Config Discovery
- **OpenClaw / OpenClaude**:
  - Identify config directory and instruction loading conventions (e.g. `~/.openclaw/`, `~/.openclaude/`, or repository-level instruction files).
  - Enable seamless skill / slash-command mounting.
- **Hermes Agent (Nous Research)**:
  - Inspect agent configuration directory (e.g. `~/.hermes/`, `~/.config/hermes-agent/`).
  - Configure tool definitions, function schemas, and MCP servers compatible with Hermes function-calling format.

### 2. Installer & Skill Deployment Extension
- Extend `install.ps1` and `install.sh` to add `-Target openclaw` and `-Target hermes` (and include in `-Target all`).
- Provide automated symlinking / copying of `along-*` skill manifests into the appropriate directories.
- Configure `code-review-graph` MCP server in respective provider JSON configuration files.

### 3. Protocol Ingestion & Native Rules
- Document instruction loading precedence in `AGENTS.md` and `README.md` for both new providers.
- Ensure `migrate_protocol.py` and `along_update.py` properly detect and update OpenClaw and Hermes environments.

## Acceptance Criteria
- [ ] Config path discovery and instruction loading verified for OpenClaw/OpenClaude and Hermes Agent.
- [ ] `install.ps1` and `install.sh` updated to support deployment to OpenClaw and Hermes Agent.
- [ ] Provider support matrix updated in `README.md` and `AGENTS.md`.
- [ ] Automated protocol verification and MCP configuration tested on both frameworks.

