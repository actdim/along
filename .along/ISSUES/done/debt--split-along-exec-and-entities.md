---
protocol: along
protocol_version: "4.4.16"
slug: split-along-exec-and-entities
type: debt
status: done
completed: 2026-10-16
priority: high
created: 2026-10-16
updated: 2026-10-16
agent: antigravity
tags: [cli, refactor, dx]
blocked_by: []
related: []
---

# Decompose along_exec.py and alongkit/entities.py into modular subsystems

## Problem

`scripts/along_exec.py` (2128 lines, 97KB) and `scripts/alongkit/entities.py` (2335 lines, 96KB) have grown into monolithic files.
`along_exec.py` still contains ~500 lines of doctor checks, ~310 lines of session/plan handling, ~190 lines of telemetry, and gate/circuit logic that should live in dedicated `alongkit/commands/` modules.
`alongkit/entities.py` conflates core vocabulary and slugs, ADR management, board projections, and filesystem queries in a single file.
Additionally, when CLI errors occur, unhandled Python tracebacks prompt external agents to inspect engine internals, burning context and violating the black-box invariance rule.

## Requirements

- REQ-1: Extract `doctor` checks and zombie doc detection from `along_exec.py` into `alongkit/commands/doctor.py`.
- REQ-2: Extract `start` and `plan` command handlers from `along_exec.py` into `alongkit/commands/lifecycle.py` (or `plan.py`).
- REQ-3: Extract `telemetry` command handlers from `along_exec.py` into `alongkit/commands/telemetry.py`.
- REQ-4: Extract `gates`, `rules`, `tool`, `circuit`, `budget` into dedicated command modules in `alongkit/commands/`.
- REQ-5: Refactor `along_exec.py` into a thin CLI router (< 300 lines) with lazy imports for all command handlers to preserve fast CLI startup time.
- REQ-6: Refactor `alongkit/entities.py` into focused modules under `alongkit/entities/` (`vocabulary.py`, `decisions.py`, `projections.py`, `query.py`), exposing a backward-compatible facade via `alongkit/entities/__init__.py` or `alongkit/entities.py`.
- REQ-7: Add CLI top-level error formatting that prevents raw tracebacks on user input or validation errors, printing actionable suggestions instead.
- REQ-8: All existing tests in `tests/test_alongkit.py` and `tests/test_skills_and_scripts.py` must pass with zero regressions.

## Acceptance Criteria

- [x] `along_exec.py` is under 400 lines and acts solely as an entrypoint/router
- [x] Command handlers modularized in `alongkit/commands/`
- [x] `alongkit.entities` functionality decomposed into clean domain modules with full backward compatibility
- [x] Raw tracebacks suppressed on standard CLI errors with actionable hints
- [x] Automated tests passing
