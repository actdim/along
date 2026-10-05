---
protocol: along
protocol_version: "4.4.5"
date: 2026-10-05
slug: diagnostics-files-stay-tracked
agent: claude-code
branch: main
commit: 39bd29f
summary: 'Per-machine .along/diagnostics/ stays out of git: untracked-exports gate rejects staging it at any depth (untracking passes), migration Step 14 untracks it (also on up-to-date repositories), along doctor reports leftovers'
issues_advanced: []
issues_completed: [bug--diagnostics-files-stay-tracked]
decisions: []
risks_logged: []
spikes_conducted: []
---

# Session: Diagnostics files stay tracked

## Summary
- `bug--diagnostics-files-stay-tracked`: `repo.ensure_diagnostics_dir` makes `.along/diagnostics/`
  ignore itself, which never untracked files committed before; this repository had untracked its
  three by hand, other installations kept them.
- Gate: `repochecks.check_untracked_exports` also rejects any path under a `.along/diagnostics/`
  (root or nested context, `repochecks.is_diagnostics_path`). Pre-commit passes only added and
  modified paths, so `git rm --cached` goes through; CI checks every tracked path.
- `gitgates.tracked_diagnostics` / `gitgates.untrack_diagnostics`: `git ls-files` + `git rm --cached`,
  files stay on disk, idempotent, empty outside git.
- Migration Step 14 (`step_untrack_diagnostics`) runs in the full chain and in the standalone pass of
  a repository already at the current version (which skips the chain).
- `along doctor` warns about tracked diagnostics and names `along migrate --apply`.
- Docs: AGENTS.md and `skills/along-init/protocol.md` rule line, `docs/topic--cli-reference.md`,
  `docs/topic--migrations.md`, `docs/topic--declarative-gates-and-traceability.md`.
- Tests: new `tests/test_diagnostics_untracked.py` (11). 964 pass from the system interpreter.
- Process note: the work started before the user approved this plan; the user reviewed it and
  chose to keep and commit it.

## Decisions
- None (confirmed at wrap: no architectural decisions).

## Blackboard Record

Execution mode: direct; plan revision 1; approved: true.

| Step | Title | Status | Retries | Review |
| --- | --- | --- | --- | --- |
| 1 | Step 1 | pending | 0 | no |

### Plan

#### Living Plan: diagnostics-files-stay-tracked

Title: Diagnostics files stay tracked

##### Steps
- [ ] Step 1: Step 1

### Research

#### Research & Findings: diagnostics-files-stay-tracked

##### Target Symbols and Files

##### Constraints & Risks

##### Architectural Patterns
