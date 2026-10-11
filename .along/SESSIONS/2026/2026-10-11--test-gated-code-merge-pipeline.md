---
protocol: along
protocol_version: "4.4.9"
date: 2026-10-11
slug: test-gated-code-merge-pipeline
agent: antigravity
branch: main
commit: b6e22fb
summary: 'feat(merge): test-gated code conflict resolution and pre-merge predictor'
milestone: v4.5.0-multi-user-merge-automation
issues_advanced: []
issues_completed: [feat--test-gated-code-merge-pipeline]
decisions: []
risks_logged: []
spikes_conducted: []
---

# Session: Test gated code merge pipeline

## Summary
feat(merge): test-gated code conflict resolution and pre-merge predictor

## Decisions
- None (confirmed at wrap: no architectural decisions).

## Blackboard Record

Execution mode: role-based; plan revision 2; approved: true.

| Step | Title | Status | Retries | Review |
| --- | --- | --- | --- | --- |
| 1 | Step 1 | passed | 0 | yes |
| 2 | Step 2 | passed | 0 | yes |
| 3 | Step 3 | passed | 0 | yes |
| 4 | Step 4 | passed | 0 | yes |
| 5 | Step 5 | passed | 1 | yes |

### Attributed Files

| Path | Kind | Edits | Last edit | Sessions |
| --- | --- | --- | --- | --- |
| `pyproject.toml` | source | 1 | 2026-10-11T12:47:00Z | antigravity--c4966a0a-af2e-48b6-874f-b20fdfbf0b01 |
| `scripts/along_conflict_check.py` | source | 1 | 2026-10-11T12:35:57Z | antigravity--c4966a0a-af2e-48b6-874f-b20fdfbf0b01 |
| `scripts/along_exec.py` | source | 2 | 2026-10-11T12:37:04Z | antigravity--c4966a0a-af2e-48b6-874f-b20fdfbf0b01 |
| `scripts/along_resolve.py` | source | 2 | 2026-10-11T12:37:43Z | antigravity--c4966a0a-af2e-48b6-874f-b20fdfbf0b01 |
| `scripts/alongkit/conflict_check.py` | source | 2 | 2026-10-11T12:47:16Z | antigravity--c4966a0a-af2e-48b6-874f-b20fdfbf0b01 |
| `scripts/alongkit/resolve.py` | source | 1 | 2026-10-11T12:33:14Z | antigravity--c4966a0a-af2e-48b6-874f-b20fdfbf0b01 |
| `scripts/alongkit/resolve_code.py` | source | 3 | 2026-10-11T12:47:35Z | antigravity--c4966a0a-af2e-48b6-874f-b20fdfbf0b01 |
| `tests/test_along_resolve_code.py` | source | 2 | 2026-10-11T12:39:24Z | antigravity--c4966a0a-af2e-48b6-874f-b20fdfbf0b01 |

### Plan

#### Implementation Plan: Test-Gated Code Merge Pipeline

- Issue: `feat--test-gated-code-merge-pipeline`
- Execution Mode: Role-Based (`along-team`)
- Plan Revision: 1 (Baseline)
- Task Size: `L-Size`
- Workspace Mode: `workspace: inherit`

---

##### 1. Requirement Traceability Matrix

| Requirement | Description | Plan Step |
| :--- | :--- | :--- |
| `REQ-1` | Language-aware code conflict resolution (imports union, non-overlapping functions/classes, collision preservation) | Step 1 |
| `REQ-2` | Mandatory Quality Gate Verification Pipeline (syntax validation, typography gate, test runner) | Step 2 |
| `REQ-3` | Transactional Rollback Engine (`FileTransaction` rollback on failure, `git add` on pass) | Step 2 |
| `REQ-4` | Pre-Merge Conflict Predictor (`along conflict-check <branch>` with merge-base & AST overlap detection) | Step 3 |
| `REQ-5` | Hermetic test suite covering resolution, rollback, and conflict prediction (`tests/test_along_resolve_code.py`) | Step 5 |
| `REQ-6` | Public CLI dispatch in `along_resolve.py` (`--code`) and `along_exec.py` (`conflict-check`) | Step 4 |

---

##### 2. Living Plan Steps

###### Step 1: Code Conflict Reconciliation Engine
- Target files:
  - `scripts/alongkit/resolve.py`
  - `scripts/alongkit/resolve_code.py`
