---
protocol: along
protocol_version: "4.2.0"
date: 2026-09-27
slug: external-review-issue-backlog
agent: cowork
branch: main
commit: 86fee5b
summary: "External review of v4.2.0 converted into 19 issues across milestones v4.3.0-v4.5.0 including Cowork runtime support"
milestone: v4.3.0-developer-experience-and-runtime-resilience
issues_advanced: []
issues_completed: []
decisions: []
risks_logged: []
spikes_conducted: []
---

# Session: External review issue backlog

## Summary
External review of v4.2.0 (idea, execution, code, docs) converted into 19 open issues distributed across the existing milestones v4.3.0-v4.5.0 by importance and complexity. Run from Claude Cowork, where Along runtime hooks and global skills are not loaded; the protocol was applied manually through the `along` CLI (`uv run --python 3.12`, because the VM Python 3.10 cannot compile `scripts/along_exec.py`).

## Work Completed
- Reviewed the repository read-only; test suite run on a throwaway copy (Python 3.12: 639 tests, 5 failures, 1 error; Python 3.10: syntax gate aborts).
- Reproduced gate bypasses through `ClaudeCodeAdapter` + `engine.evaluate_event` (MultiEdit, compound and redirected shell commands).
- Checked existing backlog via `along kb-search` for duplicates; linked related issues instead of duplicating (`feat--empirical-benchmark-harness-and-metrics`, `feat--progressive-disclosure-and-context-scaling`, `feat--bounded-prompt-footprint-gate`, `feat--workspace-containment-and-path-scoping`, `feat--test-gated-code-merge-pipeline`).
- Created milestone `v4.2.1-quality-hardening-and-gate-integrity` (12 issues): `bug--py310-fstring-syntax-error`, `task--ci-test-matrix-workflow`, `bug--claude-adapter-unmapped-tools`, `bug--safe-command-prefix-bypass`, `bug--conflict-marker-gate-wrong-target`, `bug--non-hermetic-global-skill-tests`, `bug--test-quiet-script-guard-conflict`, `bug--session-create-unsafe-yaml`, `debt--along-exec-argparse-migration`, `feat--git-level-gate-enforcement`, `feat--cowork-runtime-support`, `bug--worktree-cross-os-mount-guard`.
- Added to `v4.3.0-developer-experience-and-runtime-resilience` (6 issues): `debt--constraints-superseded-adr-filtering`, `docs--vision-md-refresh`, `docs--unverified-performance-claims`, `debt--session-start-context-budget`, `feat--kb-search-archive-scope-default`, `feat--cowork-plugin-skill-packaging`.
- Backlog without milestone: `debt--along-core-extras-split`.
- Recompiled projections: `along issue sync`, `along milestone sync`.

## Observations During the Session
- `along session create` generated this file with an unquoted `summary`, hard-coded `branch: main`, `commit: pending` and the line "Automated tests verified and passing" although no tests were relevant; fixed by hand here, tracked in `bug--session-create-unsafe-yaml`.
- `along issue show` prints a title derived from the slug ("Py310 fstring syntax error") instead of the `--title` given at creation, because `issue create` stores the title only as the H1 heading, not in front-matter.
- A read-only `git status` in the Cowork VM left a stale `.git/index.lock` (the mount forbids deletes); it was moved to `.git/_to_delete/`. Tracked in `feat--cowork-runtime-support`.

## Code Review & Blast Radius
- Only `.along/` entity files changed (19 issues, 1 new milestone, projections, this log, HISTORY). No source code touched, so no test run was required for this stage.
