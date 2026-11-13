# Living Plan: stale-protocol-path-comment

## Revision 1 (2026-11-13T13:09:25Z, ExitPlanMode)

# Plan: debt--stale-protocol-path-comment

Execution Mode: Direct

## Context
`bug--protocol-leaks-into-docs` moved the protocol reference from `docs/topic--along-protocol.md` to `.along/PROTOCOL.md`. One comment in `scripts/alongkit/budget.py:30` still names the old path. Comment-only fix, no behavior change.

## Change
- `scripts/alongkit/budget.py:30`: replace `docs/topic--along-protocol.md` with `.along/PROTOCOL.md` in the `DEFAULT_BUDGET_LIMITS` comment.

## Verification
- Grep `scripts/` for `topic--along-protocol` in comments: only the intentional legacy-cleanup references remain (`along_update.py`, `migrate_protocol.py`, `along_kb_sync.py`).
- Run `python .along/scripts/test.py` (quiet).
- `along sanitize` on the file (ASCII typography).

## Closeout
- Commit via `/along-commit` bound to `stale-protocol-path-comment`.
- `along wrap stale-protocol-path-comment --summary "..." --no-decisions`.
