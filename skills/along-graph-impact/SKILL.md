---
name: along-graph-impact
description: Determine exact semantic blast radius, affected execution flows, candidate tests, and affected documentation before modifying code or closing tasks. Use when invoking /along-graph-impact.
---

# Along Graph Impact (`/along-graph-impact`)
Calculates the semantic blast radius of planned or executed code modifications using the `code-review-graph` AST database.

## Usage
- Direct slash command: `/along-graph-impact <symbol|file>`
- Auto-detect changed files: `/along-graph-impact`
- CLI command: `along graph-impact <symbol|file>`
- Subcommand group: `along graph impact <symbol|file>`
- Script fallback: `python ~/.along/bin/along_exec.py graph-impact <symbol|file>`
- Machine-readable JSON: `along graph-impact <symbol|file> --json`
- Specify diff base: `along graph-impact --base HEAD~2`
- Adjust traversal depth: `along graph-impact <symbol> --max-depth 3`

## Key Capabilities
1. **AST Call Hierarchy**: Identifies direct callers, callees, and importers of the target symbol or file.
2. **Execution Flow Tracing**: Detects critical user flows and subsystem execution paths intersecting the changes (`get_affected_flows_tool`).
3. **Candidate Test Discovery**: Pinpoints automated test suites and files covering the target (`query_graph_tool` pattern `tests_for`).
4. **Documentation Blast Radius**: Maps affected symbols to Knowledge Base articles in `docs/topic--*.md` to guarantee public contract synchronization.
5. **Resilient Degradation**: If `code-review-graph` MCP or `uvx` is offline, automatically executes static text/AST analysis (`grep_search`) across the codebase, flags the output as `[DEGRADED]`, and ensures review gates are never skipped silently.

## Lifecycle Integration
- **`along-team` (Phase 2 Architect)**: Run `/along-graph-impact` on target components before finalizing the Living Plan to surface hidden dependencies.
- **`along-team` (Phase 4 Reviewer Check 5)**: Run `/along-graph-impact` on all modified files to verify blast radius and test coverage.
- **`along-wrap` (Phase A Cognitive Review)**: Mandate blast radius audit before closing active issues.

## Fallback Procedure (When Offline)
When the MCP server or `uvx` is unavailable:
1. Loudly report `[DEGRADED] code-review-graph MCP offline - falling back to static search`.
2. Inspect symbol occurrences and callers across tracked files.
3. Record `Blast Radius: DEGRADED (static search, code-review-graph OFFLINE)` in reviewer manifests and session logs.
