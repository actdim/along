---
protocol: along
protocol_version: "4.4.7"
date: 2026-10-08
slug: test-gate-cost-reduction
agent: antigravity
branch: main
commit: 77f4161
summary: Implement tree-hash reuse and scoped doc tests for test_before_stop (feat--test-gate-cost-reduction)
milestone: v4.5.0-multi-user-merge-automation
issues_advanced: []
issues_completed: [feat--test-gate-cost-reduction]
decisions: []
risks_logged: []
spikes_conducted: []
---

# Session: Test gate cost reduction

## Summary
Implement tree-hash reuse and scoped doc tests for test_before_stop (feat--test-gate-cost-reduction)

## Decisions
- None (confirmed at wrap: no architectural decisions).

## Blackboard Record

Execution mode: role-based; plan revision 1; approved: true.

| Step | Title | Status | Retries | Review |
| --- | --- | --- | --- | --- |
| 1 | Core Tree-Hash Reuse in Stop Gate | passed | 0 | yes |
| 2 | Scoped Doc-Only Test Execution & Gate Integration | passed | 0 | yes |
| 3 | Lifecycle Hook Speed & Release Post-Bump Tree Hash | passed | 0 | yes |
| 4 | Documentation Blast Radius & Verification | passed | 0 | yes |

### Attributed Files

| Path | Kind | Edits | Last edit | Sessions |
| --- | --- | --- | --- | --- |
| `.along/rules/gates.yaml` | state | 1 | 2026-10-08T16:48:09Z | antigravity--0347a583-91eb-4253-9ad5-79ae07ff36da |
| `.along/scripts/test.py` | state | 4 | 2026-10-08T16:51:23Z | antigravity--0347a583-91eb-4253-9ad5-79ae07ff36da |
| `docs/topic--declarative-gates-and-traceability.md` | docs | 1 | 2026-10-08T16:54:07Z | antigravity--0347a583-91eb-4253-9ad5-79ae07ff36da |
| `docs/topic--runtime-hooks-and-gates.md` | docs | 1 | 2026-10-08T16:53:50Z | antigravity--0347a583-91eb-4253-9ad5-79ae07ff36da |
| `scripts/along_version_bump.py` | source | 2 | 2026-10-08T16:52:15Z | antigravity--0347a583-91eb-4253-9ad5-79ae07ff36da |
| `scripts/alongkit/gates.py` | source | 3 | 2026-10-08T16:57:56Z | antigravity--0347a583-91eb-4253-9ad5-79ae07ff36da |
| `scripts/alongkit/hooks/predicates.py` | source | 4 | 2026-10-08T16:48:59Z | antigravity--0347a583-91eb-4253-9ad5-79ae07ff36da |
| `tests/test_lifecycle_test_evidence.py` | source | 2 | 2026-10-08T16:49:13Z | antigravity--0347a583-91eb-4253-9ad5-79ae07ff36da |

### Plan

#### Living Implementation Plan: feat--test-gate-cost-reduction

##### Execution Mode
Role-Based (along-team sequential state machine)

##### Requirement Traceability Matrix
- REQ-1: `check_test_before_stop` passes when `testruns.green_run_for(repo_root, tree_hash)` finds a green run on the current working tree. Time comparison is fallback.
- REQ-2: Doc-only edits under `count_docs: true` are satisfied by a scoped run of Markdown-facing tests (`doc_tests: [...]`) instead of the full suite.
- REQ-3: Report slowest tests in lifecycle hook (`.along/scripts/test.py`), evaluate parallel execution.
- REQ-4: Coordinate with `feat--gate-strictness-profiles` REQ-2: `test_before_stop` cost does not scale with turn count.
- REQ-5: Update `docs/topic--runtime-hooks-and-gates.md` with tree-hash reuse and doc test scope.
- REQ-6: Version-only and state-only changes keep green run; `along_version_bump` records green run for post-bump tree.

---

###### Step 1: Core Tree-Hash Reuse in Stop Gate
- **Files**: `scripts/alongkit/hooks/predicates.py`, `tests/test_lifecycle_test_evidence.py`
- **Actions**:
  1. Update `check_test_before_stop`: compute `tree = testruns.tree_hash(repo_root)`. If `testruns.green_run_for(repo_root, tree)` returns an ok run, immediately return None (allow turn stop).
  2. Fall back to timestamp comparison when `tree` is None or no matching green run exists.
  3. In `tests/test_lifecycle_test_evidence.py`, add hermetic unit tests verifying:
     - Edit file -> test -> edit back to original content -> stop gate passes without re-running tests.
     - Edit file -> no test run -> stop gate blocks.
