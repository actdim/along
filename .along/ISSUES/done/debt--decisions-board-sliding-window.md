---
protocol: along
protocol_version: "4.4.16"
slug: decisions-board-sliding-window
type: debt
status: done
completed: 2026-10-17
priority: high
created: 2026-10-17
updated: 2026-10-17
agent: claude-code
tags: [adr, projections, budget]
blocked_by: []
related: [debt--constraints-superseded-adr-filtering, debt--gate-simplification]
---

# DECISIONS.md board: sliding window of recent active ADRs

## Problem

`alongkit.entities.decisions.compile_decisions_board` writes one line (about 150 B) per ADR
into `.along/DECISIONS.md` with no cap, so the 8 KB live-repo budget
(`tests/test_modular_decisions.py::test_live_repo_projection_size_budget`) fails as soon as
enough ADRs exist: 8320 B before debt--gate-simplification, 8421 B after it.
debt--constraints-superseded-adr-filtering (done) only cleaned `CONSTRAINTS.md`. The full list
already lives in `docs/decisions/INDEX.md`.

## Requirements

- REQ-1: The board lists the newest N active ADRs (default 30, by filename date), with the
  total count in the heading and a pointer to `docs/decisions/INDEX.md` for older ones.
- REQ-2: Superseded / retired ADRs are one compact line each: `slug -> superseded_by`.
- REQ-3: N is a named constant, overridable in `.along/config.json` (`budget`), like the
  ISSUES.md recent-done cap.
- REQ-4: The board stays under the 8 KB budget for this repository with headroom.

## Resolution (2026-10-17)

`compile_decisions_board` lists the newest `decisions_board_recent` (default 30, config
`budget.decisions_board_recent`) active ADRs newest first, counts the rest with a pointer to
`docs/decisions/INDEX.md`, and writes superseded ADRs as `slug -> superseded_by`. The live
board went from 8421 B to 5197 B. `test_kb_search` now checks retrieval against the ADR files,
since the board is no longer the full list.

## Acceptance Criteria
- [x] Board shows at most N active ADRs, the total count and the pointer to the full index.
- [x] Superseded entries are compact single lines.
- [x] N configurable; hermetic test covers the window, the count and the compact lines.
- [x] Live-repo budget test passes.
- [x] Automated tests passing.
