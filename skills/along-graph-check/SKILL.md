---
name: along-graph-check
description: Debug and inspect code-review-graph status, blast radius, and enforce .code-review-graph-ignore filters to prevent node_modules ballooning. Use when invoking /along-graph-check.
---

# Along Graph Check
Inspects and verifies `code-review-graph` MCP server health, graph database status, and exclusion filters.

## Usage
- Direct command: `/along-graph-check`
- CLI command: `python scripts/along_exec.py graph-check` (or `along graph-check`)
- Doctor preflight: `along doctor` (includes MCP health check)
- JSON report: `python scripts/along_exec.py graph-check --json`

## Health Check Verification
The check executes a preflight probe against the pinned MCP dependency (`code-review-graph==2.3.8`):
1. **Runner Probe**: Verifies that `uvx` / `uv` is available in system `PATH`.
2. **Package Probe**: Runs a non-destructive command probe (`--help`) with a 7-second timeout to verify package integrity without hanging.
3. **Filter Audit**: Ensures `.code-review-graph-ignore` exists in the repository root and excludes `node_modules`, `dist`, and `build` to prevent graph database ballooning.

## Diagnostic Statuses
- **`HEALTHY`**: MCP server starts cleanly and exclusion filters are in place.
- **`DEGRADED`**: MCP server starts, but `.code-review-graph-ignore` is missing or incomplete.
- **`OFFLINE`**: `uvx` is missing or the server failed to respond. The tool outputs actionable remediation instructions (install uv, check network, verify python environment).

## Fallback Blast-Radius Procedure (When Offline)
If `code-review-graph` is offline during a code review gate, agents MUST NOT skip the gate silently. They must:
1. Loudly report `[CRITICAL WARNING] code-review-graph MCP offline!`.
2. Fall back to static search (`grep_search` across symbol callers, imports, and interface usages).
3. Record `Blast Radius: DEGRADED (static search, code-review-graph OFFLINE)` in the session log.