- **Traceability**: Satisfies REQ-1, REQ-4.

###### Step 2: Scoped Doc-Only Test Execution & Gate Integration
- **Files**: `scripts/alongkit/hooks/predicates.py`, `.along/scripts/test.py`, `.along/rules/gates.yaml`, `tests/test_lifecycle_test_evidence.py`
- **Actions**:
  1. Add `doc_tests` configuration to `test_before_stop` in `.along/rules/gates.yaml`.
  2. In `predicates.py`, track `last_doc_test_time` in activity trace when running doc-scoped tests (or full suite).
  3. In `check_test_before_stop`, if session only modified documentation (no source edits after `last_test_time`), allow turn stop if `last_doc_test_time >= doc_time`.
  4. In `.along/scripts/test.py`, add `--doc` flag to load and run configured doc tests (or default list).
  5. Add hermetic unit tests in `tests/test_lifecycle_test_evidence.py` verifying doc-only edits pass after running doc-scoped tests.
- **Traceability**: Satisfies REQ-2.

###### Step 3: Lifecycle Hook Speed & Release Post-Bump Tree Hash
- **Files**: `.along/scripts/test.py`, `scripts/along_version_bump.py`
- **Actions**:
  1. In `.along/scripts/test.py`, implement per-test duration timing via custom `TextTestResult` and print top slowest tests (default top 5 or via `--slowest N`).
  2. When full suite succeeds, call `testruns.record_run(repo_root, True, testruns.tree_hash(repo_root), "test.py")` to ensure tree hash is recorded.
  3. In `scripts/along_version_bump.py`, after finalizing bump mutations / commit, record green run for post-bump tree via `testruns.record_run(repo_root, True, testruns.tree_hash(repo_root), "along bump")`.
- **Traceability**: Satisfies REQ-3, REQ-6.

###### Step 4: Documentation Blast Radius & Verification
- **Files**: `docs/topic--runtime-hooks-and-gates.md`
- **Actions**:
  1. Update `docs/topic--runtime-hooks-and-gates.md` explaining tree-hash caching in `test_before_stop` and `doc_tests` configuration.
  2. Run full test suite and verify clean execution with zero regressions.
- **Traceability**: Satisfies REQ-5.

### Research

#### Research & Pre-Flight Analysis: feat--test-gate-cost-reduction

##### Problem & Current Architecture
1. **Stop Gate Overhead**:
   `predicates.check_test_before_stop` runs at the end of every agent turn. If any source edit was made, it compares `last_edit_time` with `last_test_time`. It does not check `testruns.green_run_for(repo_root, tree_hash)`.
   Even if the tree was reverted back to clean or already tested green, it forces a re-run of the full suite (~127s on Windows, 967 tests).
2. **Doc Edits Under `count_docs: true`**:
   Currently, `.along/rules/gates.yaml` sets `count_docs: true`. Any edit in `docs/` or `README.md` sets `last_doc_edit_time`, which sets `edit_time = doc_time` in `check_test_before_stop`, triggering a full test run.
   Doc edits only need Markdown-facing tests (e.g. `test_context_budget.py`, `test_sanitizer.py`, `test_kb_sync.py`, `test_kb_search.py`, `test_skills_and_scripts.py`).
3. **Missing Tree Hash Recording in Test Hook**:
   `.along/scripts/test.py` does not record green runs to `testruns.json` when the suite passes. Only `lifecycle.py` (`along test`) and `gates.py` (`run_repository_tests`) do so.
4. **Post-Bump Invalidation in `along_version_bump`**:
   `along_version_bump.py` runs tests on the pre-bump tree, then bumps files and creates a commit. The post-bump tree hash differs from the pre-bump tree, so when `along wrap` runs next, it executes the full suite again (218s).
   Recording a green run for the post-bump tree in `along_version_bump.py` prevents this duplicate test run.
5. **Slowest Test Profiling & Parallel Execution**:
   A spike benchmark shows parallel execution across 4 workers yields a 2.4x speedup on Windows (2.33s vs 5.58s for 6 modules). Measuring per-test duration in `test.py` enables reporting the top slowest tests.

