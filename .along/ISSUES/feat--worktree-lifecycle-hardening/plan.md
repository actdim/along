# Living Plan: Harden Git Worktree Lifecycle: Wrap Guards, Doctor Audits, and Commit Checks

## Execution Mode
Direct

## 1. Context & Technical Scrutiny

Along provides Git worktree isolation (`scripts/alongkit/worktree.py`) to run tests and mutations in an isolated directory (`.along/worktrees/<slug>`). While low-level provisioning, junction linking, and branch management are implemented, the lifecycle hooks in `along wrap`, `along doctor`, and `along commit` currently operate completely unaware of active worktrees.

### Critical Failure Modes Addressed
1. **Silent Code Loss at Closeout**: A developer starts an issue with `along start <slug> --worktree`, writes code and commits to the `along/<slug>` worktree branch, but calls `along wrap <slug>` from the root repository directory. Because `along wrap` currently only checks the root directory, it marks the issue as `done`, archives it to `.along/ISSUES/done/`, and leaves the worktree changes unmerged and forgotten.
2. **Disk Bloat & Lock Exhaustion**: Worktrees link dependency trees (`node_modules`, `.venv`) via NTFS junctions or symlinks. When worktrees are not cleaned up on issue closeout, tens of gigabytes of disk space and dormant filesystem locks accumulate.
3. **Branch Divergence**: Committing directly in the root while a worktree branch is in-flight causes diverged Git histories when the worktree is eventually merged.

---

## 2. Requirements & Traceability

- **REQ-1 (Wrap Unmerged Changes Guard)**: In `scripts/alongkit/lifecycle.py` (`execute_wrap`), check `worktree.get_worktree_path(repo_root, slug)`. If the path exists:
  - Run `git status --porcelain` inside the worktree path. If dirty, abort with error unless `--force-reason` is provided.
  - Check if the worktree branch contains commits not in the current HEAD (`git rev-list <current_branch>..along/<slug>`). If unmerged commits exist, abort with instructions to run `along worktree merge <slug>`.
- **REQ-2 (Wrap Automated Teardown)**: In `scripts/alongkit/lifecycle.py`, once pre-wrap checks pass and mutations succeed, invoke `worktree.remove_worktree(repo_root, slug, force=True, delete_branch=True)`. If deferred due to Windows file locks, notify the user.
- **REQ-3 (Doctor Dangling Worktree Audit)**: In `scripts/alongkit/commands/doctor.py`, query `worktree.list_worktrees(repo_root)`. Cross-reference each worktree's slug with `.along/ISSUES/done/`. Flag any worktree associated with a closed issue or merged branch as a zombie worktree.
- **REQ-4 (Commit Divergence Check)**: In `scripts/along_commit.py`, detect if the current active issue bound to the session has an active worktree. If so, emit an informational warning to ensure the user intends to commit in root.
- **REQ-5 (ASCII Typography and Hermetic Tests)**: Implement hermetic test cases in `tests/test_worktree.py` verifying wrap guards and doctor audits. Pass `python scripts/sanitize_typography.py --check`.

---

## 3. Step-by-Step Implementation Changes

### Step 1: Worktree Verification Helper in `scripts/alongkit/worktree.py`
Add `inspect_worktree_readiness(repo_root: str, slug: str) -> Tuple[bool, str]`:
- Returns `(is_ready_to_close, reason)`.
- Checks:
  1. Worktree existence on disk.
  2. Uncommitted modifications (`git status --porcelain`).
  3. Unmerged commits relative to parent branch (`git rev-list parent..along/<slug>`).

### Step 2: Integrate Worktree Guards into `scripts/alongkit/lifecycle.py`
- In `execute_wrap`:
  - Before modifying issue frontmatter, call `inspect_worktree_readiness`.
  - If unready and not `force_reason`, fail transaction with a descriptive error.
  - After issue relocation and transaction completion, call `remove_worktree(repo_root, slug)`.

### Step 3: Integrate Zombie Worktree Audits into `scripts/alongkit/commands/doctor.py`
- Add worktree audit step in `doctor.py`:
  - Call `list_worktrees(repo_root)`.
  - For each worktree, check if `issue_file` is located in `done/` or does not exist.
  - If zombies found, print warning: `[WARN] Found <N> dangling worktree(s). Run 'along worktree gc' to prune.`

### Step 4: Add Divergence Warning to `scripts/along_commit.py`
- When binding session names an active slug, check if `os.path.isdir(get_worktree_path(repo_root, slug))`.
- If committing from root, display: `[Notice] Active worktree exists for '<slug>'. Ensure edits were intended in root.`

---

## 4. Verification Plan

### Automated Test Cases
1. Create a hermetic repo fixture with a worktree having uncommitted files.
   - Run `along wrap <slug> --no-decisions`.
   - Verify exit status != 0 and error message citing dirty worktree.
2. Create a hermetic repo fixture with a worktree having unmerged commits on its branch.
   - Run `along wrap <slug> --no-decisions`.
   - Verify exit status != 0 and error message citing unmerged branch commits.
3. Create a clean, merged worktree for `<slug>`.
   - Run `along wrap <slug> --no-decisions`.
   - Verify issue moves to `done/` and worktree directory is deleted from disk.
4. Run `along doctor` on a repo with a closed issue's worktree:
   - Verify `along doctor` flags the zombie worktree and `along worktree gc` cleans it.
