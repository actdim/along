---
protocol: along
slug: bounded-context-budget-and-active-projections
title: "Bounded Context Budget, Active Constraints Projection, and Sliding Window Issues"
date: 2026-09-07
status: accepted
tags: [adr, architecture, decision]
---

# ADR-2026-09-07--bounded-context-budget-and-active-projections - Bounded Context Budget, Active Constraints Projection, and Sliding Window Issues

- Date: 2026-09-07
- Status: accepted
- Context:
  1. `ADR-2026-08-15--single-file-append-only-decisions` selected a single append-only file under the rationale that agents load all constraints on session start in one tool call (< 300 tokens).
  2. With 31 ADRs accumulated, `.along/DECISIONS.md` grew to 72+ KB (~19,000 tokens), causing a 60x divergence from the recorded rationale and imposing massive token overhead before any productive work.
  3. Simultaneously, `.along/ISSUES.md` accumulated all 67 completed issues without a limit, growing to 10.5 KB.
  4. Splitting ADRs into separate files would break Git union merge compatibility (`merge=union`) across parallel branches and break existing deep links and test assertions (`test_kb_search.py`).
- Decision:
  1. **Dual-Layer Decision Architecture**:
     - `.along/DECISIONS.md` remains the append-only Single Source of Truth (SSOT) preserving Git union merge safety and complete historical rationale.
     - `.along/CONSTRAINTS.md` is compiled by `along decision sync` as an ultra-compact projection (< 4 KB) containing only active architectural rules and constraints extracted from non-superseded ADRs.
     - `AGENTS.md` mandates reading `.along/CONSTRAINTS.md` on session start instead of the full historical archive.
  2. **Sliding Window Issues Projection**:
     - `along_exec.py issue sync` and `issue done` cap `## Done (recent)` in `.along/ISSUES.md` to a sliding window of the 5 most recent closed issues, sorted chronologically by `completed` date.
     - Older completed issues remain archived in `.along/ISSUES/done/`.
  3. **Context Budget Enforcement**:
     - Provide `along context-budget` (`scripts/alongkit/budget.py`) with `--json` and `--check` modes.
     - Enforce hard budget limits in `tests/test_context_budget.py` (`AGENTS.md` <= 16 KB, `ISSUES.md` <= 4 KB, `CONSTRAINTS.md` <= 6 KB, mandatory startup context <= 25 KB).
  4. **Supersession**:
     - This ADR supersedes `ADR-2026-08-15--single-file-append-only-decisions`.
- Consequences:
  - Bounded always-on session startup overhead reduced from ~113 KB (~29k tokens) to under 25 KB (~6.5k tokens), an ~80% reduction.
  - Full Git union merge safety and complete historical ADR provenance are preserved.
  - Automated CI tests fail immediately if any projection or entry point exceeds its context budget.
