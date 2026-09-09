---
protocol: along
date: 2026-08-31
slug: code-review-graph-resilience-and-windows-mcp-optimization
agent: antigravity
branch: main
commit: pending
summary: Eliminate code-review-graph MCP stdio deadlocks on Windows, optimize parser exclusions, and release v2.2.4.
milestone: v2.2.0-along
issues_advanced: []
issues_completed: [bug--code-review-graph-resilience-and-windows-mcp-optimization]
decisions: []
risks_logged: []
spikes_conducted: []
---

# Session: Code Review Graph Windows MCP Optimization & Release v2.2.4

## Summary
Diagnosed and resolved MCP task freezing caused by Windows stdio buffering and multiprocessing pipe deadlocks in `code-review-graph`, excluded ephemeral session blackboards and archive sources from code AST indexing, and prepared v2.2.4 release.

## Work Completed
1. **MCP Transport & Process Deadlock Elimination**:
   - Diagnosed root-cause hang in `code-review-graph serve` on Windows where `ProcessPoolExecutor` in conjunction with stdio pipes blocked asyncio event loop.
   - Updated `mcp_config.json` to launch with `python -u -m code_review_graph serve` and set `CRG_SERIAL_PARSE=1`, `PYTHONUNBUFFERED=1`, and `CRG_GIT_TIMEOUT=10`.
2. **Graph Exclusions**:
   - Updated `.code-review-graph-ignore` to exclude `.archive/` and `.along/.session/`.
3. **Graph Rebuild & Verification**:
   - Executed full graph build: 52 files, 357 nodes, 5110 edges in 1.5s.
   - Verified `status`, `update`, and `detect-changes` commands execute instantaneously.
4. **Automated Testing**:
   - Verified 28 unit tests pass with 0 errors.

## Code Review & Blast Radius
- **Blast Radius**: Zero breaking changes to public APIs. MCP config is stabilized for Windows environments.
- **Typographic Cleanliness**: Verified clean ASCII formatting across all modified files.
- **Tests**: 100% test pass rate across suite.