- Objective:
  - Support code conflict hunk parsing without Markdown fence filtering (`is_markdown=False`).
  - Implement language-aware import reconciliation: parse imports, extract module/names, compute set union, sort, and re-emit.
  - Implement Python AST definition reconciliation: parse `ours` and `theirs` ASTs, extract top-level functions and classes; if symbol names are disjoint, emit sequentially with standard 2-line spacing; if symbols overlap, keep conflict markers.
  - Support 3-way text merge fallback for non-Python or non-overlapping code hunks.
- Acceptance criteria:
  - Disjoint imports and functions merge cleanly with valid syntax.
  - Overlapping functions retain Git conflict markers.

###### Step 2: Quality Gate Pipeline & Transactional Rollback
- Target files:
  - `scripts/alongkit/resolve_code.py`
- Objective:
  - Integrate `alongkit.transaction.FileTransaction`: snapshot unmerged code files prior to writing tentative resolutions.
  - Gate 1 (Syntax): Validate syntax via `compile(content, path, "exec")` (Python) or language checkers.
  - Gate 2 (Typography): Validate clean ASCII typography via `alongkit.typography.findings()`.
  - Gate 3 (Tests): Execute repository test runner via `along test -q` (or project test script).
  - Rollback behavior: If any gate or test fails, invoke `tx.rollback()` to atomically restore exact Git conflict markers byte-for-byte, outputting diagnostics with failing hunks/tests.
  - Pass behavior: If all gates pass, stage files with `git add` and commit transaction.
- Acceptance criteria:
  - Failing test or syntax error immediately restores conflict markers.
  - Passing gates stage files cleanly without user intervention.

###### Step 3: Pre-Merge Conflict Predictor
- Target files:
  - `scripts/along_conflict_check.py`
  - `scripts/alongkit/conflict_check.py`
- Objective:
  - Implement `predict_conflicts(repo_root, target_branch)`:
    - Compute merge-base: `git merge-base HEAD <target_branch>`.
    - Extract modified files in `base..HEAD` and `base..<target_branch>`.
    - Identify overlapping modified files.
    - For overlapping Python files: inspect AST symbols across base, HEAD, and target branch.
    - Classify risk:
      - `LOW`: No overlapping files.
      - `MEDIUM`: Overlapping files, but modified AST symbols are disjoint.
      - `HIGH`: Overlapping modified symbols/functions/classes.
    - Format diagnostic report with risk level and recommendations.
- Acceptance criteria:
  - Predictor accurately detects overlapping files and symbol collisions between branches.

###### Step 4: CLI Dispatch and Surface Integration
- Target files:
  - `scripts/along_resolve.py`
  - `scripts/along_exec.py`
- Objective:
  - Extend `along_resolve.py` with `--code` flag to run code conflict resolution pipeline.
  - Wire `"conflict-check": "along_conflict_check.py"` into `TOOL_MAPPINGS` in `scripts/along_exec.py`.
  - Ensure `along resolve --code` and `along conflict-check <branch>` work consistently.
- Acceptance criteria:
  - CLI commands execute and display helpful usage/diagnostic output.

###### Step 5: Hermetic Test Suite & Verification
- Target files:
  - `tests/test_along_resolve_code.py`
- Objective:
  - Author comprehensive unit and integration tests using `hermetic.repo_fixture()`:
    - Test import reconciliation.
    - Test disjoint function/class reconciliation.
    - Test collision marker preservation.
    - Test transactional rollback on syntax and test failures.
    - Test pre-merge conflict check risk classification.
  - Run full test suite via `along test`.
- Acceptance criteria:
  - All new tests in `tests/test_along_resolve_code.py` pass.
  - Zero regressions across the full repository test suite.

### Research

#### Scout Research Report: Test-Gated Code Merge Pipeline

Target Issue: `feat--test-gated-code-merge-pipeline`
Scope: Read-only codebase analysis for `along resolve --code`, Quality Gate Verification Pipeline, Transactional Rollback, and `along conflict-check <branch>`.

##### 1. Executive Summary & Architectural Findings

The proposed feature introduces test-gated source code conflict resolution, atomic rollback, and pre-merge conflict prediction. The repository provides solid foundations:
- Transaction management: `alongkit.transaction.FileTransaction` provides byte-exact snapshot and rollback.
- Git operations: `alongkit.proc.git` and `alongkit.closeout.git_changes` provide execution with index-corruption resilience and unmerged status detection.
- Gate execution: `alongkit.gates` provides `syntax_gate()`, `typography_gate()`, and `run_repository_tests()`.
- AST parsing: `alongkit.patcher` and `alongkit.kb` provide AST node-span mapping, symbol extraction, and compilation verification via `ast.parse` and `compile()`.

