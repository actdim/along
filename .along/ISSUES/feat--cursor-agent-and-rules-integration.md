---
protocol: along
protocol_version: "2.2.26"
slug: cursor-agent-and-rules-integration
type: feat
status: open
priority: medium
created: 2026-09-07
updated: 2026-09-07
agent: antigravity
tags: [cursor, ide, rules, mcp, provider]
blocked_by: []
related: []
---

# Cursor Agent Integration via .cursorrules, .cursor/rules and MCP

## Context & Architectural Feasibility
Cursor is currently the most widely adopted AI-native code editor. Unlike passive completion plugins (such as traditional GitHub Copilot), Cursor features an autonomous **Composer Agent** capable of:
1. Executing terminal commands directly within the workspace.
2. Editing multiple files, navigating AST symbols, and inspecting Git diffs.
3. Consuming Model Context Protocol (MCP) servers configured via `mcp.json`.
4. Reading repository instructions via modern `.cursor/rules/*.mdc` files (Cursor 0.40+) and legacy root `.cursorrules`.

Because Cursor Agent can execute CLI commands, it can directly trigger Along lifecycle runners (`along test`, `along commit`, `along wrap`, `along build`) and query `along kb-search`, making it a genuine candidate for first-class Along integration.

## Proposed Integration Details

### 1. Thin Pointer Rule Scaffolding (`.cursor/rules/along.mdc`)
To maintain the Single Source of Truth (SSOT) and prevent documentation drift across providers:
- `along-init` should scaffold `.cursor/rules/along.mdc` with `alwaysApply: true` and glob `*`.
- The rule file acts as a lightweight pointer instructing Cursor Agent to:
  - Adhere to active conventions in `AGENTS.md`.
  - Consult the living Knowledge Base in `docs/INDEX.md`.
  - Use the canonical `along` CLI for lifecycle operations (testing, committing, wrapping).

### 2. MCP Server Registration in Cursor
- Cursor natively supports MCP servers defined in `~/.cursor/mcp.json` or `.cursor/mcp.json`.
- Provide automated configuration in `scripts/configure_mcp.py` to register `code-review-graph` and `along-kb-search` for Cursor.
- Add `-Target cursor` option to `install.ps1` and `install.sh`.

### 3. Documentation & Provider Matrix
- Update `README.md`, `AGENTS.md`, and `docs/topic--architecture.md` to list Cursor alongside Claude Code, Google Antigravity, OpenAI Codex, and OpenCode.
- Clarify workflow differences between CLI agents (Claude Code, OpenCode) and IDE-native agents (Cursor, Antigravity).

## Acceptance Criteria
- [ ] `along-init` scaffolds `.cursor/rules/along.mdc` pointing to `AGENTS.md` and `docs/INDEX.md`.
- [ ] Scaffolding is non-destructive and preserves existing user-defined Cursor rules.
- [ ] `configure_mcp.py` and installers support Cursor MCP configuration.
- [ ] Automated tests verify `.cursor/rules/along.mdc` creation and link integrity.
- [ ] Provider support matrix updated across public documentation.
