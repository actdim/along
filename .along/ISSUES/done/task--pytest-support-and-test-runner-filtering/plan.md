# Living Plan: Pytest Support and Fine-Grained Test Runner Filtering

## Execution Mode
Direct

## Status (2026-11-08 review)
Implemented in the working tree, not yet committed or wrapped. Verified:
- `python .along/scripts/test.py -q -k nonexistent_xyz_123` -> exit 1,
  `[Error] No tests collected matching the specified arguments or pattern.`
- `python .along/scripts/test.py -q test_test_runner.py` -> 16 tests OK.
- `python .along/scripts/test.py -q tests/test_cli_chdir.py::TestCliChdir` -> 7 tests OK.
- `uv run pytest -q tests/test_cli_chdir.py` -> 7 passed.

Remaining work: steps 5-7 below, then the completion checklist.

## 1. Deviation from the original plan (accepted)
The original plan claimed `tests/conftest.py` alone satisfies the `ALONG_TEST_RUNNER` guard and
that `tests/__init__.py` stays untouched. That cannot work: `tests` is a package, so pytest
imports `tests/__init__.py` before `tests/conftest.py`. The implementation therefore relaxes the
guard in `tests/__init__.py`: when `pytest` or `_pytest` is already in `sys.modules`, it sets
`ALONG_TEST_RUNNER=pytest` instead of exiting. Raw `python -m unittest` and direct script runs
are still rejected.

Known trade-off: any process that has already imported pytest passes the guard. Acceptable;
record it in the guard comment.

## 2. Implemented changes
- `pyproject.toml`: `[tool.pytest.ini_options]` (`testpaths = ["tests"]`, `pythonpath = ["scripts"]`)
  and `pytest>=7.0.0` in `[dependency-groups] dev`; `uv.lock` updated.
- `tests/__init__.py`: guard accepts a running pytest (see section 1).
- `tests/conftest.py`: sets `ALONG_TEST_RUNNER`, adds repo root, `tests/` and `scripts/` to
  `sys.path`, clears `session.SESSION_ENV_VARS` in `pytest_configure`.
- `.along/scripts/test.py`: `_normalize_test_target` (`path::Class::method`, `file.py:Class.method`,
  backslashes), `_filter_suite_by_pattern` (`-k <p>`, `-k=<p>`, `-k<p>`), zero-collected and
  zero-executed safeguards (exit 1).
- `tests/test_test_runner.py`: 16 tests for normalization, filtering and safeguards.

## 3. Remaining steps
5. Fix the silent-drop edge: `_filter_suite_by_pattern` currently filters out
   `unittest.loader._FailedTest` entries, so a module that fails to import disappears under `-k`
   and the run reports "No tests collected" instead of the import error. Keep `_FailedTest`
   instances regardless of the pattern; add a test.
6. Add the guard trade-off comment in `tests/__init__.py`; add a short "Running tests" note to
   the setup/workflow doc (`docs/topic--setup-and-workflow.md`) listing `test.py -k`,
   pytest-style selectors and `uv run pytest`.
7. Issue text amended (2026-11-08): REQ-2 covers the `tests/__init__.py` change.

## 4. Verification
- `python .along/scripts/test.py -q test_test_runner.py`
- `python .along/scripts/test.py -q -k test_chdir_chained`
- `uv run pytest -q tests/test_cli_chdir.py`
- `python -m unittest discover -s tests` still exits with the guard message.
- Full `python .along/scripts/test.py` (includes `test_zz_hermetic_suite.py`).
- `python scripts/sanitize_typography.py --check`

## 5. Close-out
`/along-commit` bound to `pytest-support-and-test-runner-filtering`, then
`along wrap pytest-support-and-test-runner-filtering --summary "..." --no-decisions`.
Land before `task--hermetic-suite-flaky-git-cache` and `task--optimize-test-suite-execution-time`
(shared files: `test.py`, `conftest.py`, `pyproject.toml`).
