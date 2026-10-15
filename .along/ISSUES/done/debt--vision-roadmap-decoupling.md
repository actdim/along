---
protocol: along
protocol_version: "4.4.14"
slug: vision-roadmap-decoupling
type: debt
status: done
completed: 2026-10-15
priority: medium
created: 2026-10-15
updated: 2026-10-15
agent: antigravity
tags: [vision, roadmap, decoupling, testing]
blocked_by: []
related: [docs--vision-md-refresh]
---

# Decouple VISION.md Roadmap from granular milestones and relax test requirements

## Problem

`.along/VISION.md` currently duplicates phase checkboxes that exist in `.along/MILESTONES/` and `.along/ISSUES/`. This dual-state maintenance leads to inevitable drift (e.g. Phase 5 was completed in `v4.5.0-multi-user-merge-automation.md` but remained unchecked in `VISION.md`). Furthermore, `tests/test_vision.py` hard-coded a mandatory file existence assertion that fails if `VISION.md` is absent or reorganized, treating a strategic boundary document as a fragile binary test constraint.

## Requirements

- REQ-1: Refactor `## Roadmap` in `.along/VISION.md` into high-level strategic horizons, delegating granular phase tracking and milestones to `.along/MILESTONES/` and `.along/ISSUES/`.
- REQ-2: Preserve `Scope` and `Non-goals` in `.along/VISION.md` as permanent guardrails against agent context amnesia and scope drift.
- REQ-3: Relax `tests/test_vision.py` so that `.along/VISION.md` is validated when present, but gracefully skips if absent, removing rigid test failure on missing vision in minimal contexts.

## Acceptance Criteria

- [x] `.along/VISION.md` reflects strategic horizons and delegates granular roadmap to `MILESTONES/` and `ISSUES/`.
- [x] `Scope` and `Non-goals` remain intact with clean ASCII typography.
- [x] `tests/test_vision.py` passes cleanly via `python .along/scripts/test.py tests.test_vision`.
- [x] No regression across full test suite.
