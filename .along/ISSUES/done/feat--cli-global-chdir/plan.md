# Living Plan: Global -C <dir> Option for Along CLI

## Execution Mode
Direct

## 1. Context & Technical Scrutiny
In multi-package monorepos and repositories with Git submodules, each subproject carries its own `.along/` context and lifecycle hooks. Currently, `scripts/along_exec.py` assumes `os.getcwd()` is the target repository root. When an agent wants to run an Along command in a submodule (e.g. `src/packages/ui-core`), it executes `(cd src/packages/ui-core && along ...)`.

This pattern causes friction:
1. Shell command string analysis in runtime hooks can fail or misclassify directory switches.
2. Hook containment checks can evaluate session cwd rather than the target subproject directory.
3. Windows PowerShell subshell handling differs from POSIX subshells.

Adding `along -C <dir> <command>...` mirrors `git -C <dir>` and allows direct, clean targeting of nested contexts without changing the agent shell working directory.

### Technical Boundaries & Invariants
- Flag position: `-C <dir>` or `--chdir <dir>` must be accepted anywhere before the primary subcommand name.
- Repetitions: Sequential `-C` calls accumulate relative changes (`along -C src -C packages/ui-core ...` -> `src/packages/ui-core`).
- Exit codes: A non-existent directory must fail with exit code 2 before any subsystem or gate loads.
- Subprocess isolation: When `along_exec.py` invokes sub-engines (`along_wrap.py`, `along_kb_sync.py`, etc.) or lifecycle scripts (`test.py`, `build.py`), the `cwd` argument must point to the target context.

---

## 2. Requirements & Traceability
- **REQ-1 (CLI Argument Parsing)**: Pre-parse `sys.argv` in `scripts/along_exec.py` to extract leading `-C` and `--chdir` arguments.
- **REQ-2 (Directory Validation & Chdir)**: Validate target directory existence, resolve absolute path, and call `os.chdir(target_dir)` before `find_repo_root()`.
- **REQ-3 (Error Handling)**: Produce a clear error message on stderr and exit code 2 when target directory does not exist.
- **REQ-4 (Help Preservation)**: Ensure `along -C <dir> --help` and `along --help` display help cleanly.
- **REQ-5 (Automated Tests)**: Hermetic unit tests in `tests/test_cli_chdir.py` testing single, multiple, and invalid `-C` options across different subcommands.

---

## 3. Step-by-Step Implementation Changes

### Step 1: Pre-parser in `scripts/along_exec.py`
1. Implement `_extract_global_chdir_options(argv: List[str]) -> Tuple[str, List[str]]`:
   - Iterate through `argv[1:]`.
   - When encountering `-C` or `--chdir`:
     - Pop flag and directory argument.
     - Accumulate path: `current_target = os.path.normpath(os.path.join(current_target, arg))`.
   - When encountering an option starting with `-` that is not `-C`/`--chdir`:
     - Stop or continue based on whether it is a global flag (e.g. `--help`).
   - Stop when the subcommand name is encountered.
2. If accumulated path differs from current working directory:
   - Check `os.path.isdir(accumulated_path)`.
   - If false, print `[Error] Target directory does not exist: <accumulated_path>` to `sys.stderr` and exit with code 2.
   - Perform `os.chdir(accumulated_path)`.
3. Re-assign remaining arguments to `sys.argv[1:]` for standard router dispatch.

### Step 2: Context Root Resolution
1. Verify that `repo_root = find_repo_root()` correctly discovers the nearest `.along/` from the new `os.getcwd()`.
2. Confirm that commands delegating to external scripts (`TOOL_MAPPINGS`, lifecycle scripts) pass the new `cwd=repo_root` to `proc.run_passthrough()`.

### Step 3: Wrapper Script Alignment
1. Verify that `scripts/along` (bash) and `scripts/along.cmd` / `scripts/along.ps1` (Windows) pass all arguments verbatim via `"$@"` / `"%*"` / `$args`.

### Step 4: Hermetic Tests in `tests/test_cli_chdir.py`
1. Create a temporary repository structure with root `.along/` and nested `subproject/.along/`.
2. Test `along -C subproject status`: resolves subproject issues and milestones.
3. Test `along -C subproject issue list`: lists issues in subproject.
4. Test `along -C nonexistent status`: exits with code 2 and error message.
5. Test chaining: `along -C parent -C child status`.

---

## 4. Verification Plan
1. Run hermetic tests: `python .along/scripts/test.py tests/test_cli_chdir.py`.
2. Manual verification: run `along -C packages/dashboard-ui status` from repo root.
3. Typography check: `along sanitize`.
