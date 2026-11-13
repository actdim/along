---
protocol: along
protocol_version: "4.8.1"
slug: stale-protocol-path-comment
type: debt
status: done
completed: 2026-11-13
priority: low
created: 2026-11-12
updated: 2026-11-13
agent: claude-code
tags: [docs, comment]
blocked_by: []
related: [bug--protocol-leaks-into-docs]
plan_status: approved
---

# Stale docs/topic--along-protocol.md path in budget.py comment

`bug--protocol-leaks-into-docs` moved the protocol reference from `docs/topic--along-protocol.md` to `.along/PROTOCOL.md`, but the comment on `DEFAULT_BUDGET_LIMITS` in `scripts/alongkit/budget.py` still names the old path. Comment-only fix; no behavior change.

## Requirements
- REQ-1: The `agents_md_bytes` comment in `scripts/alongkit/budget.py` MUST name `.along/PROTOCOL.md` as the location of situational procedures.

## Acceptance Criteria
- [x] `scripts/alongkit/budget.py` no longer references `docs/topic--along-protocol.md`.
- [x] Test suite (`python .along/scripts/test.py`) passes after the edit.
