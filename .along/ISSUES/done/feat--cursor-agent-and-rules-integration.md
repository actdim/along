---
protocol: along
protocol_version: "2.2.26"
slug: cursor-agent-and-rules-integration
type: feat
status: done
completed: 2026-11-25
priority: medium
created: 2026-09-07
updated: 2026-11-25
plan_status: approved
agent: antigravity
tags: [cursor, ide, rules, mcp, provider]
milestone: v3.1.0-native-ast-and-cursor-parity
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
- [x] `along-init` scaffolds `.cursor/rules/along.mdc` pointing to `AGENTS.md` and `docs/INDEX.md`.
- [x] Scaffolding is non-destructive and preserves existing user-defined Cursor rules.
- [x] `configure_mcp.py` and installers support Cursor MCP configuration (`~/.cursor/mcp.json` for existing servers `code-review-graph` and `along-webdev`; `along-kb-search` remains CLI-only per approved plan).
- [x] Automated tests verify `.cursor/rules/along.mdc` creation, link integrity, installer parity, MCP registration, and runtime/hook alignment.
- [x] Provider support matrix updated across public documentation.

## Implementation Summary
- **Rule scaffolding**: `scripts/alongkit/scaffold.py` (`CURSOR_RULE_RELPATH`, `cursor_rule_template`) and `scripts/along_init.py` (`scaffold_cursor_rule`) create `.cursor/rules/along.mdc` via `write_if_missing` at non-nested architecture roots, preserving customized/unrelated `.cursor/` files and respecting `--dry-run`.
- **Installers & MCP**: Added `cursor` to `alongkit.install` (`PROVIDERS`, `FOLDER_PROVIDERS`, `Homes`, verified `mcp_target` at `~/.cursor/mcp.json`), `scripts/install_manifest.py`, `scripts/configure_mcp.py`, `scripts/along_update.py`, `install.ps1`, `install.sh`, and `install.bat`, deploying `along-*` skills to `~/.cursor/skills/` while keeping global Cursor hooks opt-in (`along hook attribution --runtime cursor` remains default).
- **Hooks & runtime reporting**: Added `beforeSubmitPrompt` (`UserPromptSubmit`) to `get_cursor_hook_manifest()` and `GenericCliAdapter`, added `along_hooks_registered("cursor", ...)` and updated `RUNTIME_MATRIX["cursor"]` / `enforcement_level` in `scripts/alongkit/runtime.py`, added `CURSOR_AGENT`/`CURSOR_TRACE_ID`/`CURSOR_CLI` detection in `scripts/alongkit/entities/vocabulary.py`, and preserved `RUNTIME_HOOK_NARROWINGS["cursor"]` in `along doctor`.
- **Documentation**: Updated `README.md`, `docs/topic--setup-and-workflow.md`, `docs/topic--runtime-hooks-and-gates.md`, `docs/topic--architecture.md`, `docs/topic--cli-reference.md`, `docs/topic--skills-reference.md`, `skills/along-init/SKILL.md`, and `skills/along-update/SKILL.md` (leaving `write_policy: manual` `docs/topic--system-comparisons.md` untouched).
