---
protocol: along
protocol_version: "4.7.0"
slug: pytest-support-and-test-runner-filtering
type: task
status: in-progress
priority: medium
created: 2026-11-06
updated: 2026-11-08
agent: antigravity
tags: [testing, pytest, test-runner, dx]
blocked_by: []
related: []
plan_status: approved
---

# Add Pytest Support and Fine-Grained Test Runner Filtering

Enable native Pytest execution and IDE test explorer integration via `conftest.py` / `pyproject.toml`, and enhance `.along/scripts/test.py` with `-k <pattern>` substring filtering, pytest-style target normalization, and zero-test execution safeguards.

## Context and Problem Statement

The repository test suite enforces an intentional runner guard (`ALONG_TEST_RUNNER` environment variable check in `tests/__init__.py` and individual test modules) to prevent unconfigured raw test execution that lacks dependency resolution or the pre-flight syntax gate. While this guard protects against accidental raw runs, it currently prevents developers and IDE test runners (e.g. VS Code, Cursor, PyCharm) from executing tests directly via `pytest`.

Furthermore, `.along/scripts/test.py` currently only accepts full file names or dotted test paths (`test_module.TestClass.test_method`). When developers copy pytest-style test node IDs (e.g. `tests/test_x.py::Class::method` or `test_x.py:Class.method`), `unittest` fails with an `ImportError: ModuleNotFoundError`. Additionally, `.along/scripts/test.py` lacks pattern-based filtering (`-k <pattern>`).

Finally, standard `unittest` reports success when 0 tests are run (such as when a target or pattern is misspelled), returning exit code 0. This creates a silent pass risk in CI and developer workflows that must be guarded against.

## Requirements

- REQ-1 (Pyproject Pytest Configuration): Add `[tool.pytest.ini_options]` to `pyproject.toml` configuring `testpaths = ["tests"]` and `pythonpath = ["scripts"]`.
- REQ-2 (Pytest Runner Guard Bridge): Create `tests/conftest.py` with a `pytest_configure` hook that sets `os.environ["ALONG_TEST_RUNNER"] = "pytest"` and configures `sys.path`. Because `tests` is a package, pytest imports `tests/__init__.py` before `conftest.py`, so the guard in `tests/__init__.py` MUST also accept a running pytest (`pytest` / `_pytest` in `sys.modules`). Raw `python -m unittest` and direct script runs MUST still be rejected; the trade-off (a process that already imported pytest passes) is documented in a guard comment.
- REQ-3 (Pattern Filtering in test.py): Update `.along/scripts/test.py` to support `-k <pattern>` (and `-k=<pattern>`), filtering the discovered test suite by test ID matching the substring.
- REQ-4 (Pytest-Style Path Normalization): Update `.along/scripts/test.py` to parse and normalize arguments like `tests/test_x.py::Class::method`, `tests\test_x.py::Class::method`, or `test_x.py:Class.method` into dotted names (`test_x.Class.method`) for `unittest.TestLoader.loadTestsFromName`.
- REQ-5 (Zero-Test Safeguards): Ensure that if zero tests are executed or collected (e.g. due to unmatched filters or invalid target names), `.along/scripts/test.py` fails with a non-zero exit code (matching Pytest exit code 5 behavior).
- REQ-5a (No Silent Drop Under -k): `-k` filtering MUST keep `unittest.loader._FailedTest` entries, so a module that fails to import reports its import error instead of "No tests collected".
- REQ-5b (Documentation): `docs/topic--setup-and-workflow.md` lists `test.py -k`, pytest-style selectors and `uv run pytest`.
- REQ-6 (ASCII Typography Compliance): Ensure all created and modified files pass `scripts/sanitize_typography.py --check` with zero non-ASCII characters.

## Acceptance Criteria

- [x] `[tool.pytest.ini_options]` added to `pyproject.toml`.
- [x] `tests/conftest.py` created with `pytest_configure` setting `ALONG_TEST_RUNNER=pytest`; `tests/__init__.py` guard accepts a running pytest.
- [x] Running tests via `pytest` satisfies the runner guard and discovers tests (`uv run pytest -q tests/test_cli_chdir.py`: 7 passed).
- [x] `.along/scripts/test.py -k <pattern>` filters and executes only matching tests.
- [x] `.along/scripts/test.py tests/test_x.py::Class::method` normalizes the target (`tests/test_cli_chdir.py::TestCliChdir`: 7 OK).
- [x] `.along/scripts/test.py` exits with non-zero code when zero tests match or execute (`-k nonexistent_xyz_123`: exit 1).
- [x] Automated tests verify filtering, target normalization, and zero-test safeguards (`test_test_runner.py`: 17 OK).
- [x] `-k` keeps `_FailedTest` import errors (REQ-5a), with a test.
- [x] Guard trade-off comment and setup doc note (REQ-2, REQ-5b).
- [x] `python -m unittest discover -s tests` still exits with the guard message.
- [x] Full suite passes; repository passes `python scripts/sanitize_typography.py --check`.
