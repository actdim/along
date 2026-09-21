---
protocol: along
date: 2026-09-21
slug: updater-explicit-global-sync
agent: antigravity
branch: main
commit: pending
summary: Decoupled repository context updates from global machine skill installation in along_update.py with explicit --global flag.
milestone: v4.0.0-runtime-gates-and-worktree-isolation
issues_advanced: []
issues_completed: [updater-explicit-global-sync]
decisions: []
risks_logged: []
spikes_conducted: []
---

# Session: Decouple Repository Context Updates from Global Machine Skill Installation

## Summary
Decoupled repository context updates from global machine skill installation in `scripts/along_update.py`. Added explicit `--global` / `--sync-global` flag, making repository updates isolated by default across both development and consumer repositories.

## Work Completed
- Refactored `run_update()` in `scripts/along_update.py` to add `sync_global=False` parameter and `--global` / `--sync-global` CLI flag.
- Ensured default behavior (`sync_global=False`) operates in strictly isolated mode: only local repository context (`AGENTS.md` managed block, projections, and runtime hooks) is updated without touching host user directories (`~/.gemini/config/skills/`, `~/.claude/`, etc.).
- Eliminated implicit execution of `install_global_from_local` in the Along dev repository.
- Updated `skills/along-update/SKILL.md` and `docs/topic--skills-reference.md` to document the new `--global` flag and isolated default policy.
- Added hermetic automated test `test_35_along_update_explicit_global_isolation` in `tests/test_skills_and_scripts.py`.
- Closed issue `feat--updater-explicit-global-sync` and synchronized `.along/ISSUES.md`.

## Code Review & Blast Radius
- All 498 tests pass cleanly via `.along/scripts/test.py`.
- `along sanitize` confirms 474 files scanned with zero forbidden non-ASCII typography.
- Hermetic meta-test `test_zz_hermetic_suite.py` verified zero repo root command-line targeting and clean working tree invariants.