##### Target Symbols & Affected Files
- `scripts/alongkit/hooks/predicates.py`: `check_test_before_stop`, `record_tool_activity`
- `scripts/alongkit/testruns.py`: `tree_hash`, `green_run_for`, `record_run`
- `.along/scripts/test.py`: `main`, custom test runner/result reporting slowest tests and supporting `--doc`
- `scripts/along_version_bump.py`: `main`, post-bump green run recording
- `.along/rules/gates.yaml`: gate `test_before_stop` options (`doc_tests`)
- `tests/test_lifecycle_test_evidence.py`: hermetic unit tests
- `docs/topic--runtime-hooks-and-gates.md`: documentation

### Execution Trace

#### Execution Trace: test-gate-cost-reduction
- 2026-10-08T16:40:15Z denied [require_plan_approval] run_command: Inquiry Read-Only Invariance [gate: require-plan-approval]: No approved plan for issue 'test-gate-cost-reduction' (phase: 'planning', plan_approved: false). ... (x5)
- 2026-10-08T16:42:39Z plan approved (along plan approve)
- 2026-10-08T16:42:44Z step 1: pending -> in-progress
- 2026-10-08T16:43:37Z edit scripts/alongkit/hooks/predicates.py (x2)
- 2026-10-08T16:44:00Z edit tests/test_lifecycle_test_evidence.py
- 2026-10-08T16:44:24Z step 1: in-progress -> passed
- 2026-10-08T16:44:29Z step 2: pending -> in-progress
- 2026-10-08T16:47:54Z edit scripts/alongkit/gates.py (x2)
- 2026-10-08T16:48:09Z edit .along/rules/gates.yaml
- 2026-10-08T16:48:23Z edit .along/scripts/test.py
- 2026-10-08T16:48:59Z edit scripts/alongkit/hooks/predicates.py (x2)
- 2026-10-08T16:49:13Z edit tests/test_lifecycle_test_evidence.py
- 2026-10-08T16:50:04Z step 2: in-progress -> passed
- 2026-10-08T16:50:09Z step 3: pending -> in-progress
- 2026-10-08T16:51:23Z edit .along/scripts/test.py (x3)
- 2026-10-08T16:52:15Z edit scripts/along_version_bump.py (x2)
- 2026-10-08T16:52:38Z step 3: in-progress -> passed
- 2026-10-08T16:53:02Z step 4: pending -> in-progress
- 2026-10-08T16:53:50Z edit docs/topic--runtime-hooks-and-gates.md
- 2026-10-08T16:54:07Z edit docs/topic--declarative-gates-and-traceability.md
- 2026-10-08T16:57:56Z edit scripts/alongkit/gates.py
- 2026-10-08T17:01:28Z step 4: in-progress -> passed

### Review step-1

#### Review Report: Step 1 (Core Tree-Hash Reuse in Stop Gate)

##### Verdict
VERDICT: PASS

##### Summary
Integrated `testruns.tree_hash(repo_root)` and `testruns.green_run_for(repo_root, tree)` into `check_test_before_stop` in `scripts/alongkit/hooks/predicates.py`. Added hermetic test class `TestTreeHashReuse` in `tests/test_lifecycle_test_evidence.py`. Verified that:
1. Clean or reverted trees with a recorded green run pass the Stop gate immediately.
2. Changes to source files without a test run are properly blocked.
3. 46 existing gate and activation tests continue to pass with zero regressions.

##### Gate Execution Manifest
- Workspace Isolation: EXECUTED (PASS) [mode: inherit (default)]
- File Integrity: EXECUTED (PASS)
- Automated Tests: EXECUTED (PASS) [46 tests passed in 0.88s]
- Diff Scope Audit: EXECUTED (PASS) [scoped to predicates.py and test_lifecycle_test_evidence.py]
- Requirement Traceability: EXECUTED (PASS) [REQ-1, REQ-4]
- Blast Radius: EXECUTED (PASS)
- Documentation Parity: SKIPPED (deferred to Step 4)
- Clean Typography: EXECUTED (PASS)

### Review step-2

#### Review Report: Step 2 (Scoped Doc-Only Test Execution & Gate Integration)

##### Verdict
VERDICT: PASS

