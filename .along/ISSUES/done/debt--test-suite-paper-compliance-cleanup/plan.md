# Plan: Test suite paper compliance cleanup and contract assertion hardening

## Execution Mode
Direct

## Context and Scope
Audit of the repository test suite revealed several patterns of paper compliance, redundant execution, and shallow verification that inflate test metrics without providing real contract enforcement:
1. `tests/test_version_bump.py` subclasses `TestReleaseCiCheck` from `tests/test_release_ci_check.py`, needlessly executing the exact same 15 test cases twice.
2. `tests/test_release_ci_check.py:264-281` mocks out subcommands and asserts only mock call arguments rather than system failure/rollback behavior.
3. `tests/test_system_comparisons.py` and `tests/test_docs.py` perform literal string matching on marketing phrases in markdown documentation instead of asserting structural schema integrity and link resolution.
4. `tests/test_docker_scripts.py` and `tests/test_skills_and_scripts.py` assert `os.path.isfile(path) is True` without verifying script shebangs, non-empty content, or schema validity.

Target Issue: `debt--test-suite-paper-compliance-cleanup`
Milestone: `v5.0.0-agent-run-protocol-and-observability`

## Step-by-Step Implementation Plan

### Step 1: Deduplicate `tests/test_version_bump.py`
- Remove `from test_release_ci_check import TestReleaseCiCheck`.
- Provide direct tests for `along_version_bump.py` CLI behavior (CLI help, `--dry-run` flag validation, invalid version bump handling).

### Step 2: Behavioral Mock Hardening in `tests/test_release_ci_check.py`
- Refactor `test_release_preflight_passes_skip_ci_to_precondition` to assert system behavior:
  - Verify `release_preflight` raises `ReleaseAborted` if `check_ci_precondition` raises `ReleaseAborted`.
  - Verify `release_preflight` raises `ReleaseAborted` if `run_test_gate` returns non-zero.
  - Verify `release_preflight` raises `ReleaseAborted` if `link_integrity_gate` returns False.

### Step 3: Refactor Brittle Prose Tests in `tests/test_system_comparisons.py` and `tests/test_docs.py`
- In `tests/test_system_comparisons.py`:
  - Assert document existence, valid markdown structure, presence of Paradigm 7 header, and clean ASCII typography.
  - Avoid brittle substring checks on exact marketing phrases ("Append-only chat bloat", "The \"Sufficient Statistic\" Trap / Lost History").
- In `tests/test_docs.py`:
  - Verify rule keywords ("python -c", "view_file", "black box") and section integrity without hardcoding ephemeral phrasing.

### Step 4: Upgrade Superficial File Checks in `tests/test_docker_scripts.py` and `tests/test_skills_and_scripts.py`
- In `tests/test_docker_scripts.py`:
  - Assert `docker/git-credential-along` exists, has non-empty content, and begins with a valid shell shebang (`#!/bin/sh` or `#!/bin/bash`).
- In `tests/test_skills_and_scripts.py`:
  - Assert that generated files (`llms.txt`, `llms-full.txt`, target articles) are non-empty and contain expected headers.

### Step 5: Verification
- Run full test suite with `python .along/scripts/test.py`.
- Verify total test count and execution time, ensuring zero regressions.
