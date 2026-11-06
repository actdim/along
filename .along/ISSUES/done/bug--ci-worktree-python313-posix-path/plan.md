# Living Plan: Fix Worktree inspect_git_dir POSIX Path Handling on Windows in Python 3.13

## Execution Mode
Direct

## 1. Context & Root Cause Analysis
In Python 3.13 on Windows, `os.path.isabs` was updated to adhere strictly to Windows semantics: paths starting with a single slash (such as `/var/repos/main` or `\var\repos`) without a drive letter are treated as drive-relative, not absolute (`os.path.isabs` returns `False`).

In `scripts/alongkit/worktree.py`:
- `gitdir = raw_target if os.path.isabs(raw_target) else os.path.normpath(os.path.join(path, raw_target))`
- `c_dir = c_content if os.path.isabs(c_content) else os.path.normpath(os.path.join(gitdir, c_content))`

Because `os.path.isabs(raw_target)` returns `False` under Python 3.13 on Windows for `/var/repos/main/...`, `os.path.join(path, raw_target)` is invoked, attaching the Windows working drive (e.g. `C:`) and converting forward slashes to backslashes (`C:\var\repos\main...`). This causes `test_19_posix_path_preservation_in_inspect_git_dir` to fail with `AssertionError: 'C:\\var\\repos\\main' != '/var/repos/main'`.

Similarly, in `scripts/alongkit/proc.py` line 256:
- `find_git_dir` checks `if not os.path.isabs(gdir):` when reading `.git` gitdir pointers.

## 2. Requirements & Traceability
- **REQ-1 (Worktree gitdir & commondir preservation)**: `inspect_git_dir` in `scripts/alongkit/worktree.py` MUST treat paths starting with `/` or `\` as rooted/absolute targets across all Python versions, preventing unintended concatenation with the local repository path and drive letter.
- **REQ-2 (Process find_git_dir preservation)**: `find_git_dir` in `scripts/alongkit/proc.py` MUST also recognize rooted paths (`p.startswith(("/", "\\"))`) as absolute.
- **REQ-3 (Hermetic Cross-Version Verification)**: `tests/test_worktree.py` and the full test suite MUST pass under Python 3.13 and Python 3.12 on Windows.

## 3. Step-by-Step Changes

### Step 1: Update `scripts/alongkit/worktree.py`
In `inspect_git_dir`:
- Check `is_abs = os.path.isabs(raw_target) or raw_target.startswith(("/", "\\"))` before joining with `path`.
- For `c_dir`, check `c_is_abs = os.path.isabs(c_content) or c_content.startswith(("/", "\\"))` before joining with `gitdir`.

### Step 2: Update `scripts/alongkit/proc.py`
In `find_git_dir`:
- Check `if not (os.path.isabs(gdir) or gdir.startswith(("/", "\\"))):` before joining with `cur`.

### Step 3: Run Verification
- Run `uv run --python 3.13 python .along/scripts/test.py tests/test_worktree.py`.
- Run `uv run --python 3.12 python .along/scripts/test.py tests/test_worktree.py`.
- Run `python scripts/along_exec.py sanitize`.

---

## 4. Verification Plan
1. Single test execution: `uv run --python 3.13 python .along/scripts/test.py tests/test_worktree.py`
2. Full suite run or gate check.
3. Typography check via `along sanitize`.
