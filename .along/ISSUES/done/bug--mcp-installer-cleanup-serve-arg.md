---
protocol: along
protocol_version: "4.4.10"
slug: mcp-installer-cleanup-serve-arg
type: bug
status: done
completed: 2026-10-12
priority: high
created: 2026-10-11
updated: 2026-10-12
agent: antigravity
tags: [installers, mcp, decoupling, code-review-graph]
blocked_by: []
related: [feat--decouple-code-review-graph-from-mcp-to-direct-cli]
---

# Purge default MCP auto-registration from installers

## 1. Context and Problem Statement

Following ADR `ADR-2026-09-27--decouple-code-review-graph-from-mcp-to-direct-cli`, `code-review-graph` was decoupled from the MCP server layer and transitioned to direct CLI invocation (`along graph-impact`, `along graph-arch`, `along graph-sync`).

However, the installers (`install.ps1` and `install.sh`) continued invoking `configure_mcp.py` without `--clean`, attempting to register the MCP server in `~/.claude.json` by default. Because `code-review-graph` requires the `serve` subcommand to run as an MCP server, the default entry produced a failing server in Claude Code. Furthermore, running `code-review-graph` as MCP contradicts the decoupling decision (causes interactive dialogs, schema reading tax, Windows stdio pipe freezes).

## 2. Requirements

- REQ-1: `install.ps1` must invoke `configure_mcp.py` with `--clean` by default so that stale MCP entries are removed and no new MCP server is registered.
- REQ-2: `install.sh` must invoke `configure_mcp.py` with `--clean` by default to preserve cross-platform installer parity.
- REQ-3: Optional explicit registration flag (`-RegisterMcp` in PowerShell, `--register-mcp` in Bash) allows opt-in registration if explicitly requested.
- REQ-4: All regression tests must pass.

## 3. Acceptance Criteria

- [x] `install.ps1` runs `configure_mcp.py --clean` by default.
- [x] `install.sh` runs `configure_mcp.py --clean` by default.
- [x] Installer artifact parity tests in `tests/test_skills_and_scripts.py` pass.
- [x] Full automated test suite passes.
