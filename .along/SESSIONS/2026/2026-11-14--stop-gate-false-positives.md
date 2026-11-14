---
protocol: along
protocol_version: "4.8.1"
date: 2026-11-14
slug: stop-gate-false-positives
agent: antigravity
branch: main
commit: 9f0e162
summary: Fix Stop gate false positives on compiled projections and foreign session edits; enable ackable Stop denials
milestone: v4.9.0-stop-gate-resilience-and-runtime-stabilization
issues_advanced: []
issues_completed: [bug--stop-gate-false-positives]
decisions: [ADR-2026-11-14--stop-gate-session-attribution-and-trace-denials]
---

# Session: Stop gate false positives

## Summary
Fix Stop gate false positives on compiled projections and foreign session edits; enable ackable Stop denials

## Decisions
- [ADR-2026-11-14--stop-gate-session-attribution-and-trace-denials]

## Blackboard Record

Execution mode: role-based; plan revision 2; approved: true.

| Step | Title | Status | Retries | Review |
| --- | --- | --- | --- | --- |
| 1 | Step 1 | passed | 0 | yes |
| 2 | Step 2 | passed | 0 | yes |
| 3 | Step 3 | passed | 0 | yes |
| 4 | Step 4 | passed | 0 | yes |
| 5 | Step 5 | passed | 0 | yes |
| 6 | Step 6 | passed | 0 | yes |
| 7 | Step 7 | passed | 0 | yes |
| 8 | Step 8 | passed | 0 | yes |

Plan: kept with the issue (`plan/plan.md`, 1 revision(s)).

### Execution Trace

#### Execution Trace: stop-gate-false-positives
- 2026-11-14T16:33:36Z plan approved (along plan approve) approved_via: cli-unverified, plan_sha256: 5dfca9ba6165
- 2026-11-14T16:55:15Z plan approved (along plan approve) approved_via: cli-unverified, plan_sha256: 5dfca9ba6165
- 2026-11-14T16:57:08Z step 1: pending -> in-progress
- 2026-11-14T17:05:28Z step 1: in-progress -> passed
- 2026-11-14T17:06:08Z step 2: pending -> in-progress
- 2026-11-14T17:15:20Z step 2: in-progress -> passed
- 2026-11-14T17:15:36Z step 3: pending -> in-progress
- 2026-11-14T17:36:40Z step 3: in-progress -> passed
- 2026-11-14T17:36:56Z step 4: pending -> in-progress
- 2026-11-14T17:44:03Z step 4: in-progress -> passed
- 2026-11-14T17:45:27Z step 5: pending -> in-progress
- 2026-11-14T17:57:18Z step 5: in-progress -> passed
- 2026-11-14T17:57:38Z step 6: pending -> in-progress
- 2026-11-14T18:04:37Z step 6: in-progress -> passed
- 2026-11-14T18:04:46Z step 7: pending -> in-progress
- 2026-11-14T18:09:59Z step 7: in-progress -> passed
- 2026-11-14T18:10:11Z step 8: pending -> in-progress
- 2026-11-14T18:44:28Z step 8: in-progress -> passed

### Review step-1

#### Review Record: Step 1 - Compiled projections are not plan-governed (REQ-1)

##### Scope
- `scripts/alongkit/closeout.py`: Added `COMPILED_PROJECTION_NAMES` and `is_compiled_projection`.
- `scripts/alongkit/hooks/predicates.py`: Updated `_is_plan_governed` to exempt compiled projections via `closeout.is_compiled_projection`.
- `tests/test_gates_traceability.py`: Added `TestCompiledProjections` covering package-level `docs/INDEX.md`, `llms.txt`, and source files.

##### Review Checks
1. Code Quality: Pure functions, safe file reading, exact front-matter parsing for Along indexes.
2. Regression: 0 regressions, all 3 tests in `test_gates_traceability.py` pass cleanly.
3. Typography: `along sanitize` reported 0 banned characters.

VERDICT: PASS

### Review step-2

#### Review Record: Step 2 - kb-sync does not rewrite unchanged indexes (REQ-2)

