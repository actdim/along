---
protocol: along
protocol_version: "4.7.0"
slug: optimize-test-suite-execution-time
type: task
status: done
completed: 2026-11-09
priority: medium
created: 2026-11-07
updated: 2026-11-09
agent: antigravity
tags: [testing, performance, pytest, test-runner, dx]
blocked_by: [task--pytest-support-and-test-runner-filtering, task--hermetic-suite-flaky-git-cache]
related: [task--pytest-support-and-test-runner-filtering, task--hermetic-suite-flaky-git-cache]
plan_status: approved
---

# Optimize Test Suite Execution Time: measure, separate integration tests, run in parallel

Make a fast local feedback loop possible without weakening the suite: measure where time goes, give both runners (`.along/scripts/test.py` and pytest) one shared definition of "integration test", add opt-in parallel execution with pytest-xdist that keeps the hermeticity gate meaningful, and share read-only fixtures where proven safe. In-process engine invocation is an optional later phase that requires production entry-point changes.

## Context and Problem Statement

The suite has 115 test files and runs sequentially; a full run takes several minutes on Windows, where process creation and git operations are expensive. Heavy tests (real git repositories, `uv` venv bootstrap, Docker) are not separated from fast unit tests.

Constraints found in the 2026-11-08 review (see [plan.md](./task--optimize-test-suite-execution-time/plan.md)):
- Per-test `@pytest.mark` decorators would make `import pytest` mandatory for the unittest runner. The integration list lives in one pytest-free registry read by both runners.
- Under xdist every worker imports `test_zz_hermetic_suite.py` and takes its own baseline while other workers write; the hermetic test must run serially after the parallel run, against a baseline taken before it.
- `tests/test_skills_and_scripts.py` has 50 `run_engine(` calls; `along_update.py` and `along_dash.py` have no `main()`, so in-process invocation needs production changes.
- No measured baseline exists yet; all time targets are set from Phase 0 data.

## Requirements

- REQ-1 (Baseline): Measure per-module and per-test durations with both runners and record them in this issue before any change; targets for later phases are derived from these numbers.
- REQ-2 (Integration Registry): A pytest-free registry (`tests/_integration.py`) lists integration modules and, where needed, individual test ids. `tests/conftest.py` applies the registered `integration` marker from it; `.along/scripts/test.py --unit` / `--fast` excludes the same set. A test fails if the registry names a module or test that does not exist.
- REQ-3 (Parallel Execution): `pytest-xdist>=3.5.0` in `[dependency-groups] dev`. `.along/scripts/test.py -n <N|auto>` runs the pre-flight syntax gate, takes the hermetic baseline, runs `pytest -n <N> --dist=loadfile -p no:cacheprovider` with `test_zz_hermetic_suite` deselected, then runs the hermetic test serially. Without xdist it falls back to the sequential runner with a notice.
- REQ-4 (Shared Read-Only Fixtures): Tests in `tests/test_skills_and_scripts.py` may share a class-level fixture only when proven read-only (fixture tree hash unchanged at `tearDownClass`).
- REQ-5 (Invariants): No test deleted, skipped by default or weakened; the full sequential run still executes everything; `test_zz_hermetic_suite.py` always runs last and serially; no new files in the repository root.
- REQ-6 (Optional, separate issue): In-process engine invocation, only if Phase 0 data shows process spawn dominates after REQ-2..REQ-4. Engines first get `main(argv=None) -> int`; the helper restores `sys.argv`, cwd, `os.environ`, `sys.path` and engine `sys.modules` entries.
- REQ-7 (ASCII Typography Compliance): `scripts/sanitize_typography.py --check` passes.

## Acceptance Criteria

- [x] Baseline durations recorded in this issue; targets set from them.
- [x] `tests/_integration.py` registry exists; pytest marker and `test.py --unit` both use it; stale-entry test passes.
- [x] `[tool.pytest.ini_options]` registers the `integration` marker.
- [x] `pytest-xdist>=3.5.0` added to `[dependency-groups] dev`; `uv.lock` updated.
- [x] `python .along/scripts/test.py -n auto` passes 3 consecutive runs, with the hermetic test run serially afterwards.
- [x] `python .along/scripts/test.py --unit` and `uv run pytest -m "not integration" -q` run the same set of tests.
- [x] Shared fixtures used only where the read-only check passes.
- [x] Full sequential `python .along/scripts/test.py` passes; test count is unchanged.
- [x] Before/after durations recorded in this issue.
- [x] Repository passes `python scripts/sanitize_typography.py --check`.
