# Plan: along lint <paths...> (mostly done; verify, fix one gap, close)

## Execution Mode
Direct

Target executor: a fast model. Small task.

## Facts verified in code
Already shipped in commit `43986c5` (`lint-worktree-and-doctor-subprojects`):
- `along lint [--worktree] [paths...]` -> `handle_gates_command(["check", ...])`
  (`scripts/alongkit/commands/gates.py`, `handle_lint_command`); help text documents paths.
- `gitgates.check_files(repo_root, paths)` runs the content gates on files or directories,
  staged or not. Tests: `tests/test_lint_unstaged.py`.
- No paths -> staged changes (REQ-2 met). argparse usage errors exit 2, findings exit 1,
  clean exit 0 (REQ-3 met).

Remaining gap: a path that does not exist is silently dropped in `check_files`, so
`along lint typo.md` prints a clean report and exits 0.

## Step 1: missing paths are a usage error
In `handle_gates_command`, branch `elif opts.hook_args:` (paths mode), before calling
`check_files`:
```python
missing = [p for p in opts.hook_args
           if not os.path.exists(p if os.path.isabs(p) else os.path.join(repo_root, p))]
if missing:
    print(f"[Error] Path(s) not found: {', '.join(missing)}", file=sys.stderr)
    return 2
```
Relative paths: check against both the process cwd and `repo_root` (a path given from a
subfolder): treat as missing only when neither exists. If `check_files` resolves only
against `repo_root`, pass `os.path.abspath(p)` for paths that exist relative to the cwd.

## Step 2: tests (`tests/test_lint_unstaged.py`)
1. `test_lint_reports_non_ascii_in_unstaged_issue_plan`: write
   `.along/ISSUES/x/plans/01--y.md` containing an em dash (build it with `chr(0x2014)`,
   never a literal); `along lint <that path>` exits 1 and names the file.
2. `test_lint_missing_path_exits_2`.

## Step 3: close
Tick the acceptance criteria in the ticket and wrap with `--no-decisions`.

## Verification
```bash
python .along/scripts/test.py tests/test_lint_unstaged.py
```
