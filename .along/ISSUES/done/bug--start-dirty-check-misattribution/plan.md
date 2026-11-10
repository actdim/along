# Plan: along start must not blame the session's own edits on wrapped issues

## Execution Mode
Direct

Target executor: a fast model. One block of `along start` changes, plus tests.

## Facts verified in code
`scripts/alongkit/commands/lifecycle.py`, start handler, block `if not is_worktree:`
(around lines 103-156):
- Check 1 builds `wrapped_groups` from `closeout.done_issues_attribution(repo_root)`:
  any dirty path that a wrapped issue's session log ever listed is blamed on it. It
  never asks whether an in-progress issue edited that path since.
- Check 2 already uses `session.attributed_files(repo_root, other_slug)` (the edit
  ledger) and maps paths to the git top with
  `repo.canonical_relpath(os.path.join(repo_root, p), top)` plus `closeout.path_key`.
- `key = session.current_session_key()` is computed only later in the function.

## Step 1: skip both checks on a re-start of the session's own issue (REQ-2)
Before `if not is_worktree:` add:
```python
key_now = session.current_session_key()
_bctx, bound_slug = session.bound_blackboard(repo_root, key_now)
restart_own = issue.get("status") == "in-progress" and bound_slug == issue["slug"]
```
and change the condition to `if not is_worktree and not restart_own:`.

## Step 2: exclude paths claimed by in-progress issues from check 1 (REQ-1, REQ-3)
Inside `if changes:`, before the `for dkey, dinfo in done_attr.items()` loop:
```python
in_progress = [i for i in entities.scan_issues(repo_root) if i.get("status") == "in-progress"]
if issue.get("status") != "in-progress":
    in_progress.append(issue)  # the issue being started may hold earlier edit events
claimed = set()
for ip in in_progress:
    for p in session.attributed_files(repo_root, ip["slug"]):
        claimed.add(closeout.path_key(repo.canonical_relpath(os.path.join(repo_root, p), top)))
unattributed_candidates = [p for p in changes if closeout.path_key(p) not in claimed]
```
Then the existing loop uses `unattributed_candidates` as today. Reuse the same path
conversion as check 2 (copy it, do not invent a new one). Then reuse `in_progress` in
check 2 instead of calling `scan_issues` a second time (filter out `issue["slug"]`).

Paths only a wrapped issue touched are still blocked (REQ-3): no other change.

## Step 3: tests (`tests/test_start_guard.py`, reuse its fixtures)
1. `test_dirty_path_claimed_by_in_progress_issue_is_not_blamed_on_wrapped`: wrapped
   issue's session log lists `a.py`; in-progress issue X has an `edit` event for `a.py`;
   `a.py` is dirty; `along start X --write-scope sub/` exits 0 and adds the scope.
2. `test_restart_own_bound_issue_skips_dirty_checks`: session bound to in-progress X,
   other dirty files of another in-progress issue exist; `along start X` exits 0 without
   `--allow-dirty`.
3. `test_dirty_path_only_wrapped_issue_touched_still_blocks`: as today (keep or confirm the
   existing test covers it).
4. All existing tests in the file pass unchanged.

## Verification
```bash
python .along/scripts/test.py tests/test_start_guard.py
```
```bash
python .along/scripts/test.py -q
```

## Out of scope
- `--write-scope` handling itself, `along scope add` (see `feat--plan-grants-write-scope`).
