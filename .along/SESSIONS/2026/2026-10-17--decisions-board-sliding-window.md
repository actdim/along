---
protocol: along
protocol_version: "4.4.16"
date: 2026-10-17
slug: decisions-board-sliding-window
agent: claude-code
branch: main
commit: 348766f
summary: 'DECISIONS.md board is a sliding window: newest 30 active ADRs, count and pointer to docs/decisions/INDEX.md, compact superseded lines (8421 B to 5197 B)'
issues_advanced: []
issues_completed: [debt--decisions-board-sliding-window]
decisions: []
risks_logged: []
spikes_conducted: []
---

# Session: Decisions board sliding window

## Summary
DECISIONS.md board is a sliding window: newest 30 active ADRs, count and pointer to docs/decisions/INDEX.md, compact superseded lines (8421 B to 5197 B)

## Decisions
- None (confirmed at wrap: no architectural decisions).

## Blackboard Record

Execution mode: direct; plan revision 1; approved: true.

### Attributed Files

| Path | Kind | Edits | Last edit | Sessions |
| --- | --- | --- | --- | --- |
| `.along/ISSUES/debt--decisions-board-sliding-window.md` | state | 1 | 2026-10-17T19:59:52Z | claude--9d7ca833-45a1-4de5-bb24-0d65e05e8c19 |
| `scripts/alongkit/entities/__init__.py` | source | 3 | 2026-10-17T19:46:02Z | claude--9d7ca833-45a1-4de5-bb24-0d65e05e8c19 |
| `scripts/alongkit/entities/decisions.py` | source | 2 | 2026-10-17T19:45:39Z | claude--9d7ca833-45a1-4de5-bb24-0d65e05e8c19 |
| `tests/test_kb_search.py` | source | 1 | 2026-10-17T19:54:23Z | claude--9d7ca833-45a1-4de5-bb24-0d65e05e8c19 |
| `tests/test_modular_decisions.py` | source | 1 | 2026-10-17T19:45:50Z | claude--9d7ca833-45a1-4de5-bb24-0d65e05e8c19 |

### Plan

#### Living Plan: decisions-board-sliding-window

Title: Decisions board sliding window

Approved by the user via ExitPlanMode on 2026-10-17 (copied from the plan-mode file; the
installed global hook predates ExitPlanMode capture). Approach chosen by the user: sliding window.

##### Steps
- [x] Step 1: Windowed board, config override, tests, recompile

##### Approved plan

Execution Mode: Direct (2 source files + 2 test files, one subsystem).

1. `alongkit/entities/decisions.py` `compile_decisions_board`: constant
   `DECISIONS_BOARD_RECENT = 30`, override `.along/config.json` `budget.decisions_board_recent`;
   newest N active ADRs newest first, heading with total and "newest N shown", a line
   `Older decisions (<k>): docs/decisions/INDEX.md`; superseded ADRs as `slug -> superseded_by`;
   intro paragraph dropped.
2. `tests/test_modular_decisions.py`: compact superseded line, window test with config
   override, budget test docstring.
3. `along decision sync`; check the board size.

Verification: decision tests, then the full suite green with no bypass; commit
debt--gate-simplification first, then this issue.

### Execution Trace

#### Execution Trace: decisions-board-sliding-window
- 2026-10-17T19:45:23Z phase: planning -> execution
- 2026-10-17T19:45:23Z plan approved (ExitPlanMode) approved_via: exit-plan-mode
- 2026-10-17T19:45:39Z edit scripts/alongkit/entities/decisions.py (x2)
- 2026-10-17T19:45:50Z edit tests/test_modular_decisions.py
- 2026-10-17T19:46:02Z edit scripts/alongkit/entities/__init__.py (x3)
- 2026-10-17T19:54:23Z edit tests/test_kb_search.py
- 2026-10-17T19:59:23Z test pass (Pre-Commit Quality Gate)
- 2026-10-17T19:59:52Z edit .along/ISSUES/debt--decisions-board-sliding-window.md
