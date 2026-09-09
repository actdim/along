---
protocol: along
date: 2026-09-09
slug: entity-status-enum-and-unused-taxonomy
agent: antigravity
branch: main
commit: pending
summary: Extended issue status enum with non-delivered terminal states (superseded, cancelled, duplicate), added supersession and duplicate graph linking, implemented type inference assistance, updated dashboard metrics to compute bug/debt ratio, and corrected misclassified historical entities.
milestone: v3.0.0-global-quality-revision
issues_advanced: []
issues_completed: [debt--entity-status-enum-and-unused-taxonomy]
decisions: []
risks_logged: []
spikes_conducted: []
---

# Session: Entity Status Enum and Taxonomy Quality Revision

## Summary
Addressed unused decorative taxonomy and missing terminal issue outcomes. Extended the issue status enum to support `superseded`, `cancelled`, and `duplicate`, added front-matter fields `superseded_by` and `duplicate_of` with full DAG integration, added type inference warnings to `along issue create`, provided status and reference flags to `along issue done`, updated dashboard collector to exclude non-delivered issues from completion counts and calculate `bug_debt_ratio`, and reclassified 5 misclassified historical issues in `ISSUES/done/`.

## Work Completed
1. **Core Vocabulary & Schemas (`scripts/alongkit/entities.py`, `dashboard/schemas/`)**:
   - Extended `ISSUE_STATUSES` with `superseded`, `cancelled`, and `duplicate`.
   - Defined `CLOSED_ISSUE_STATUSES` and `DELIVERED_ISSUE_STATUSES` (`done` only).
   - Added `superseded_by` and `duplicate_of` to `IssueSchema`.
   - Added `bug_debt_ratio` to `DashboardMetricsSchema` and extended `StatusBreakdown`.
2. **Dashboard Collector & DAG (`dashboard/core/collector.py`, `dashboard/core/graph.py`, `dashboard/app.py`)**:
   - Collected `superseded_by` and `duplicate_of` front-matter fields.
   - Counted extended statuses and calculated `bug_debt_ratio`.
   - Ensured `done_issues` count only reflects delivered issues (`status: done`).
   - Added DAG edges for supersession and duplication.
   - Added UI metrics for superseded/cancelled count and bug/debt ratio.
3. **Validation & CLI Assistance (`scripts/alongkit/entities.py`, `scripts/along_exec.py`)**:
   - Added `infer_issue_type` heuristics covering bug, debt, and docs keywords.
   - Added type inference notice to `along issue create` when `feat` matches bug/debt keywords.
   - Enhanced `along issue done` / `close` with `--status`, `--superseded-by`, and `--duplicate-of`.
   - Enhanced `compile_issues_board` to render `[~]` for non-delivered closed issues.
   - Extended `validate_entities` to enforce `completed` date on all closed statuses and validate `superseded_by` and `duplicate_of` targets.
4. **Historical Entity Reclassification (`.along/ISSUES/done/`)**:
   - Reclassified `feat--add-sqlite-vector-indexing.md` to `status: superseded`, `superseded_by: feat--integrate-wiki-llm-mcp`.
   - Reclassified `feat--integrate-wiki-llm-mcp.md` to `status: cancelled`.
   - Reclassified and renamed `feat--code-review-graph-resilience-and-windows-mcp-optimization.md` to `bug--...` (`type: bug`).
   - Reclassified and renamed `feat--installer-junction-fallback-and-dependencies.md` to `bug--...` (`type: bug`).
   - Reclassified and renamed `feat--centralize-scripts-and-clean-skills-purity.md` to `debt--...` (`type: debt`).
   - Reconciled all target issue references across `.along/MILESTONES/` and `.along/SESSIONS/2026/`.
5. **Protocol & Documentation Sync (`AGENTS.md`, `skills/along-init/protocol.md`, `docs/topic--domain-model.md`)**:
   - Synchronized Issue front-matter schema in `skills/along-init/protocol.md` and `AGENTS.md` identically.
   - Documented delivered vs non-delivered outcomes and DAG linking in `docs/topic--domain-model.md`.
6. **Test Suite Expansion (`tests/test_issue_lifecycle.py`, `tests/test_skills_and_scripts.py`)**:
   - Added tests for `issue done` with `--status` and `--superseded-by`.
   - Added tests for `issue create` type inference notice.
   - Added doctor tests for dangling `superseded_by` and `duplicate_of`.
   - Added collector test verifying non-delivered issues excluded from `done_issues` and `bug_debt_ratio` computation.

## Verification
- `python .along/scripts/test.py`: 327 unit tests passing (0 failures, 0 errors).
- `python scripts/along_exec.py doctor --entities`: 0 errors, 0 warnings across 166 entities.
- `python scripts/along_exec.py sanitize`: 300 files scanned, 0 typography violations.
- `python scripts/along_exec.py kb-sync`: Clean documentation compile and link check.
- `code-review-graph`: timed out; degraded to static search fallback (all AST callers verified intact).