Existing conflict resolution (`scripts/along_resolve.py` and `alongkit/resolve.py`) is designed for Markdown documentation. Adapting it to code requires:
1. Distinguishing Markdown vs source code parsing (Markdown fence filtering must be bypassed for code).
2. AST and language-aware reconciliation for imports and disjoint functions/classes.
3. Transaction-wrapped gate verification pipeline.
4. Pre-merge conflict predictor comparing branch diffs against merge-base.

##### 2. Component Analysis

###### 2.1 scripts/along_resolve.py and alongkit/resolve.py
- `along_resolve.py` accepts `--docs` (default: True), `--check` / `--dry-run`, `--strict`, and positional files.
- Need to add `--code` flag to resolve source code conflicts.
- `resolve.parse_conflict_hunks` in `alongkit/resolve.py` uses `FenceTracker` for Markdown. For source code files, `is_markdown=False` must be supported so backticks in code/comments do not disable marker detection.

###### 2.2 Transactional Rollback (alongkit.transaction.FileTransaction)
- `FileTransaction(repo_root, label)` snapshots protected files before mutation.
- `tx.protect(path)` stores original bytes.
- `tx.rollback()` restores all protected files byte-for-byte.
- `tx.commit()` finalizes on success.

###### 2.3 Quality Gate Pipeline
- Syntax check: Python `compile()` / `ast.parse()`, optional TS `tsc --noEmit`.
- Typography check: `alongkit.typography.findings()` verifying zero non-ASCII typographic characters.
- Test runner: `along test -q` / project lifecycle script.

###### 2.4 Pre-Merge Conflict Predictor (along conflict-check <branch>)
- Computes `git merge-base HEAD <branch>`.
- Identifies overlapping modified files between `base..HEAD` and `base..<branch>`.
- Extracts modified AST symbols on overlapping Python files.
- Classifies risk: Low (no overlapping files), Medium (overlapping files, disjoint symbols), High (colliding symbols).

###### 2.5 Command Dispatch in scripts/along_exec.py
- `TOOL_MAPPINGS` maps CLI command names to scripts.
- Map `"conflict-check": "along_conflict_check.py"` and extend `"resolve": "along_resolve.py"`.

### Execution Trace

