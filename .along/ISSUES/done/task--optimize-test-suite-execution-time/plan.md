# Living Plan: Optimize Test Suite Execution Time

## Execution Mode
Role-Based (`along-team`): the work spans test infrastructure, ~12 test modules and, in phase 4,
production engine entry points. Each phase below is a separate commit and can be a separate issue.

## Revision note (2026-11-08 review)
Corrections to the previous revision:
- Wrong test names: `test_09` is `test_09_installer_artifact_parity`, `test_17` is
  `test_17_link_integrity_gate` (not `along_exec_commands` / `along_kb_sync_options`).
- `tests/test_skills_and_scripts.py` has 50 `run_engine(` calls, not "over 60".
- `scripts/along_update.py` and `scripts/along_dash.py` define no `main()`; their logic runs under
  `if __name__ == "__main__":`. In-process invocation therefore needs a production refactor and
  cannot be a test-only change.
- Decorating test modules with `@pytest.mark` makes `import pytest` mandatory for the unittest
  runner (`.along/scripts/test.py`). Markers move to one central registry instead.
- Under pytest-xdist each worker imports `test_zz_hermetic_suite.py` and takes its own BASELINE
  while other workers keep writing; `test_zz` would run concurrently with the suite and its
  verdict would be meaningless. A `serial` marker does nothing in xdist by itself.
- All speed targets (`< 15-20s`, `< 4s`) were unmeasured. Phase 0 measures first.

Prerequisites: `task--pytest-support-and-test-runner-filtering` wrapped,
`task--hermetic-suite-flaky-git-cache` landed.

## Phase 0: Measure (no code changes)
1. `uv run pytest -q --durations=40 -p no:randomly` and `python .along/scripts/test.py --slowest=40`.
2. Record per-module totals, the top 40 tests, and how many tests spawn `git` / `uv` / docker /
   `sys.executable` children (grep `run_capture`, `subprocess`, `run_engine`).
3. Write the numbers into the issue as the baseline. Set targets from them; drop targets that the
   data does not support.

## Phase 1: Integration registry (single source of truth)
1. Add `tests/_integration.py` (no pytest import) with
   `INTEGRATION_MODULES: frozenset[str]` and optional `INTEGRATION_TESTS` (dotted ids) for
   modules where only some tests are heavy. Seed it from the Phase 0 data; candidates:
   `test_docker_image_integration`, `test_worktree`, `test_git_gate_enforcement`,
   `test_merge_driver`, `test_parallel_closeout`, `test_release_engine`, `test_installers`, and
   the heavy parts of `test_commit`, `test_lifecycle_wrap`, `test_devenv`, `test_bootstrap`.
2. `tests/conftest.py`: register the `integration` marker and apply it in
   `pytest_collection_modifyitems` from the registry.
3. `pyproject.toml` `[tool.pytest.ini_options]`: add `markers = ["integration: ..."]`.
4. `.along/scripts/test.py`: `--unit` / `--fast` drops tests whose module or id is in the
   registry (same file, so both runners agree). The zero-test safeguard still applies.
5. Tests: registry entries all name existing modules/tests (a stale entry fails), and
   `--unit` excludes them.

## Phase 2: Parallel execution with pytest-xdist
1. Add `pytest-xdist>=3.5.0` to `[dependency-groups] dev`; refresh `uv.lock`.
2. `tests/conftest.py`: when `PYTEST_XDIST_WORKER` is set, deselect `test_zz_hermetic_suite`
   items in `pytest_collection_modifyitems`.
3. `.along/scripts/test.py -n <N|auto>`: after the pre-flight syntax gate, take the hermetic
   BASELINE in the parent, run `pytest -n <N> --dist=loadfile -p no:cacheprovider`, then run
   `test_zz_hermetic_suite.py` serially in a second step against that baseline. Without xdist
   installed, print a notice and fall back to the sequential runner.
   `-p no:cacheprovider` keeps `.pytest_cache/` out of the repository root.
4. Audit fixtures for shared fixed paths (grep for literal temp names, `REPO_ROOT` writes,
   fixed ports in dashboard tests); fix collisions found by 3 consecutive `-n auto` runs.

## Phase 3: Shared read-only fixtures in test_skills_and_scripts.py
Only for tests proven read-only (assert the fixture tree hash is unchanged in `tearDownClass`).
Mutating tests keep per-test fixtures. No assertion is removed or weakened.

## Phase 4 (optional, separate issue): in-process engine invocation
Only if Phase 0 shows process spawn dominates `test_skills_and_scripts.py` after phases 1-3.
1. Production change first: give `along_update.py` and `along_dash.py` a `main(argv=None) -> int`
   and keep `if __name__ == "__main__": sys.exit(main())`.
2. Test helper `run_engine_inprocess(entry, argv, cwd, env)`: saves and restores `sys.argv`,
   cwd, `os.environ` (`mock.patch.dict(..., clear=True)` with the isolated home env),
   `sys.path`, and `sys.modules` entries for engine modules; redirects stdout/stderr; maps
   `SystemExit` to a return code. Engines that call `bootstrap.ensure_deps()` or re-exec stay on
   subprocess.
3. Convert tests one at a time; each conversion keeps identical assertions.

## Invariants
- No test deleted, skipped by default or weakened; the full suite still runs everything.
- `test_zz_hermetic_suite.py` always runs serially, after everything else, in every runner mode.
- No new files in the repository root (`.pytest_cache`, worker temp dirs).
- ASCII typography (`python scripts/sanitize_typography.py --check`).

## Verification
- Phase 0 numbers vs after each phase, recorded in the issue.
- `python .along/scripts/test.py --unit`, `python .along/scripts/test.py -n auto`,
  `uv run pytest -m "not integration" -q`, full sequential `python .along/scripts/test.py`.
