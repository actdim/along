# Living Plan: Fix worktree-env-readiness False Positives on Git Submodules & Recovery Deadlocks

## Execution Mode
Direct

## 1. Context & Technical Scrutiny
In ALONG-PROTOCOL 4.5.4 on Windows, an agent session operating in a Git submodule faced immediate execution deadlocks:
1. `worktree-env-readiness` gate blindly classified the submodule as a Git worktree because submodules carry a `.git` file beginning with `gitdir:`.
2. The gate checked `os.getcwd()` rather than the target file path, denying file writes even for files outside the submodule (e.g., superproject `.along/ISSUES/`).
3. The gate intercepted shell commands without evaluating leading directory changes (e.g., `cd`), denying `along gates ack`, `along doctor`, `along gates stats`, `along plan status`, and plain `cd`. This made it impossible to satisfy the `unresolved-gate-denial` Stop gate.
4. For nested subprojects and monorepo workspaces (pnpm/npm workspaces), parent `node_modules` was not recognized.
5. Error messages erroneously suggested running `along worktree create` inside an existing submodule.

### Technical Boundaries & Invariants
- **Gate Scope**: A Git submodule is an independent checkout, not a Git worktree. `worktree-env-readiness` exists solely to enforce the Environment Readiness Contract on isolated Git worktrees. It must never fire for submodules.
- **Hermetic Metadata Inspection**: Git repository topology must be inspected via filesystem parsing of `.git` metadata (`gitdir:`, `commondir`, and path segments), avoiding `git` subprocess overhead on every PreToolUse event.
- **Anti-Deadlock Invariant**: Along recovery, diagnostic, governance commands, and directory navigation (`cd`, `pwd`, `dir`) must never be denied by readiness checks.

---

## 2. Requirements & Traceability
- **REQ-1 (Worktree vs Submodule Separation)**: `worktree-env-readiness` gate and `is_worktree` predicate MUST distinguish Git worktrees from Git submodules using Git metadata (`worktrees/` directory segment in gitdir target, `commondir` pointer). Submodules MUST NOT trigger worktree environment readiness denials.
- **REQ-2 (Target Path & CD Evaluation)**: `worktree-env-readiness` gate MUST evaluate target paths for file modification tools and effective working directory after leading directory changes (e.g., `cd`) for shell commands, rather than solely inspecting session cwd.
- **REQ-3 (Recovery & Navigation Whitelist)**: `worktree-env-readiness` gate MUST NEVER deny Along recovery, diagnostic, and governance commands (`along gates ack`, `along gates stats`, `along gates denials`, `along doctor`, `along plan status`, `along status`, `along gates check`) or directory navigation commands (`cd`, `pwd`), preventing deadlocks with `unresolved-gate-denial`.
- **REQ-4 (Workspace Dependency Resolution)**: For nested Along subprojects or workspaces, `worktree-env-readiness` MUST treat `node_modules` as satisfied if present in the subproject itself or in an ancestor workspace root (e.g., `pnpm-workspace.yaml`, `package.json` workspaces).
- **REQ-5 (Actionable Violation Messages)**: When a readiness violation occurs, the diagnostic message MUST specify the detected Git worktree path, gitdir target, primary repository, and actionable fix (`mklink /J` or `ln -s`), never suggesting `along worktree create` for existing checkouts.

---

## 3. Step-by-Step Implementation Changes

### Step 1: Git Metadata Inspection in `scripts/alongkit/worktree.py`
1. Implement `inspect_git_dir(path: str) -> Dict[str, Any]`:
   - Inspects `.git`:
     - If directory: `{"kind": "repo", "git_dir": path, "primary_repo": path}`
     - If not file: `{"kind": "none"}`
     - If file with `gitdir: <target>`:
       - Resolve target path (absolute or relative to `path`).
       - Check for `commondir` file or `worktrees` in path segments.
       - If `commondir` exists or `worktrees` in parts:
         - Resolve `primary_repo` from `commondir` target or parent of `.git/worktrees/`.
         - Return `{"kind": "worktree", "gitdir": target, "primary_repo": primary_repo, "has_commondir": ...}`
       - If `modules` in parts without `worktrees`:
         - Return `{"kind": "submodule", "gitdir": target, "primary_repo": None}`
       - Otherwise return `{"kind": "secondary", "gitdir": target}`