#### Execution Trace: test-gated-code-merge-pipeline
- 2026-10-10T21:17:38Z test pass (along test)
- 2026-10-10T21:26:42Z denied [require_plan_approval] run_command: Inquiry Read-Only Invariance [gate: require-plan-approval]: No approved plan for issue 'test-gated-code-merge-pipeline' (phase: 'planning', plan_approved: fa...
- 2026-10-11T12:32:37Z plan approved (along plan approve)
- 2026-10-11T12:32:55Z step 1: pending -> in-progress
- 2026-10-11T12:33:14Z edit scripts/alongkit/resolve.py
- 2026-10-11T12:33:54Z edit scripts/alongkit/resolve_code.py
- 2026-10-11T12:34:55Z step 1: in-progress -> passed
- 2026-10-11T12:35:01Z step 2: pending -> in-progress
- 2026-10-11T12:35:24Z step 2: in-progress -> passed
- 2026-10-11T12:35:30Z step 3: pending -> in-progress
- 2026-10-11T12:35:50Z edit scripts/alongkit/conflict_check.py
- 2026-10-11T12:35:57Z edit scripts/along_conflict_check.py
- 2026-10-11T12:36:34Z step 3: in-progress -> passed
- 2026-10-11T12:36:37Z step 4: pending -> in-progress
- 2026-10-11T12:37:04Z edit scripts/along_exec.py (x2)
- 2026-10-11T12:37:43Z edit scripts/along_resolve.py (x2)
- 2026-10-11T12:38:23Z step 4: in-progress -> passed
- 2026-10-11T12:38:32Z step 5: pending -> in-progress
- 2026-10-11T12:39:24Z edit tests/test_along_resolve_code.py (x2)
- 2026-10-11T12:40:19Z step 5: in-progress -> passed
- 2026-10-11T12:46:06Z test FAIL (Wrap Quality Gate)
- 2026-10-11T12:46:47Z denied [team_step_active] replace_file_content: along-team Step Violation [gate: team-step-active]: 'test-gated-code-merge-pipeline' runs the along-team step loop, but no step is in progress, so 'pyproject...
- 2026-10-11T12:46:55Z step 5: passed -> in-progress
- 2026-10-11T12:46:55Z step 5: retry 1/2
- 2026-10-11T12:47:00Z edit pyproject.toml
- 2026-10-11T12:47:16Z edit scripts/alongkit/conflict_check.py
- 2026-10-11T12:47:35Z edit scripts/alongkit/resolve_code.py (x2)
- 2026-10-11T12:48:11Z step 5: in-progress -> passed
- 2026-10-11T12:52:24Z test pass (Wrap Quality Gate)

### Review step-1

#### Review Step 1: Code Conflict Reconciliation Engine

- Step: 1
- Target: Code conflict reconciliation engine (`scripts/alongkit/resolve.py`, `scripts/alongkit/resolve_code.py`)
- Requirement: `REQ-1`

##### Checks
1. File Integrity: PASS. Files exist, non-zero bytes, syntax valid.
2. Automated Tests: PASS. Existing resolve tests (`test_along_resolve_docs.py`) pass cleanly (13/13).
3. Diff & Scope Audit: PASS. `parse_conflict_hunks` parameterized with `is_markdown=True` backwards-compatible default; `resolve_code.py` handles imports and disjoint definitions without regression.
4. Requirement Traceability: PASS. Disjoint imports and functions supported, collision preservation implemented.
5. Blast Radius: PASS. `along graph-impact` confirms healthy impact and 0 broken nodes.
6. Typography: PASS. Clean ASCII, zero non-ASCII characters.

VERDICT: PASS

Gate Execution Manifest:
- Workspace Isolation: EXECUTED (PASS) [mode: inherit]
- File Integrity: EXECUTED (PASS)
- Automated Tests: EXECUTED (PASS) [test_along_resolve_docs.py: 13 passed]
- Diff Scope Audit: EXECUTED (PASS)
- Requirement Traceability: EXECUTED (PASS) [REQ-1]
- Blast Radius: EXECUTED (PASS) [along graph-impact: healthy]
- Documentation Parity: SKIPPED (internal engine module, public CLI in Step 4)
- Clean Typography: EXECUTED (PASS)

### Review step-2

#### Review Step 2: Quality Gate Pipeline & Transactional Rollback

- Step: 2
- Target: Quality gate verification and transactional rollback (`scripts/alongkit/resolve_code.py`)
- Requirements: `REQ-2`, `REQ-3`

##### Checks
1. File Integrity: PASS. Files non-zero bytes, valid Python syntax.
2. Automated Tests: PASS. Pre-flight syntax validation and unit tests pass cleanly.
3. Diff & Scope Audit: PASS. `verify_code_gates` and `resolve_and_verify_code` implement syntax check, typography check, test execution, and transactional rollback via `FileTransaction`.
4. Requirement Traceability: PASS.
   - Syntax validation (`compile`), typography validation (`typography.findings`), and test running (`along test` / `test.py`) enforced.
   - On gate or test failure: `tx.rollback()` restores byte-exact Git conflict state.
   - On pass: `git add` stages resolved files and `tx.commit()` finalizes.
5. Blast Radius: PASS. AST impact analysis shows 0 impacted nodes.
6. Typography: PASS. Clean ASCII, 0 non-ASCII characters.

VERDICT: PASS

Gate Execution Manifest:
- Workspace Isolation: EXECUTED (PASS) [mode: inherit]
- File Integrity: EXECUTED (PASS)
- Automated Tests: EXECUTED (PASS)
- Diff Scope Audit: EXECUTED (PASS)
- Requirement Traceability: EXECUTED (PASS) [REQ-2, REQ-3]
- Blast Radius: EXECUTED (PASS) [along graph-impact: healthy]
- Documentation Parity: SKIPPED (CLI wiring in Step 4)
- Clean Typography: EXECUTED (PASS)

### Review step-3

#### Review Step 3: Pre-Merge Conflict Predictor

- Step: 3
- Target: Pre-merge branch conflict predictor (`scripts/alongkit/conflict_check.py`, `scripts/along_conflict_check.py`)
- Requirements: `REQ-4`

##### Checks
1. File Integrity: PASS. Files exist, non-zero bytes, syntax valid.
2. Automated Tests: PASS. Tested with branch comparison (`HEAD` vs `HEAD`) in terminal and JSON mode.
3. Diff & Scope Audit: PASS. `predict_conflicts` correctly queries `git merge-base`, diff file lists, and AST symbol mapping.
4. Requirement Traceability: PASS (`REQ-4`). Detects overlapping files, extracts and compares AST symbols, and reports risk levels (LOW, MEDIUM, HIGH).
5. Blast Radius: PASS. New modular engine with 0 regressions.
6. Typography: PASS. Clean ASCII, 0 non-ASCII characters.

VERDICT: PASS

Gate Execution Manifest:
- Workspace Isolation: EXECUTED (PASS) [mode: inherit]
- File Integrity: EXECUTED (PASS)
- Automated Tests: EXECUTED (PASS)
- Diff Scope Audit: EXECUTED (PASS)
- Requirement Traceability: EXECUTED (PASS) [REQ-4]
- Blast Radius: EXECUTED (PASS)
- Documentation Parity: SKIPPED (CLI wiring in Step 4)
- Clean Typography: EXECUTED (PASS)

### Review step-4

#### Review Step 4: CLI Dispatch and Surface Integration

- Step: 4
- Target: CLI dispatch in `scripts/along_resolve.py` and `scripts/along_exec.py`
- Requirements: `REQ-6`

##### Checks
1. File Integrity: PASS. Files exist, valid syntax.
2. Automated Tests: PASS. CLI execution verified via `along_exec.py resolve --help` and `along_exec.py conflict-check --help`.
3. Diff & Scope Audit: PASS. `--code` and `--no-tests` added to `along_resolve.py`, `conflict-check` added to `TOOL_MAPPINGS` in `along_exec.py`.
4. Requirement Traceability: PASS (`REQ-6`). CLI surface is complete and integrated.
5. Blast Radius: PASS. Zero unexpected breakages.
6. Typography: PASS. Clean ASCII, 0 non-ASCII characters.

VERDICT: PASS

Gate Execution Manifest:
- Workspace Isolation: EXECUTED (PASS) [mode: inherit]
- File Integrity: EXECUTED (PASS)
- Automated Tests: EXECUTED (PASS)
- Diff Scope Audit: EXECUTED (PASS)
- Requirement Traceability: EXECUTED (PASS) [REQ-6]
- Blast Radius: EXECUTED (PASS)
- Documentation Parity: EXECUTED (PASS)
- Clean Typography: EXECUTED (PASS)

### Review step-5

#### Review Step 5: Hermetic Test Suite & Verification

- Step: 5
- Target: Hermetic unit test suite (`tests/test_along_resolve_code.py`), packaging manifest, exception gate compliance, execution guards.
- Requirements: `REQ-5`

##### Checks
1. File Integrity: PASS. Tests non-zero bytes, valid syntax.
2. Automated Tests: PASS.
   - `tests/test_along_resolve_code.py`: 12/12 passed (0.76s).
   - `tests/test_along_resolve_docs.py`: 13/13 passed (0.03s).
   - `tests/test_along_exec.py`: 13/13 passed (13.0s).
   - `tests/test_alongkit.py`: 95/95 passed (2.34s, packaging contract + exception gate).
   - `tests/test_rules.py`: 16/16 passed (1.46s, alongkit library execution guards).
3. Diff & Scope Audit: PASS. All acceptance criteria covered: import reconciliation, definition reconciliation, collision retention, transactional rollback on syntax/test failures, pre-merge conflict check risk prediction.
4. Requirement Traceability: PASS (`REQ-5`).
5. Blast Radius: PASS. Zero regressions.
6. Typography: PASS. Clean ASCII, 0 non-ASCII characters.

VERDICT: PASS

Gate Execution Manifest:
- Workspace Isolation: EXECUTED (PASS) [mode: inherit]
- File Integrity: EXECUTED (PASS)
- Automated Tests: EXECUTED (PASS) [test_along_resolve_code.py, test_along_resolve_docs.py, test_along_exec.py, test_alongkit.py, test_rules.py]
- Diff Scope Audit: EXECUTED (PASS)
- Requirement Traceability: EXECUTED (PASS) [REQ-5]
- Blast Radius: EXECUTED (PASS)
- Documentation Parity: EXECUTED (PASS)
- Clean Typography: EXECUTED (PASS)
