# Living Plan: Refactor _handle_chdir_options into a dependency-free argv module

## Execution Mode
Direct (3 files: one new module, two import edits).

## Revision note (2026-11-08 review)
The previous revision moved `_handle_chdir_options` into `scripts/alongkit/commands/common.py`.
That target is unsafe: importing `alongkit.commands.common` executes
`scripts/alongkit/commands/__init__.py`, which imports every command router
(`issue.py` pulls `entities`, `frontmatter`, `gates`, `lifecycle`, `session`, `transaction`).
`scripts/alongkit/cli.py` is the thin `along` console launcher: it imports only `repo` and
`version`, runs before `bootstrap.ensure_deps()` (which lives in `along_exec.py`), and serves
`along --version` / `along -C <dir>`. Pulling the whole router tree into it would slow every
launch and can fail with an ImportError before dependencies are bootstrapped.

The "inverted dependency" argument is also weaker than stated: both `cli.py` and
`along_exec.py` import from inside `alongkit`. The concrete defects are (a) the duplicate import
at `scripts/along_exec.py:47` and (b) a CLI argv helper living in the launcher module.

Issue REQ-1 / REQ-2 / REQ-3 originally named `commands/common.py` as the destination; they were
amended (2026-11-08) to name `scripts/alongkit/cliargs.py`.

## 1. Facts (verified 2026-11-08)
- `_handle_chdir_options` is defined at `scripts/alongkit/cli.py:39-65` and used at `cli.py:72`.
- `scripts/along_exec.py` imports it at lines 19 and 47 (identical lines) and calls it at 252.
- No test imports `_handle_chdir_options` directly; `tests/test_cli_chdir.py` and
  `tests/test_rules.py` go through `alongkit.cli.main`.
- `TestNoDuplicateHelpers` (`tests/test_alongkit.py:679`) forbids engines (`scripts/*.py`) from
  redefining package helpers; a package-internal module is fine.
- No `scripts/alongkit/cliargs.py` exists today.

## 2. Boundaries & Invariants
- Signature and behavior unchanged: `(args: List[str]) -> Tuple[Optional[str], List[str]]`,
  attached and spaced `-C` / `--chdir` forms, chained `-C a -C b`, missing argument prints to
  stderr and exits 2.
- `cliargs.py` imports only the standard library (`os`, `sys`, `typing`). It must never import
  `alongkit.commands` or anything that needs `ruamel.yaml`.
- `cli.py` keeps working both as a package module and when executed as a script.
- Keep a name binding `alongkit.cli._handle_chdir_options` (via the import) so external callers
  that reached into the old location do not break.

## 3. Steps
1. Create `scripts/alongkit/cliargs.py` with the library-module guard used across `alongkit`
   (`if __name__ == "__main__": raise SystemExit(...)`), a module docstring, and the function body
   moved verbatim from `cli.py`.
2. `scripts/alongkit/cli.py`: delete the local definition; import it in both branches:
   script branch `from alongkit.cliargs import _handle_chdir_options`, package branch
   `from .cliargs import _handle_chdir_options`. Drop `Tuple` from the typing import if unused.
3. `scripts/along_exec.py`: replace line 19 with `from alongkit.cliargs import _handle_chdir_options`
   and delete the duplicate at line 47.
4. Optional, same commit: add a test in `tests/test_cli_chdir.py` asserting that importing
   `alongkit.cli` does not load `alongkit.commands` (check `sys.modules` in a subprocess), so the
   launcher stays light.

## 4. Verification
- `python .along/scripts/test.py test_alongkit.py test_cli_chdir.py test_rules.py`
- `along -C packages/dashboard-ui status` and `python scripts/along_exec.py -C packages/dashboard-ui status`
  return 0 with the subproject context.
- `along --version` still works.
- `along sanitize` clean.

## 5. Sequencing
Land before `task--domain-exceptions-and-error-flow`, which edits `cli.py`, `along_exec.py`
and `commands/common.py`.
