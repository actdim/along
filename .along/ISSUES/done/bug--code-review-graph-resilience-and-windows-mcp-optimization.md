---
protocol: along
slug: code-review-graph-resilience-and-windows-mcp-optimization
type: bug
status: done
completed: 2026-08-31
priority: high
created: 2026-08-31
updated: 2026-08-31
agent: antigravity
tags: [mcp, crg, windows]
milestone: v2.2.0-along
blocked_by: []
related: []
---

# Code Review Graph Windows MCP Deadlock Elimination & Optimization

Eliminate MCP subprocess deadlocks on Windows by switching MCP server execution to unbuffered Python (`-u`), enforcing serial parsing (`CRG_SERIAL_PARSE=1`), setting tight git subprocess timeouts (`CRG_GIT_TIMEOUT=10`), and updating `.code-review-graph-ignore` to exclude ephemeral sessions and archive artifacts.

## Acceptance Criteria
- [x] Fixed `mcp_config.json` with unbuffered stdio transport and `CRG_SERIAL_PARSE=1` to prevent Windows `ProcessPoolExecutor` pipe deadlocks.
- [x] Updated `.code-review-graph-ignore` to exclude `.archive/` and `.along/.session/`.
- [x] Verified `code-review-graph` rebuild and status across 52 repository files (357 nodes, 5110 edges).
- [x] 100% unit tests pass with zero failures.

