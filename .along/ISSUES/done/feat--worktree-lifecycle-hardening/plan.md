# Plan: worktree lifecycle hardening (wrap guard, teardown, doctor, commit notice)

## Execution Mode
Direct

Target executor: a fast model. Follow the steps in order.

## Review notes (why this plan differs from the first draft)
- BUG in the first draft: "unmerged = `git rev-list HEAD..along/<slug>` is non-empty".
  `along worktree merge` defaults to `--squash` (`worktree.merge_worktree`). A squash
  merge never makes the branch an ancestor of HEAD, so that check would block EVERY wrap
  after a normal merge. Use a content check instead (Step 1).
- Doctor: report only worktrees whose issue is closed or missing. "Branch already merged"
  is dropped from doctor (same squash problem, and wrap now cleans those up).
- Commit notice (REQ-4, SHOULD): kept, but a single printed line, no new flag.
- Teardown failures never fail a wrap: `remove_worktree` already quarantines locked dirs
  into `.trash_*` and `along worktree gc` cleans them.

## Facts verified in code (`scripts/alongkit/worktree.py`)
- `get_worktree_path(repo_root, slug)` -> `.along/worktrees/<slug>`; branch `along/<slug>`.
- `remove_worktree(repo_root, slug, force=True, delete_branch=True) -> bool` flushes the
  blackboard, unlinks junctions, removes with retries, quarantines on lock, and runs
  `git branch -D`.
- `list_worktrees(repo_root)` -> `[{slug, path, branch, ...}]`; `gc_worktrees` exists.
- `scripts/alongkit/lifecycle.py` `execute_wrap(...)`: all checks run before the first
  write; forced checks use the `force_reason` / `_force_allowed()` / `forced.append(...)`
  pattern (see the "along-team step discipline" block around line 1125).
- `scripts/alongkit/commands/doctor.py`: checks are `_doctor_*_checks(repo_root, warnings)`
  functions called from `handle_doctor_command`.

## Step 1: `worktree.close_blockers(repo_root, slug) -> List[str]`
Empty list = safe to wrap and remove. Nothing on disk -> `[]`.
```python
wpath = get_worktree_path(repo_root, slug)
if not os.path.isdir(wpath):
    return []
out = []
st = proc.git(["status", "--porcelain"], cwd=wpath)
dirty = [l for l in st.lines() if l.strip()]
if dirty:
    out.append(f"{len(dirty)} uncommitted change(s) in {repo.safe_relpath(wpath, repo_root)}")
branch = f"along/{slug}"
base = proc.git(["merge-base", "HEAD", branch], cwd=repo_root)
if base.ok:
    changed = [l for l in proc.git(["diff", "--name-only", base.stdout.strip(), branch],
                                   cwd=repo_root).lines() if l.strip()]
    if changed and not proc.git(["diff", "--quiet", "HEAD", branch, "--", *changed],
                                cwd=repo_root).ok:
        out.append(f"branch '{branch}' has changes not in HEAD "
                   f"(run 'along worktree merge {slug}' and commit)")
return out
```
`proc.Result` (verified): `.ok` is a property (`returncode == 0`), `.stdout` is a str,
`.lines()` is used the same way in `list_worktrees`. `git diff --quiet` exits 1 when there
are differences, so `.ok` False means "not merged".
The content check works for squash, ff and normal merges: a file the branch changed
that differs from HEAD means its work is not in HEAD.

## Step 2: guard in `execute_wrap`
Right after the along-team block, same pattern:
```python
wt_blockers = worktree.close_blockers(repo_root, clean_slug)
if wt_blockers and not force_reason:
    _check_failed()
    print("[Error] Wrap aborted: the issue's worktree holds work not in this branch:\n"
          + "\n".join(f"  - {b}" for b in wt_blockers)
          + "\n  Merge it ('along worktree merge <slug>'), commit, or pass --force-reason \"...\".",
          file=sys.stderr)
    return 2
if wt_blockers and not _force_allowed():
    return 2
if wt_blockers:
    forced.append(f"Wrapped with unmerged worktree ({'; '.join(wt_blockers)}): {force_reason}")
```
Follow whatever the neighbouring checks do under `dry_run`; do not add a separate
dry-run branch for this guard.

## Step 3: teardown after a successful wrap
At the end of `execute_wrap`, after the transaction committed and only when
`not dry_run` and the worktree dir exists and `wt_blockers` was empty:
```python
try:
    if worktree.remove_worktree(repo_root, clean_slug):
        print(f"-> Removed worktree .along/worktrees/{clean_slug}")
    else:
        print(f"[Notice] Worktree removal deferred (file locks); run 'along worktree gc' later.")
except OSError as exc:
    print(f"[Notice] Worktree not removed: {exc}. Run 'along worktree remove {clean_slug}'.")
```
A forced wrap (blockers present) KEEPS the worktree and its branch; print one line saying so.

## Step 4: doctor audit (`commands/doctor.py`)
Add `_doctor_worktree_checks(repo_root, warnings) -> int`: for each
`worktree.list_worktrees(repo_root)` entry, `entities.find_issue_by_slug(repo_root, slug)`;
if missing or closed (`done` / status in `entities.CLOSED_ISSUE_STATUSES`), it is a
zombie. Print `[WARN] N dangling worktree(s): a, b. Run 'along worktree remove <slug>'
(or 'along worktree gc').` else nothing. Call it from `handle_doctor_command` next to the
other checks; add its count to `warnings`.

## Step 5: commit notice (`scripts/along_commit.py`)
After the active issue is resolved (around line 99): if
`os.path.isdir(worktree.get_worktree_path(repo_root, slug))` and the process cwd is not
inside that worktree, print:
`[Notice] Issue '<slug>' has a worktree (.along/worktrees/<slug>); this commit goes to the main tree.`
Never block.

## Step 6: tests (`tests/test_worktree.py`, reuse its git fixture and skip guards)
1. dirty worktree -> wrap exits 2, message names the worktree.
2. worktree branch with a commit, not merged -> wrap exits 2.
3. branch squash-merged and committed in main -> wrap succeeds, worktree dir and branch gone.
4. `--force-reason` with an unmerged branch -> wrap succeeds, worktree kept.
5. doctor: worktree whose issue is in `ISSUES/done/` -> WARN line with its slug.
6. `close_blockers` with no worktree -> `[]`.

## Verification
```bash
python .along/scripts/test.py tests/test_worktree.py
```
```bash
python .along/scripts/test.py -q
```
```bash
along sanitize
```

## Out of scope
- Per-step worktrees for along-team (`feat--team-worktree-lifecycle`).
