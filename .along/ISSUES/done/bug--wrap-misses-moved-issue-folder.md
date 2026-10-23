---
protocol: along
protocol_version: "4.5.2"
slug: wrap-misses-moved-issue-folder
type: bug
status: done
completed: 2026-10-23
priority: medium
created: 2026-10-23
updated: 2026-10-23
agent: claude-code
tags: [wrap, plans]
blocked_by: []
related: [feat--pre-approved-plans]
---

# along wrap does not commit the issue folder moved to done/

Since `feat--pre-approved-plans`, an issue's plan lives in `.along/ISSUES/<key>/plan.md` and
`along wrap` moves that folder to `.along/ISSUES/done/<key>/` with the ticket. The wrap
auto-commit (`lifecycle._auto_commit_wrapped_work`) stages the attributed files, the moved
ticket, the session log and the projections, but not the issue folder at its new place: the
commit records the old `plan.md` as deleted (it was attributed through edit events) and the
new `done/<key>/plan.md` is left untracked. Observed on the wrap of `feat--pre-approved-plans`
(commit 6566193; the file was committed by hand in bb65864). `_warn_uncommitted_work` has the
same blind spot.

The regression test also showed the ticket's deletion at its open place staged only when the
ticket carried edit events (the old ticket file was left as an unstaged deletion otherwise):
the same move, fixed with it.

## Requirements
- REQ-1: The wrap auto-commit MUST stage the changed files of the wrapped issue's folder at both places (the open folder the move deleted and the folder in `done/`), and the ticket's deletion at its open place.
- REQ-2: The uncommitted-work warning after a wrap without auto-commit MUST list those files too.

## Acceptance Criteria
- [x] A wrap of an issue with `ISSUES/<key>/plan.md` commits `ISSUES/done/<key>/plan.md` and leaves no untracked file of the folder.
- [x] A regression test fails on the current code and passes with the fix (`test_16c`, `test_16d` in `tests/test_lifecycle_wrap.py`).
- [x] Automated tests passing (`python .along/scripts/test.py -q`, 1592 tests).