##### Scope
- `scripts/along_kb_sync.py`:
  - `_kb_generate_index`: compare dumped front-matter with preserved `updated` date against existing content; skip write when content is identical.
  - `sync_decisions_to_docs`: compare destination content before writing ADR files and decisions `INDEX.md`; skip write and print notification only when at least one file was written.
- `tests/test_kb_sync.py`: Added `TestIdempotentSync` verifying byte-identical repository state across two consecutive sync runs with advanced dates.

##### Review Checks
1. Code Quality: Clean date comparison without unneeded date bumps, avoiding false dirty git states.
2. Regression: All 19 tests in `tests/test_kb_sync.py` passed in 3.19s.
3. Typography: `along sanitize` reported 0 banned characters.

VERDICT: PASS

### Review step-3

#### Review Record: Step 3 - wrap commits what its sync changed (REQ-3)

##### Scope
- `scripts/alongkit/lifecycle.py`:
  - `_auto_commit_wrapped_work`: Added `extra_projections` parameter to stage dynamically compiled projections.
  - `execute_wrap`: Captured pre/post fingerprint of git changes around the `along_kb_sync.py` subprocess, detected modified compiled projections (`is_compiled_projection`), and passed them into `extra_projections`.
- `tests/test_parallel_closeout.py`: Added `TestWrapCommitsPackageIndex` verifying `packages/pkg/docs/INDEX.md` is committed and the working tree is clean after wrap.

##### Review Checks
1. Code Quality: Dynamic capture of written projections prevents uncommitted package-level indexes.
2. Regression: All 48 tests in `test_parallel_closeout.py` and all 48 tests in `test_wrap_engine_writes.py`/`test_lifecycle_wrap.py` passed cleanly.
3. Typography: `along sanitize` reported 0 banned characters.

VERDICT: PASS

### Review step-4

#### Review Record: Step 4 - Stop plan gate counts only this session's writes (REQ-4)

##### Scope
- `scripts/alongkit/hooks/predicates.py`:
  - `record_tool_activity`:
    - Reset `turn_writes = []` and clear `shell_pending` on `USER_PROMPT_SUBMIT`.
    - Track written paths on `POST_TOOL_USE` for file writing tools (`turn_writes`).
    - Capture snapshot in `shell_pending` on `PRE_TOOL_USE` and diff on `POST_TOOL_USE` for shell tools.
  - `check_mutation_authorization`:
    - Filtered `turn_changes` at `STOP` against this session's attributed writes (`mine_keys`).
    - Foreign changes outside session tool calls logged as trace event, not causing false positive denials.
- `tests/test_gates_traceability.py`: Added `TestStopCountsSessionWrites` testing foreign writes, own file-tool writes, own shell writes, and legacy trace compatibility.

##### Review Checks
1. Code Quality: Clean attribution tracking per session key with Windows path normalization.
2. Regression: All 73 tests across `test_gates_traceability.py`, `test_inquiry_gate.py`, `test_anti_silent_fallback.py`, and `test_hook_activation.py` passed cleanly.
3. Typography: `along sanitize` reported 0 banned characters.

VERDICT: PASS

### Review step-5

#### Review Record: Step 5 - Stop denials are recorded and ackable, bound or not (REQ-5)

##### Scope
- `scripts/alongkit/hooks/predicates.py`:
  - Added `stop_denial_id` generating deterministic Stop denial IDs.
  - Plan gate Stop message records `last_stop_denial` in activity trace and suggests `along gates ack <id> --note "..."`. If already acked, returns `None`.
  - Added `_record_stop_denial` capturing Stop denials in activity trace (and ledger if bound).
  - Added `stop_denials` and `ack_stop_denials` helpers for querying and settling Stop denials.
- `scripts/alongkit/commands/gates.py`:
  - `_handle_denials`: Supported listing and acknowledging Stop denials from session activity trace even when unbound.
- `tests/test_anti_silent_fallback.py`: Added `TestStopDenialAck` with full lifecycle tests in bound and unbound states.

