# Living Plan: Verify and Harden Worktree Environment Readiness

## Execution Mode
Direct

## 1. Context & Identified Edge Cases
During code inspection of the `worktree-env-readiness` implementation, three latent edge cases were identified:
1. **POSIX Path Stripping in `inspect_git_dir`**:
   `parts = [p for p in norm_gitdir.split("/") if p]` stripped empty elements. When reconstructing `common_git = os.sep.join(parts[:idx])` on POSIX systems where paths start with `/`, the leading `/` was lost, producing an invalid relative path (e.g. `home/user/...` instead of `/home/user/...`).
2. **Workspace Root Detection for Immediate Children**:
   `_has_workspace_node_modules` started ancestor traversal from `os.path.dirname(os.path.dirname(primary_repo))` or skipped `primary_repo`'s direct parent if the hierarchy was shallow. It should start checking from `os.path.dirname(os.path.abspath(primary_repo))` upwards using a dedicated `_is_workspace_root` helper.
3. **Python Flags in Recovery Commands**:
   `_is_recovery_command` assumed the script was always `words[1]`. If Python was called with flags (e.g., `python -u scripts/along_exec.py ...` or `python -B ...`), flags were not skipped, causing `_is_recovery_command` to miss the command.

---

## 2. Requirements & Traceability
- **REQ-1 (POSIX Path Integrity)**: `inspect_git_dir` MUST use index slicing of `norm_gitdir` rather than `split("/")` joined without leading slash, ensuring leading `/` is preserved on POSIX systems.
- **REQ-2 (Monorepo Workspace Ancestor Traversal)**: `_has_workspace_node_modules` MUST check from the direct parent of `primary_repo` upwards for workspace root markers (`pnpm-workspace.yaml`, `package.json` with `workspaces`, `lerna.json`), correctly resolving hoisted `node_modules` for immediate child packages.
- **REQ-3 (Interpreter Flag Tolerance)**: `_is_recovery_command` MUST skip arbitrary command-line flags before identifying the script name.
- **REQ-4 (Hermetic Regression Suite)**: Tests in `tests/test_worktree.py` MUST verify all three edge cases.

---

## 3. Step-by-Step Changes

### Step 1: Fix `inspect_git_dir` in `scripts/alongkit/worktree.py`
Use `idx = norm_gitdir.rfind("/worktrees/")` to extract `common_git = gitdir[:idx]` preserving drive letters and leading slashes.

### Step 2: Harden `_has_workspace_node_modules` and `_is_recovery_command` in `scripts/alongkit/hooks/predicates.py`
1. Add `_is_workspace_root(dir)` helper.
2. Traverse from `os.path.dirname(os.path.abspath(primary_repo))` upwards.
3. Update `_is_recovery_command` loop to skip flags like `-u`, `-B`.

### Step 3: Add Regression Tests in `tests/test_worktree.py`
1. `test_19_posix_path_preservation_in_inspect_git_dir`: simulate POSIX `/var/repos/main/.git/worktrees/wt` path and verify `primary_repo == "/var/repos/main"`.
2. `test_20_recovery_command_with_python_flags`: verify `python -u scripts/along_exec.py gates ack` is recognized.
3. `test_21_immediate_child_workspace_detection`: verify a subproject directly in `packages/core` resolves `node_modules` from workspace root.

---

## 4. Verification Plan
1. Run `python .along/scripts/test.py tests/test_worktree.py`.
2. Run `along sanitize`.
3. Wrap and commit under `verify-worktree-env-readiness-hardening`.
