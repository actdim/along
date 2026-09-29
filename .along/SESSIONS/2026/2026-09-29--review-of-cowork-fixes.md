---
protocol: along
protocol_version: "4.2.1"
date: 2026-09-29
slug: review-of-cowork-fixes
agent: claude-code
branch: main
commit: a94d382
summary: Audited the 8 Cowork-closed v4.3.0 issues; fixed residual shell-classifier bypasses; added .github/workflows/tests.yml and closed CI matrix task
issues_advanced: []
issues_completed: [bug--shell-classifier-residual-bypasses, task--ci-test-matrix-workflow]
decisions: []
risks_logged: []
spikes_conducted: []
milestone: v2.0.0-along-transition
---

# Session: Review of cowork fixes

## Summary
Audited the 8 Cowork-closed v4.3.0 issues; fixed residual shell-classifier bypasses; added .github/workflows/tests.yml and closed CI matrix task

## Work Completed
- Audit of the 8 issues closed in the 2026-09-27 Cowork session: 7 correct; `bug--safe-command-prefix-bypass` left bypasses (lone `&`, `python -c "print(1); ..."`, `git branch -D`, `git diff --output`).
- Fixed them in `scripts/alongkit/hooks/shellparse.py` under `bug--shell-classifier-residual-bypasses`, with 25 new table cases in `tests/test_shell_classification.py`.
- Added `.github/workflows/tests.yml` from the Cowork draft and completed all acceptance criteria for `task--ci-test-matrix-workflow`.
- `.git/_to_delete/` and `.git/index.lock` were already gone; nothing to remove.

## Code Review & Blast Radius
- Tests: `python .along/scripts/test.py -q` - 699 tests OK (Python 3.12, Windows). `compileall` on Python 3.10 via uv passes. `along sanitize`: no banned characters.
- Blast radius: `shellparse.is_read_only_command` is used only by `predicates.check_mutation_authorization`; stricter classification can only move commands from allow to plan-approval.
- Note: the auto-generated tests line read a hooks activity trace from 2026-09-27, i.e. not scoped to this session.
- Nothing committed, by request.
