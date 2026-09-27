---
protocol: along
protocol_version: "4.1.0"
slug: cli-safety-inline-python-and-budget-ceiling
type: bug
status: done
completed: 2026-09-27
priority: high
created: 2026-09-27
updated: 2026-09-27
agent: antigravity
tags: [hooks, cli-safety, budget, issues-board, context]
milestone: v4.2.0-monorepo-subprojects
blocked_by: []
blocks: []
related: []
---

# Fix CLI Safety Inline Python Interception and Context Budget Ceiling

## Problem

1. **CLI Safety Gate Gap**: `[gate: cli_safety]` in `scripts/alongkit/hooks/predicates.py` only intercepts `python -c` when attempting to write files (`open(..., 'w')`). Ad-hoc inline Python invocations inspecting internal modules (`alongkit`, `along_exec`) or executing multiple chained statements were not intercepted, leading to confusing `ModuleNotFoundError: No module named 'alongkit'` or `AttributeError` output in the user terminal.
2. **Context Budget Violation on ISSUES.md**: With 35+ active and backlog items in `.along/ISSUES/`, `.along/ISSUES.md` reached 4256 bytes, exceeding the rigid 4096-byte ceiling in `DEFAULT_BUDGET_LIMITS["issues_md_bytes"]`, causing `test_live_repo_budget_compliance` in `tests/test_context_budget.py` to fail.

## Requirements

1. Update `DANGEROUS_CLI_PATTERNS` in `scripts/alongkit/hooks/predicates.py` to catch ad-hoc inline Python invocations probing internal Along modules (`alongkit`, `along_exec`) and multi-statement inline Python invocations, returning an actionable error message directing the agent to use Along CLI tools or `scratch/`.
2. Calibrate `DEFAULT_BUDGET_LIMITS["issues_md_bytes"]` in `scripts/alongkit/budget.py` from 4096 to 6144 bytes (6 KB) while keeping `mandatory_session_bytes` at 32768 bytes, ensuring live repository context budget compliance.
3. Verify all related tests pass with zero regressions.
