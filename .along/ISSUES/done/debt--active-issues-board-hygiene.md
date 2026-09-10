---
protocol: along
slug: active-issues-board-hygiene
type: debt
status: done
completed: 2026-09-10
priority: medium
created: 2026-09-10
updated: 2026-09-10
agent: antigravity
tags: [board, issues, hygiene, milestones, entities]
milestone: v3.0.0-global-quality-revision
blocked_by: []
related: [debt--v3-dod-alignment-and-board-reconciliation]
---

# Reconcile Active Issues Board and Milestone Consistency

## Problem
An audit of `.along/ISSUES/` identified 5 stale issues dating back to milestones v1.5.0 and v2.0.0 lingering on the active issues board:
1. `feat--lsif-scip-lsp-mcp-integration`: empty stub without content, superseded by native AST analyzer and code-review-graph.
2. `feat--token-efficiency-and-context-optimization-skills`: implemented across protocol context pruning, KB search IDF snippet scoring, and AGENTS.md trimming.
3. `v1.5.0-dashboard-and-analytics`: remains in `in-progress` (60%) solely due to the two zombie issues above.
4. Three open feature issues (`automated-ui-screenshots-and-visual-verification`, `external-issue-trackers-sync-and-import`, `openclaw-and-hermes-agent-integration`) reference the already-completed milestone `v2.0.0-along-transition`.
5. `.along/SESSIONS/2026/2026-09-09--migration-version-cleanup-and-kb-schema-decoupling.md` contains an unquoted YAML colon in its summary field, causing `along doctor --entities` to fail.

## Requirements
- REQ-1: Mark `feat--lsif-scip-lsp-mcp-integration` as superseded and move to `done/`.
- REQ-2: Mark `feat--token-efficiency-and-context-optimization-skills` as superseded and move to `done/`.
- REQ-3: Reconcile milestone `v1.5.0-dashboard-and-analytics` to `completed` (100%).
- REQ-4: Disassociate stale milestone `v2.0.0-along-transition` from the 3 deferred feature issues.
- REQ-5: Repair YAML front-matter in session log `2026-09-09--migration-version-cleanup-and-kb-schema-decoupling.md`.
- REQ-6: Recompile `.along/ISSUES.md` via `along issue sync`.
- REQ-7: Verify `along doctor --entities` passes with 0 errors.

## Acceptance Criteria
- [x] Stale v1.5.0 issues moved to `done/` with superseded status.
- [x] Milestone v1.5.0 marked completed.
- [x] Stale milestone references cleaned up on deferred issues.
- [x] Session log front-matter parse error resolved.
- [x] `along doctor --entities` passes with 0 errors.
- [x] Test suite passes cleanly.