2. Update `is_worktree(path: str) -> bool`:
   - Return `True` only when `inspect_git_dir(path).get("kind") == "worktree"`.
3. Add `is_submodule(path: str) -> bool`:
   - Return `True` when `inspect_git_dir(path).get("kind") == "submodule"`.

### Step 2: Predicate Refactoring in `scripts/alongkit/hooks/predicates.py`
1. Update `check_worktree_env_readiness(event: HookEvent, repo_root: str, **kwargs: Any) -> Optional[str]`:
   - **Target Path Resolution for File Tools**:
     - Extract `target = _extract_target_file(event)`.
     - If target path present:
       - Resolve absolute path.
       - Traverse directory ancestors to locate enclosing directory with `.git`.
       - If enclosing directory is NOT a Git worktree (`not worktree.is_worktree(enclosing)`), return `None`.
       - Set `check_dir = enclosing`.
   - **Shell Command Handling**:
     - Extract command string.
     - Whitelist recovery and diagnostic commands:
       - Match `along gates (ack|stats|denials|check)`, `along doctor`, `along plan status`, `along status`, `along --help`, `along help`.
       - Return `None` immediately if matched.
     - Parse directory navigation:
       - Use `shellparse.split_segments` and `shellparse.words`.
       - If command consists solely of navigation (`cd`, `chdir`, `pushd`, `set-location`, `sl`, `pwd`, `dir`, `ls`, `get-location`), return `None`.
       - If leading segment changes directory (`cd <dir> && ...`), compute effective working directory.
       - Traverse ancestors of effective directory for enclosing `.git`.
       - If enclosing directory is NOT a Git worktree, return `None`.
       - Set `check_dir = enclosing`.
   - **Workspace Dependency Traversal**:
     - For detected Git worktree `check_dir`:
       - If `node_modules` exists or is linked at `check_dir`, satisfied.
       - Else, traverse parent directories up to workspace root (indicated by `pnpm-workspace.yaml`, `package.json` with workspaces, `lerna.json`, or primary repository root) looking for `node_modules`.
       - If found in ancestor workspace root, satisfied.
   - **Diagnostic Message Construction**:
     - Format violation to include:
       - Detected worktree directory.
       - Gitdir pointer.
       - Primary repository path.
       - Specific missing dependency (`node_modules` or `.venv`).
       - Actionable remediation advice (`mklink /J` on Windows or `ln -s` on POSIX).

### Step 3: Comprehensive Hermetic Tests in `tests/test_worktree.py`
Add tests to verify:
1. `test_14_submodule_not_classified_as_worktree`: Submodule `.git` with `gitdir: .../modules/...` returns `is_worktree() == False` and `is_submodule() == True`, and `check_worktree_env_readiness` returns `None`.
2. `test_15_target_path_evaluation_outside_worktree`: Modifying a file outside an unlinked worktree (such as superproject issues) is permitted even when cwd is in the worktree.
3. `test_16_recovery_commands_and_cd_allowed`: Running `along gates ack`, `along doctor`, `along plan status`, and `cd` in an unlinked worktree is never denied.
4. `test_17_workspace_root_node_modules_satisfies_nested_worktree`: Ancestor workspace with `pnpm-workspace.yaml` and `node_modules` satisfies readiness for nested subprojects.
5. `test_18_violation_message_diagnostics`: Worktree violation message identifies worktree path, gitdir, primary repo, and junction linking remediation.

---

## 4. Verification Plan
1. Run hermetic tests: `python .along/scripts/test.py tests/test_worktree.py`.
2. Run full repository diagnostics: `along doctor`.
3. Check typography and clean ASCII formatting: `along sanitize`.
