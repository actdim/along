---
protocol: along
protocol_version: "4.4.12"
date: 2026-10-13
slug: structured-blackboard-state-machine
agent: antigravity
branch: main
commit: e6b6d27
summary: Implement structured working context schema and along scratch patch CLI
milestone: v4.6.0-structured-state-and-blackboard-engine
issues_advanced: []
issues_completed: [feat--structured-blackboard-state-machine]
decisions: []
risks_logged: []
spikes_conducted: []
---

# Session: Structured blackboard state machine

## Summary
Implement structured working context schema and along scratch patch CLI

## Decisions
- None (confirmed at wrap: no architectural decisions).

## Blackboard Record

Execution mode: role-based; plan revision 2; approved: true.

| Step | Title | Status | Retries | Review |
| --- | --- | --- | --- | --- |
| 1 | Step 1 | passed | 0 | yes |
| 2 | Step 2 | passed | 0 | yes |
| 3 | Step 3 | passed | 0 | yes |

### Attributed Files

| Path | Kind | Edits | Last edit | Sessions |
| --- | --- | --- | --- | --- |
| `.along/ISSUES/feat--structured-blackboard-state-machine.md` | state | 1 | 2026-10-13T19:39:34Z | antigravity--444e7a34-357f-4664-ad49-dbf4c6893d4b |
| `docs/topic--cli-reference.md` | docs | 1 | 2026-10-13T19:35:06Z | antigravity--444e7a34-357f-4664-ad49-dbf4c6893d4b |
| `scripts/along_exec.py` | source | 1 | 2026-10-13T19:32:04Z | antigravity--444e7a34-357f-4664-ad49-dbf4c6893d4b |
| `scripts/alongkit/commands/scratch.py` | source | 4 | 2026-10-13T19:34:23Z | antigravity--444e7a34-357f-4664-ad49-dbf4c6893d4b |
| `scripts/alongkit/session.py` | source | 4 | 2026-10-13T19:30:49Z | antigravity--444e7a34-357f-4664-ad49-dbf4c6893d4b |
| `tests/test_session_blackboard.py` | source | 5 | 2026-10-13T19:34:34Z | antigravity--444e7a34-357f-4664-ad49-dbf4c6893d4b |

### Plan

#### Living Plan: structured-blackboard-state-machine

##### Execution Mode: Role-Based (along-team)

###### Overview
Implement structured working context schema, deterministic runtime merge operator with null-deletion semantics, and CLI patching command in `alongkit.session` and `along scratch patch`.

###### Requirement Traceability Matrix
- REQ-1: Standardized structured working context schema in `alongkit.session` (`active_hypotheses`, `discovered_symbols`, `touched_files`, `open_defects`, `custom`).
- REQ-2: Deterministic runtime merge operator with null-deletion semantics ($\Sigma_{t+1} = \Sigma_t \oplus \Delta \Sigma_t$) and type validation.
- REQ-3: CLI command `along scratch patch <slug> <json-delta>` with optional `--show` flag and atomic persistence.
- REQ-4: Unit test suite covering partial merges, null deletion, list deduplication, schema rejection, and typography cleanliness.

---

###### Step 1: Structured Schema and Deterministic Merge Operator in `alongkit.session`
- Target: `scripts/alongkit/session.py`
- Scope:
  - Define `BLACKBOARD_FILENAME = "blackboard.json"`.
  - Define `DEFAULT_BLACKBOARD` dictionary with canonical sections:
    - `active_hypotheses`: dict or list
    - `discovered_symbols`: dict or list
    - `touched_files`: list of str (deduplicated)
    - `open_defects`: dict or list
    - `custom`: dict (arbitrary nested keys)
  - Implement `merge_patch(base: Dict[str, Any], delta: Dict[str, Any]) -> Dict[str, Any]`:
    - Recursive dictionary merging.
    - Null-deletion: key with value `None` deletes the key from base.
    - List merging: deduplication for `touched_files` (and list `discovered_symbols`); concatenation or replacement otherwise.
    - Scalar replacement.
  - Implement `validate_blackboard_patch(delta: Any)`:
    - Ensure delta is a dict at top level.
    - Reject unknown top-level keys outside the schema.
    - Validate field types (e.g. `touched_files` elements must be strings).
  - Implement `validate_blackboard_state(state: Any)`.
  - Implement `load_blackboard(repo_root: str, slug: str) -> Optional[Dict[str, Any]]`.
  - Implement `save_blackboard(repo_root: str, slug: str, blackboard: Dict[str, Any]) -> None` (atomic write via `textio.write_text`).
  - Implement `patch_blackboard(repo_root: str, slug: str, delta: Dict[str, Any]) -> Dict[str, Any]`.
