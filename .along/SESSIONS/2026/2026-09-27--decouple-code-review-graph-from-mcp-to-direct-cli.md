---
protocol: along
slug: decouple-code-review-graph-from-mcp-to-direct-cli
date: 2026-09-27
agent: antigravity
summary: "Decoupled code-review-graph from MCP to direct CLI execution, purged IDE config, updated protocol and overhauled documentation"
milestone: v4.1.0-code-intelligence-and-mcp-ecosystem
issues_advanced: []
issues_completed: [feat--decouple-code-review-graph-from-mcp-to-direct-cli]
decisions: [decouple-code-review-graph-from-mcp-to-direct-cli]
risks_logged: []
spikes_conducted: []
branch: main
commit: unknown
---

# Session Log: 2026-09-27 - Decouple code-review-graph from MCP to Direct CLI Execution

## 1. Initial Implementation Plan (Baseline)

The objective of issue `feat--decouple-code-review-graph-from-mcp-to-direct-cli` was to eliminate the operational friction of using `code-review-graph` as an external MCP server:
- Eliminate interactive security approval dialogs in Antigravity IDE and other runtimes that halted autonomous agent loops even in YOLO mode.
- Remove the lazy-loading overhead where models faced a 2-step schema read ceremony for 30 lazy MCP tools.
- Retain the underlying Python/Tree-sitter AST engine via `uvx`, standardizing execution through the already-trusted native `run_command` tool running `along graph-impact`, `along graph-arch`, `along graph-sync`, and `along graph-check`.
- Overhaul repository documentation, skills, and protocols to position `code-review-graph` as a CLI-driven AST intelligence engine with built-in graceful fallback to static search.

The Living Plan defined 4 execution steps:
1. Unregister & Decouple MCP Configuration (`mcp_config.json`, `install.py`, `configure_mcp.py`).
2. Protocol Root & Skills Modernization (`AGENTS.md`, `skills/along-init/protocol.md`, `skills/along-graph-*`, `skills/along-team`).
3. Knowledge Base & Documentation Overhaul (`topic--architecture.md`, `topic--cli-reference.md`, `topic--llm-wiki-architecture.md`, `topic--setup-and-workflow.md`, `topic--skills-reference.md`, `README.md`).
4. Verification, Sync & Regression Gates (`along kb sync`, `along sanitize`, `test.py`).

## 2. Execution & Loop Trace (Fixes & Re-plans)

- **Step 1: Unregister & Decouple MCP Configuration**:
  - Purged `code-review-graph` entry from `C:\Users\Admin\.gemini\antigravity\mcp_config.json`, leaving `{ "mcpServers": {} }`.
  - Added `unregister_mcp` and `clean: bool = False` support to `scripts/alongkit/install.py`.
  - Updated `scripts/configure_mcp.py` with `--clean` and `--unregister` options, safely removing `code-review-graph` from `~/.claude.json`.
  - Preserved package constants (`MCP_SERVER_NAME`, `MCP_SERVER_ENTRY`, etc.) for test suite stability.
  - Added `test_unregister_mcp_removes_configuration` to `tests/test_installers.py` verifying clean unregistration and idempotency.
- **Step 2: Protocol Root & Skills Modernization**:
  - Replaced review checklist item in `AGENTS.md` and `skills/along-init/protocol.md` from "evaluate blast radius via code-review-graph MCP" to "evaluate blast radius via along graph-impact (or static search fallback)".
  - Updated `skills/along-graph-impact/SKILL.md` to remove references to `get_affected_flows_tool` and `query_graph_tool`, establishing direct CLI invocation.
  - Updated `skills/along-graph-arch/SKILL.md` to remove MCP tool references (`get_hub_nodes_tool`, `get_bridge_nodes_tool`) in favor of AST analysis descriptions.
  - Updated `skills/along-graph-check/SKILL.md` and `skills/along-team/SKILL.md` to describe `code-review-graph` as an AST engine and report `code-review-graph offline` rather than `MCP offline`.
- **Step 3: Knowledge Base & Documentation Overhaul**:
  - Updated `docs/topic--architecture.md`: replaced `code-review-graph MCP` with `along graph-* CLI (code-review-graph AST Engine)` in topology diagrams and execution tables.
  - Updated `docs/topic--llm-wiki-architecture.md`: replaced `get_impact_radius_tool` with `along graph-impact` in the blast radius flow diagram and review checklist.
  - Updated `docs/topic--cli-reference.md`: added complete reference documentation for `along graph-impact` and `along graph-arch` detailing flags, traversal depth, and JSON output.
  - Updated `docs/topic--setup-and-workflow.md`: replaced MCP registration honesty with Code Intelligence & MCP Decoupling runbook.
  - Updated `docs/topic--skills-reference.md` and `README.md` to reflect AST engine capabilities without MCP requirements.
- **Step 4: Verification, Sync & Regression Gates**:
  - Synchronized Knowledge Base via `along kb sync --strict --strict-sections`: 14 topic articles indexed, 367 relative links verified, 0 broken links.
  - Scanned repository typography via `along sanitize`: 586 files scanned, 0 forbidden characters.
  - Executed full test suite via `python .along/scripts/test.py`: 639 tests passed in 63.8s (0 failures, 2 skipped).
  - Executed `along graph-impact` on touched files confirming healthy AST analysis and candidate test resolution.

## 3. Verification Walkthrough & Gate Manifest

```text
Gate Execution Manifest:
- Workspace Isolation: EXECUTED (PASS) [mode: inherit]
- File Integrity: EXECUTED (PASS) [all new and modified files non-zero bytes]
- Automated Tests: EXECUTED (PASS) [639 tests in 63.8s, 0 failures, 2 skipped]
- Diff Scope Audit: EXECUTED (PASS) [clean boundaries, no out-of-scope edits]
- Requirement Traceability: EXECUTED (PASS) [REQ-1, REQ-2, REQ-3, REQ-4, REQ-5]
- Blast Radius: EXECUTED (PASS) [along graph-impact: HEALTHY, AST analysis operational]
- Documentation Parity: EXECUTED (PASS) [KB synced, 367 links verified]
- Clean Typography: EXECUTED (PASS) [586 files scanned, 0 banned characters]
```
