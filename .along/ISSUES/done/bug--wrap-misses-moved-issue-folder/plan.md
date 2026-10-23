# Living Plan: wrap-misses-moved-issue-folder

## Revision 1 (2026-10-23T17:13:14Z, ExitPlanMode)

Execution Mode: Direct (one function pair in one module plus one regression test)

- Step 1: Regression tests in `tests/test_lifecycle_wrap.py` next to `test_16b_wrap_auto_commits_by_default`: a wrap with auto-commit leaves no untracked file of `.along/ISSUES/` and tracks `done/<key>/plan.md`; with `no_commit=True` the warning lists `done/<key>/plan.md`. Run red on the current code.
- Step 2: `scripts/alongkit/lifecycle.py`: helper `_issue_folder_changes(dest_file, top, changed_keys)` on `closeout.issue_folder_files`; `_auto_commit_wrapped_work` and `_warn_uncommitted_work` seed `dirty_entities` with it.
- Step 3: Full suite; commit via `along commit`; wrap with the repo CLI so the fix applies to its own wrap.

## Revision 2 (2026-10-23T17:25:00Z, during implementation)

Reason: the regression test showed the ticket's deletion at its open place also left unstaged when the ticket carried no edit events; same move, within REQ-1.

- `_issue_folder_changes` also returns the ticket's open path.
- `tests/test_session_records.py::test_uncommitted_wrap_before_stop_warns` relied on that leftover deletion to get its warning; it now wraps with `no_commit=True`, the scenario it tests.