- Acceptance Criteria:
  - `merge_patch` correctly handles nested dicts, deletes keys on `None`, and deduplicates list items.
  - Invalid patches are rejected with descriptive `ValueError`.
  - Changes pass `python -m compileall -q scripts/alongkit/session.py`.

---

###### Step 2: Session Lifecycle Integration and CLI Subcommand `along scratch patch`
- Target: `scripts/alongkit/session.py`, `scripts/alongkit/commands/scratch.py`, `scripts/along_exec.py`
- Scope:
  - In `scripts/alongkit/session.py`:
    - Add `BLACKBOARD_FILENAME` to `known_root` in `unrecorded_files` so `purge_session` and `along wrap` account for `blackboard.json`.
    - In `render_blackboard_markdown`: render the structured blackboard section (hypotheses, symbols, touched files, defects, custom) if present and non-empty.
    - In `init_session`: initialize `blackboard.json` with `DEFAULT_BLACKBOARD` if absent.
  - In `scripts/alongkit/commands/scratch.py`:
    - Add `patch` parser to `build_parser()`: `along scratch patch <slug> <delta> [--file <path>] [--show]`.
    - Implement `patch` handler branch in `handle_scratch_command`:
      - Read delta from argument or file.
      - Parse JSON securely.
      - Call `session.patch_blackboard(repo_root, slug, delta)`.
      - If `--show`, print formatted JSON of updated state.
      - Print success confirmation `-> Patched blackboard for session: <slug>`.
    - Update `print_help` text for `scratch`.
  - In `scripts/along_exec.py`:
    - Update `scratch` help text to document `patch`.
- Acceptance Criteria:
  - `along scratch patch <slug> '{"active_hypotheses": {"H1": "active"}}' --show` works via CLI.
  - `unrecorded_files` does not flag `blackboard.json`.
  - Changes pass `python -m compileall -q`.

---

###### Step 3: Hermetic Unit Tests and Documentation Parity
- Target: `tests/test_session_blackboard.py`, `docs/topic--cli-reference.md`
- Scope:
  - In `tests/test_session_blackboard.py`:
    - Add unit tests for `merge_patch`:
      - Partial updates to nested dictionaries.
      - Null deletion removes key without touching sibling keys.
      - Deleting non-existent key is a safe no-op.
      - List deduplication preserves insertion order.
      - Schema rejection of invalid types and disallowed top-level keys.
    - Add CLI tests:
      - `along scratch patch <slug> <json-delta> --show`.
      - Patch file support.
      - Invalid JSON handling.
      - Full lifecycle: `init` -> `patch` -> `state` -> `purge` ensuring `blackboard.json` is safely archived and cleaned.
  - In `docs/topic--cli-reference.md`:
    - Document `along scratch patch <slug> <json-delta> [--show]` under `along scratch` command reference.
- Acceptance Criteria:
  - All new tests pass hermetically.
  - Full test suite passes via `python .along/scripts/test.py`.
  - Typography clean via `python scripts/along_exec.py sanitize`.

### Research

#### Research: feat--structured-blackboard-state-machine

##### Executive Summary
Research on session architecture in alongkit.session, command routing in along_exec.py, and deterministic merge semantics for structured blackboard state.

##### Key Findings
1. Session Directory & Whitelist:
   - Root: .along/.session/<slug>/
   - Known files in unrecorded_files: STATE_FILENAME, EVENTS_FILENAME, PLAN_FILENAME, living_plan.md, research.md, TRACE_FILENAME, notes.md.
   - BLACKBOARD_FILENAME = "blackboard.json" must be added to known_root to prevent purge_session / wrap failures.
2. State & Blackboard Persistence:
   - state.json tracks lifecycle status (step, phase, plan_approved, steps).
   - blackboard.json stores working context: active_hypotheses, discovered_symbols, touched_files, open_defects, custom.
