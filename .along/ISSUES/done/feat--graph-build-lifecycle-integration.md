---
protocol: along
slug: graph-build-lifecycle-integration
type: feat
status: done
completed: 2026-09-15
priority: high
created: 2026-09-15
updated: 2026-09-15
agent: antigravity
tags: [code-review-graph, mcp, lifecycle, cli, blast-radius, graph-build]
milestone: v1.3.0-knowledge-base-and-graph
blocked_by: []
related: [feat--native-ast-blast-radius-analyzer]
---

# Graph Build Lifecycle Integration

## Problem

The `code-review-graph` MCP server is installed and configured by Along installers,
but no Along skill, CLI command, or lifecycle hook ever calls `build_or_update_graph_tool`.
The graph is always empty. Skills that read the graph (`along-wrap`, `along-team`)
silently fall back to degraded grep-based blast-radius analysis every time.

Additionally, `along-init` does not scaffold `.code-review-graph-ignore`, causing
`build_or_update_graph_tool` to scan `node_modules` and timeout on any project
with JS dependencies.

## Requirements

- REQ-1: Implement `along graph-build` CLI command (`scripts/along_graph_build.py`)
  that connects to the `code-review-graph` MCP server via stdio JSON-RPC and calls
  `build_or_update_graph_tool`. Supports `--full` (full rebuild) and incremental (default).
- REQ-2: `along-init` scaffolds `.code-review-graph-ignore` with standard exclusions
  (node_modules, dist, build, .venv, __pycache__, site, .git).
- REQ-3: `along-update` triggers incremental graph update after protocol refresh.
- REQ-4: Register `graph-build` in `along_exec.py` TOOL_MAPPINGS and installer aliases.
- REQ-5: Update `along-graph-check` SKILL.md to reference the new build command.
- REQ-6: Update docs (cli-reference, skills-reference, README skill table).
- REQ-7: Hermetic tests for the new script and init scaffolding.

## Acceptance Criteria

- [x] `along graph-build` connects to MCP server, triggers full or incremental build, prints result.
- [x] `along graph-build --full` forces full rebuild.
- [x] `along-init` creates `.code-review-graph-ignore` if missing (non-destructive).
- [x] `along-update` calls incremental graph build after sync engines.
- [x] `along_exec.py` routes `graph-build` to the new script.
- [x] Tests pass hermetically.
- [x] Documentation updated.