##### Summary
Implemented scoped doc-only test execution and gate integration for `count_docs: true`:
1. Added `DEFAULT_DOC_TESTS` and `get_doc_tests(repo_root)` in `scripts/alongkit/gates.py` resolving declared doc tests from `.along/rules/gates.yaml`.
2. Configured `doc_tests` under `test_before_stop` in `.along/rules/gates.yaml`.
3. Supported `--doc` / `--doc-tests` flag in `.along/scripts/test.py` to selectively run the declared doc test suite (134 tests in 18s instead of 127s).
4. Updated `record_tool_activity` in `scripts/alongkit/hooks/predicates.py` to record `last_doc_test_time` on doc test runs and both timestamps on full runs.
5. Updated `check_test_before_stop` in `scripts/alongkit/hooks/predicates.py` so that doc-only edits under `count_docs: true` pass when doc tests have run, while source edits continue to require a full suite run.
6. Added hermetic tests `test_doc_only_edit_satisfied_by_doc_scoped_test` and `test_doc_scoped_test_does_not_satisfy_source_edit` in `tests/test_lifecycle_test_evidence.py`.

##### Gate Execution Manifest
- Workspace Isolation: EXECUTED (PASS) [mode: inherit (default)]
- File Integrity: EXECUTED (PASS)
- Automated Tests: EXECUTED (PASS) [test_lifecycle_test_evidence.py (12 tests) and test.py --doc (134 tests) passed cleanly]
- Diff Scope Audit: EXECUTED (PASS)
- Requirement Traceability: EXECUTED (PASS) [REQ-2]
- Blast Radius: EXECUTED (PASS)
- Documentation Parity: SKIPPED (deferred to Step 4)
- Clean Typography: EXECUTED (PASS)

### Review step-3

#### Review Report: Step 3 (Lifecycle Hook Speed & Release Post-Bump Tree Hash)

##### Verdict
VERDICT: PASS

##### Summary
Implemented test suite profiling, full suite green run recording, and post-bump tree hash recording:
1. Added `TimingTestResult` and `TimingTestRunner` in `.along/scripts/test.py` measuring per-test elapsed time and printing the top slowest tests (default top 5 or via `--slowest=N`).
2. Configured `.along/scripts/test.py` to record green runs via `testruns.record_run(repo_root, True, tree, "test.py")` on successful full suite runs.
3. Updated `scripts/along_version_bump.py` to record a green run for the post-bump working tree upon successful completion, ensuring `along wrap` reuses the verified tree without running tests a second time.
4. Conducted spike evaluation for parallel test execution: 4 workers yielded 2.33s vs 5.58s sequential (2.4x speedup on Windows).
5. All 19 tests in `tests/test_release_engine.py` passed with top slowest test reporting verified.

##### Gate Execution Manifest
- Workspace Isolation: EXECUTED (PASS) [mode: inherit (default)]
- File Integrity: EXECUTED (PASS)
- Automated Tests: EXECUTED (PASS) [test_release_engine.py (19 tests) passed cleanly]
- Diff Scope Audit: EXECUTED (PASS)
- Requirement Traceability: EXECUTED (PASS) [REQ-3, REQ-6]
- Blast Radius: EXECUTED (PASS)
- Documentation Parity: SKIPPED (deferred to Step 4)
- Clean Typography: EXECUTED (PASS)

### Review step-4

#### Review Report: Step 4 (Documentation Blast Radius & Verification)

##### Verdict
VERDICT: PASS

##### Summary
Completed documentation blast radius updates and full repository test suite verification:
1. Updated `docs/topic--runtime-hooks-and-gates.md` explaining tree-hash reuse in `test_before_stop` (`testruns.green_run_for(repo_root, tree_hash)`), `along bump` post-bump tree hash caching, and doc-only scoped test runs under `count_docs: true` (`along test --doc`).
2. Updated `docs/topic--declarative-gates-and-traceability.md` describing tree-hash green run satisfaction and `doc_tests` options.
3. Executed full test suite (`python .along/scripts/test.py -q`): all 1129 tests passed cleanly (with 2 skipped).
4. Verified that successful full suite test run recorded green tree hash in `.along/diagnostics/test_runs.json` (`source: "test.py"`).

##### Gate Execution Manifest
- Workspace Isolation: EXECUTED (PASS) [mode: inherit (default)]
- File Integrity: EXECUTED (PASS)
- Automated Tests: EXECUTED (PASS) [1129 tests passed in 172.58s]
- Diff Scope Audit: EXECUTED (PASS)
- Requirement Traceability: EXECUTED (PASS) [REQ-5]
- Blast Radius: EXECUTED (PASS)
- Documentation Parity: EXECUTED (PASS)
- Clean Typography: EXECUTED (PASS)