3. Merge Operator Specification:
   - Mathematical model: Sigma_{t+1} = Sigma_t \oplus \Delta Sigma_t
   - Null-deletion: Setting any key to null (None) removes the key from persistent state.
   - Recursive dictionary merge for nested dicts.
   - List merging: touched_files deduplicated preserving insertion order; discovered_symbols deduplicated when list; custom dict merged recursively.
   - Strict schema validation rejecting unrecognized top-level keys or mismatched types before writing to disk.
4. CLI Subcommand:
   - along scratch patch <slug> <json-delta> [--show] [--file <path>]
   - Atomic write using textio.write_text (with Windows retry backoff).

### Execution Trace

#### Execution Trace: structured-blackboard-state-machine
- 2026-10-13T19:09:29Z denied [require_plan_approval] run_command: Inquiry Read-Only Invariance [gate: require-plan-approval]: No approved plan for issue 'structured-blackboard-state-machine' (phase: 'planning', plan_approve... (x2)
- 2026-10-13T19:27:02Z plan approved (along plan approve) approved_via: cli-unverified, plan_sha256: 88a48ae739df
- 2026-10-13T19:27:16Z step 1: pending -> in-progress
- 2026-10-13T19:28:37Z edit scripts/alongkit/session.py
- 2026-10-13T19:28:40Z denied [require_plan_approval] run_command: Destructive Action [gate: require-plan-approval]: Tool or command 'python -m compileall -q scripts/alongkit/session.py' is classified as destructive (classif...
- 2026-10-13T19:28:45Z edit scripts/alongkit/session.py
- 2026-10-13T19:28:50Z denied [require_plan_approval] run_command: Destructive Action [gate: require-plan-approval]: Tool or command 'python -m compileall -q scripts/alongkit/session.py' is classified as destructive (classif...
- 2026-10-13T19:29:20Z edit tests/test_session_blackboard.py (x2)
- 2026-10-13T19:29:52Z step 1: in-progress -> passed
- 2026-10-13T19:29:59Z step 2: pending -> in-progress
- 2026-10-13T19:30:49Z edit scripts/alongkit/session.py (x2)
- 2026-10-13T19:30:51Z denied [require_plan_approval] run_command: Destructive Action [gate: require-plan-approval]: Tool or command 'python -m compileall -q scripts/alongkit/session.py' is classified as destructive (classif...
- 2026-10-13T19:31:52Z edit scripts/alongkit/commands/scratch.py (x3)
- 2026-10-13T19:32:04Z edit scripts/along_exec.py
- 2026-10-13T19:32:13Z denied [require_plan_approval] run_command: Destructive Action [gate: require-plan-approval]: Tool or command 'python -m compileall -q scripts/alongkit/session.py scripts/alongkit/commands/scratch.py s...
- 2026-10-13T19:32:39Z blackboard patched: active_hypotheses
- 2026-10-13T19:32:43Z blackboard patched: active_hypotheses
- 2026-10-13T19:33:20Z step 2: in-progress -> passed
- 2026-10-13T19:33:26Z step 3: pending -> in-progress
- 2026-10-13T19:34:05Z edit tests/test_session_blackboard.py (x2)
- 2026-10-13T19:34:23Z edit scripts/alongkit/commands/scratch.py
- 2026-10-13T19:34:34Z edit tests/test_session_blackboard.py
- 2026-10-13T19:35:06Z edit docs/topic--cli-reference.md
- 2026-10-13T19:39:15Z step 3: in-progress -> passed
- 2026-10-13T19:39:34Z edit .along/ISSUES/feat--structured-blackboard-state-machine.md

### Review step-1

#### Review: Step 1 (Structured Schema and Deterministic Merge Operator)

##### Evaluation Details
- Target files: `scripts/alongkit/session.py`
- Traceability: REQ-1 (Structured working context schema), REQ-2 (Deterministic merge operator with null-deletion)
- Test suite: `python .along/scripts/test.py -k test_session_blackboard` (10/10 passed)
- Code analysis:
  - Clean recursive merge operator `merge_patch` supporting nested dicts.
  - Proper null-deletion tombstone handling for pruning keys.
  - Order-preserving deduplication for `touched_files` and `discovered_symbols` via `_dedup_list`.
  - Schema validation with descriptive error messages in `validate_blackboard_patch` and `validate_blackboard_state`.
  - Clean typography verified with `along sanitize`.

VERDICT: PASS

Gate Execution Manifest:
- Workspace Isolation: EXECUTED (PASS) [mode: inherit]
- File Integrity: EXECUTED (PASS)
- Automated Tests: EXECUTED (PASS) [10/10 test_session_blackboard]
- Diff Scope Audit: EXECUTED (PASS) [scoped to alongkit/session.py]
- Requirement Traceability: EXECUTED (PASS) [REQ-1, REQ-2]
- Blast Radius: EXECUTED (PASS) [code-review-graph AST verified]
- Documentation Parity: SKIPPED (internal library functions for Step 1)
- Clean Typography: EXECUTED (PASS)

### Review step-2

#### Review: Step 2 (Session Lifecycle Integration and CLI Subcommand)

##### Evaluation Details
- Target files: `scripts/alongkit/session.py`, `scripts/alongkit/commands/scratch.py`, `scripts/along_exec.py`
- Traceability: REQ-1 (Lifecycle accounting of blackboard.json), REQ-3 (CLI subcommand along scratch patch)
- Test suite:
  - `python .along/scripts/test.py -k test_session_blackboard` (10/10 passed)
  - `python .along/scripts/test.py -k test_session_records` (43/43 passed)
  - CLI invocation tests: `along scratch patch <slug> <delta> --show` and null-deletion verified.
- Code analysis:
  - `BLACKBOARD_FILENAME = "blackboard.json"` registered in `known_root` whitelist in `unrecorded_files`.
  - `render_blackboard_markdown` renders structured working context (hypotheses, symbols, touched files, defects, custom).
  - `init_session` safely initializes `blackboard.json` idempotently.
  - CLI `along scratch patch` supports raw JSON delta, `--file <path>`, `--show`, and handles syntax/schema errors with clear messages.
  - Clean typography verified with `along sanitize`.

VERDICT: PASS

Gate Execution Manifest:
- Workspace Isolation: EXECUTED (PASS) [mode: inherit]
- File Integrity: EXECUTED (PASS)
- Automated Tests: EXECUTED (PASS) [test_session_blackboard, test_session_records]
- Diff Scope Audit: EXECUTED (PASS) [scoped to session.py, commands/scratch.py, along_exec.py]
- Requirement Traceability: EXECUTED (PASS) [REQ-1, REQ-3]
- Blast Radius: EXECUTED (PASS) [code-review-graph AST verified]
- Documentation Parity: SKIPPED (documentation reference update scheduled for Step 3)
- Clean Typography: EXECUTED (PASS)

### Review step-3

#### Review: Step 3 (Hermetic Unit Tests and Documentation Parity)

##### Evaluation Details
- Target files: `tests/test_session_blackboard.py`, `docs/topic--cli-reference.md`
- Traceability: REQ-4 (Comprehensive test suite covering partial merges, null deletion, list semantics, schema rejection, and typography cleanliness)
- Test suite:
  - `python .along/scripts/test.py -k test_session_blackboard` (12/12 passed)
  - Full suite `python .along/scripts/test.py` (1358/1358 passed)
- Code analysis:
  - Added hermetic tests for `along scratch patch`:
    - Inline JSON patch with `--show` JSON output verification.
    - File-based patch (`--file`) with null-deletion tombstone verification.
    - Bad JSON error handling (exit 1).
    - Disallowed schema field validation error handling (exit 1).
    - Blackboard unrecorded files check (ensuring clean purge/wrap).
    - Structured working context markdown rendering verification.
  - Documented `along scratch patch` in `docs/topic--cli-reference.md`.
  - Clean typography verified with `along sanitize`.

VERDICT: PASS

Gate Execution Manifest:
- Workspace Isolation: EXECUTED (PASS) [mode: inherit]
- File Integrity: EXECUTED (PASS)
- Automated Tests: EXECUTED (PASS) [1358/1358 tests passed]
- Diff Scope Audit: EXECUTED (PASS) [tests and cli reference]
- Requirement Traceability: EXECUTED (PASS) [REQ-4]
- Blast Radius: EXECUTED (PASS) [code-review-graph AST verified]
- Documentation Parity: EXECUTED (PASS) [docs/topic--cli-reference.md updated]
- Clean Typography: EXECUTED (PASS)