##### Review Checks
1. Code Quality: Trace-backed Stop denials provide complete traceability and clear acknowledgment flow.
2. Regression: All 40 tests across `test_anti_silent_fallback.py`, `test_subagent_denials.py`, and `test_gates_traceability.py` passed cleanly.
3. Typography: `along sanitize` reported 0 banned characters.

VERDICT: PASS

### Review step-6

#### Review Record: Step 6 - Reconcile 1-line exemption text and enforcement (REQ-6 / Decision D1: Option A)

##### Scope
- `skills/along-init/protocol.md` & `skills/along-init/protocol-reference.md`:
  - Removed misleading sentence claiming 1-line typo/comment edits are exempt from plan approval.
  - Aligned protocol text with strict mechanical gate reality: no unapproved source edits.
- `AGENTS.md` & `.along/PROTOCOL.md`:
  - Regenerated managed ALONG-PROTOCOL blocks via `along init --no-rules --no-git --no-hooks --no-migrate`.
- `tests/test_gates_traceability.py`:
  - Added `TestNoMicroEditExemption` asserting exemption text is absent from protocol sources and managed blocks.

##### Review Checks
1. Code Quality & Consistency: Protocol docs and managed blocks now strictly match runtime enforcement.
2. Regression: 76 tests across `test_context_budget.py`, `test_skills_and_scripts.py`, and `test_gates_traceability.py` passed cleanly.
3. Typography: `along sanitize` reported 0 banned characters across all 1264 files.

VERDICT: PASS

### Review step-7

#### Review Record: Step 7 - Documentation Updates (REQ-7)

##### Scope
- `docs/topic--runtime-hooks-and-gates.md`:
  - Updated section 2.6 to document that Stop branch checks session-attributed writes (`turn_writes` or pending shell diff snapshots).
  - Documented that compiled projections (`closeout.is_compiled_projection`) across any workspace depth are non-plan-governed.
  - Documented trace-backed Stop denial IDs and acknowledgment via `along gates ack`.
- `docs/topic--cli-reference.md`:
  - Updated `along gates denials` and `along gates ack` to note query and settlement of Stop denials without requiring active session bindings.
- `docs/topic--troubleshooting.md`:
  - Documented diagnosis and resolution of `PLAN_REQUIRED ... INDEX.md` false positives on compiled projections.
  - Documented foreign session write isolation and trace-backed Stop denial acknowledgments.
- Documentation Sync & Verification:
  - Executed `along kb-sync`: verified link integrity across 671 links, doc taxonomy contracts, and idempotent index compilation.
  - Executed doc test suites: 71 tests passed cleanly.
  - Checked typography: `along sanitize` reported 0 banned characters.

VERDICT: PASS

### Review step-8

#### Review Record: Step 8 - Full Verification, Independent Review & ADR Registration (REQ-1 - REQ-7)

##### Scope
- Full implementation audit and independent code review session:
  - Subagent `Independent Code Reviewer` audited all working tree modifications against requirements REQ-1 through REQ-7.
  - Aligned `PreToolUse` compiled projection exemption with `Stop` branch in `scripts/alongkit/hooks/predicates.py`.
  - Resolved AST quality gate exception handling in session diff normalization.
  - Resolved context budget limits for 60 ADRs in `scripts/alongkit/budget.py`.
- Automated Test Verification:
  - 128 regression tests executed across `test_gates_traceability.py`, `test_kb_sync.py`, `test_anti_silent_fallback.py`, `test_parallel_closeout.py`, `test_context_budget.py`, and `test_shell_classification.py`: all passed cleanly (0 failures, 0 errors).
- Typography & Sanitation:
  - `along sanitize`: 1273 files scanned, 0 banned characters.
- Decisions & Documentation:
  - Registered `ADR-2026-11-14--stop-gate-session-attribution-and-trace-denials.md` in `.along/DECISIONS/` and synchronized `.along/CONSTRAINTS.md`.
  - All acceptance criteria in `.along/ISSUES/bug--stop-gate-false-positives.md` ticked and verified.

VERDICT: PASS
