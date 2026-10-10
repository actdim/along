---
protocol: along
protocol_version: "4.4.8"
date: 2026-10-09
slug: wrapped-work-left-uncommitted
agent: antigravity
branch: main
commit: d1c8c7c
summary: Warn on uncommitted wrapped work, group in session list and doctor, support done session close
milestone: v4.5.0-multi-user-merge-automation
issues_advanced: []
issues_completed: [bug--wrapped-work-left-uncommitted]
decisions: []
risks_logged: []
spikes_conducted: []
---

# Session: Wrapped work left uncommitted

## Summary
Warn on uncommitted wrapped work, group in session list and doctor, support done session close

## Decisions
- None (confirmed at wrap: no architectural decisions).

## Blackboard Record

Execution mode: role-based; plan revision 1; approved: true.

| Step | Title | Status | Retries | Review |
| --- | --- | --- | --- | --- |
| 1 | Warn on uncommitted attributed files in along wrap | passed | 0 | yes |
| 2 | Group uncommitted changes by done issue in along session list and doctor | passed | 0 | yes |
| 3 | Enable along session close on done slugs | passed | 0 | yes |
| 4 | Stop-gate warning and full regression verification | passed | 0 | yes |

### Attributed Files

| Path | Kind | Edits | Last edit | Sessions |
| --- | --- | --- | --- | --- |
| `.along/ISSUES/bug--wrapped-work-left-uncommitted.md` | state | 1 | 2026-10-09T19:18:26Z | antigravity--b6382f35-542e-41ee-99ab-57b0e2413189 |
| `docs/topic--cli-reference.md` | docs | 2 | 2026-10-09T19:16:51Z | antigravity--b6382f35-542e-41ee-99ab-57b0e2413189 |
| `docs/topic--declarative-gates-and-traceability.md` | docs | 2 | 2026-10-09T19:16:02Z | antigravity--b6382f35-542e-41ee-99ab-57b0e2413189 |
| `docs/topic--parallel-sessions.md` | docs | 2 | 2026-10-09T19:16:33Z | antigravity--b6382f35-542e-41ee-99ab-57b0e2413189 |
| `docs/topic--runtime-hooks-and-gates.md` | docs | 2 | 2026-10-09T19:17:12Z | antigravity--b6382f35-542e-41ee-99ab-57b0e2413189 |
| `scripts/along_exec.py` | source | 1 | 2026-10-09T19:01:21Z | antigravity--b6382f35-542e-41ee-99ab-57b0e2413189 |
| `scripts/alongkit/closeout.py` | source | 4 | 2026-10-09T19:05:31Z | antigravity--b6382f35-542e-41ee-99ab-57b0e2413189 |
| `scripts/alongkit/hooks/config.py` | source | 1 | 2026-10-09T19:08:02Z | antigravity--b6382f35-542e-41ee-99ab-57b0e2413189 |
| `scripts/alongkit/hooks/default_gates.yaml` | source | 1 | 2026-10-09T19:08:14Z | antigravity--b6382f35-542e-41ee-99ab-57b0e2413189 |
| `scripts/alongkit/hooks/predicates.py` | source | 2 | 2026-10-09T19:09:25Z | antigravity--b6382f35-542e-41ee-99ab-57b0e2413189 |
| `scripts/alongkit/lifecycle.py` | source | 2 | 2026-10-09T18:57:12Z | antigravity--b6382f35-542e-41ee-99ab-57b0e2413189 |
| `tests/test_lifecycle_wrap.py` | source | 4 | 2026-10-09T18:58:58Z | antigravity--b6382f35-542e-41ee-99ab-57b0e2413189 |
| `tests/test_parallel_closeout.py` | source | 2 | 2026-10-09T19:05:52Z | antigravity--b6382f35-542e-41ee-99ab-57b0e2413189 |
| `tests/test_session_records.py` | source | 1 | 2026-10-09T19:08:39Z | antigravity--b6382f35-542e-41ee-99ab-57b0e2413189 |

### Plan

#### Living Plan: bug--wrapped-work-left-uncommitted

##### Execution Mode
Role-Based (along-team)

##### Revision 1 (Baseline)

###### Requirement Traceability Matrix
- REQ-1 -> Step 1: `along wrap` prints warning and exact `along commit -i <slug> --paths ...` when files remain uncommitted
- REQ-2 -> Step 2: `along session list` and `along doctor` group unattributed changes by wrapped/done issue
- REQ-3 -> Step 3: `along session close <slug>` accepts done issue and commits its attributed files from session log
- REQ-4 -> Step 4: Optional Stop-gate warning for session that wrapped but did not commit; end-to-end test and validation

---

##### Steps

###### Step 1: Warn on Uncommitted Attributed Files in `along wrap` (REQ-1)
- **Target Files**:
  - `scripts/alongkit/lifecycle.py`: In `execute_wrap`, after writing session log and before/after purge, compare attributed files + entity files against `closeout.git_changes(repo_root)`. If uncommitted files remain, emit warning and suggested `along commit -i <slug> --paths <p1> <p2> ...` command.
  - `tests/test_lifecycle_wrap.py`: Add test verifying wrap with uncommitted files outputs the warning and exact commit command.
- **Acceptance Criteria**:
  - `along wrap` exits with code 0 while printing warning and suggested commit command when attributed/entity files are uncommitted.
  - Test passes hermetically.

###### Step 2: Group Uncommitted Changes by Done Issue in `along session list` and `along doctor` (REQ-2)
- **Target Files**:
  - `scripts/alongkit/closeout.py`:
    - Add `done_issues_attribution(repo_root)` helper parsing session logs in `.along/SESSIONS/` (`### Attributed Files` tables) and done issues in `.along/ISSUES/done/`.
    - In `closeout_status(repo_root)`: correlate `git_changes` against done issues' attribution and group under `wrapped` / `done_issues`. Only unassociated files remain in `unattributed`.
    - In `format_closeout_status(status)`: render uncommitted changes grouped under each wrapped issue.
  - `scripts/along_exec.py`:
    - In `handle_doctor_command`, check uncommitted files against done issues attribution and emit warning with commit suggestions.
  - `tests/test_parallel_closeout.py`: Add tests for grouping uncommitted changes by done issue.
- **Acceptance Criteria**:
  - `along session list` groups uncommitted files under wrapped issue headings.
  - `along doctor` reports uncommitted files belonging to wrapped issues as a warning.

###### Step 3: Enable `along session close` on Done Slugs (REQ-3)
- **Target Files**:
  - `scripts/alongkit/closeout.py`:
    - In `run_closeout`, allow resolving done issue slugs when provided in `keys`.
    - Retrieve attributed files from session log and construct closeout item.
    - Update `_entity_files` to locate the actual session log for the issue even across dates.
    - Run Closeout Quality Gate and commit attributed files via `_commit()`.
  - `tests/test_parallel_closeout.py`: Add test verifying `along session close <done-slug>` commits attributed files after blackboard purge.
- **Acceptance Criteria**:
  - `along session close <slug>` succeeds for an issue already in `done/`, committing its attributed files and projections.

###### Step 4: Optional Stop-Gate Warning & Full Verification (REQ-4)
- **Target Files**:
  - `scripts/alongkit/hooks/predicates.py`: Implement non-blocking warning in `check_wrap_before_stop` or `check_uncommitted_wrap_before_stop` alerting when session completed work with uncommitted files.
  - `scripts/alongkit/hooks/default_gates.yaml`: Register `wrapped_work_uncommitted` Stop gate (default shadow/warning mode).
  - `tests/test_hook_activation.py` / `tests/test_parallel_closeout.py`: Verify non-blocking warning behavior.
  - Run full test suite (`python .along/scripts/test.py`).
  - Run docs blast radius check and `/along-kb-sync`.
- **Acceptance Criteria**:
  - Stop gate warns without blocking when wrapped files remain uncommitted.
  - Zero test failures across whole test suite.

### Research

#### Scout Research: bug--wrapped-work-left-uncommitted

##### 1. Problem Summary
When parallel sessions wrap issues (issue moved to `done/`, session log written) and stop without committing:
- `along wrap` doesn't inspect git status or warn that attributed files are left uncommitted.
- `along session list` and `along doctor` show the dirty files under "unattributed changes" because the wrapped issue is no longer "in-progress" and its blackboard is gone.
- `along session close` rejects the done issue because it's not in-progress, and refuses to commit unattributed changes.
- Stop gates do not alert that an issue was wrapped but uncommitted.

##### 2. Affected Components & Architecture
1. `scripts/alongkit/lifecycle.py`:
   - `execute_wrap`: Add post-wrap check comparing attributed files (`session.attributed_files` + entity files) against `closeout.git_changes(repo_root)`. If any remain dirty, emit warning with exact command: `along commit -i <slug> --paths ...`.
2. `scripts/alongkit/closeout.py`:
   - Add parsing/discovery of attributed files from done issues' session logs in `.along/SESSIONS/`.
   - Update `closeout_status` to attribute uncommitted changes to done issues whose session logs list those paths under `### Attributed Files`.
   - Update `format_closeout_status` to display uncommitted changes grouped under wrapped/done issues.
   - Update `run_closeout` and `_plan_item` to support closing/committing a done issue by reading its attributed files from the session log even after blackboard purge.
3. `scripts/along_exec.py`:
   - In `handle_doctor_command`, cross-reference dirty git status files with done issue session logs, warning if uncommitted files belong to completed issues.
4. `scripts/alongkit/hooks/predicates.py` / `default_gates.yaml`:
   - Implement optional non-blocking warning gate or check in `wrap_before_stop` or dedicated predicate for uncommitted wrapped issues (when session has completion tokens or uncommitted files).
5. Tests:
   - `tests/test_parallel_closeout.py`
   - `tests/test_lifecycle_wrap.py`

### Execution Trace

#### Execution Trace: wrapped-work-left-uncommitted
- 2026-10-09T17:31:36Z denied [require_plan_approval] run_command: Inquiry Read-Only Invariance [gate: require-plan-approval]: No approved plan for issue 'wrapped-work-left-uncommitted' (phase: 'planning', plan_approved: fal... (x9)
- 2026-10-09T18:54:29Z plan approved (along plan approve)
- 2026-10-09T18:54:55Z step 1: pending -> in-progress
- 2026-10-09T18:57:12Z edit scripts/alongkit/lifecycle.py (x2)
- 2026-10-09T18:58:58Z edit tests/test_lifecycle_wrap.py (x4)
- 2026-10-09T18:59:33Z step 1: in-progress -> passed
- 2026-10-09T18:59:36Z step 2: pending -> in-progress
- 2026-10-09T19:01:08Z edit scripts/alongkit/closeout.py (x2)
- 2026-10-09T19:01:21Z edit scripts/along_exec.py
- 2026-10-09T19:02:52Z edit tests/test_parallel_closeout.py
- 2026-10-09T19:04:02Z step 2: in-progress -> passed
- 2026-10-09T19:04:08Z step 3: pending -> in-progress
- 2026-10-09T19:05:31Z edit scripts/alongkit/closeout.py (x2)
- 2026-10-09T19:05:52Z edit tests/test_parallel_closeout.py
- 2026-10-09T19:06:52Z step 3: in-progress -> passed
- 2026-10-09T19:06:56Z step 4: pending -> in-progress
- 2026-10-09T19:07:52Z edit scripts/alongkit/hooks/predicates.py
- 2026-10-09T19:08:02Z edit scripts/alongkit/hooks/config.py
- 2026-10-09T19:08:14Z edit scripts/alongkit/hooks/default_gates.yaml
- 2026-10-09T19:08:39Z edit tests/test_session_records.py
- 2026-10-09T19:09:25Z edit scripts/alongkit/hooks/predicates.py
- 2026-10-09T19:16:02Z edit docs/topic--declarative-gates-and-traceability.md (x2)
- 2026-10-09T19:16:33Z edit docs/topic--parallel-sessions.md (x2)
- 2026-10-09T19:16:51Z edit docs/topic--cli-reference.md (x2)
- 2026-10-09T19:17:12Z edit docs/topic--runtime-hooks-and-gates.md (x2)
- 2026-10-09T19:17:44Z step 4: in-progress -> passed
- 2026-10-09T19:18:26Z edit .along/ISSUES/bug--wrapped-work-left-uncommitted.md
- 2026-10-09T19:19:31Z denied [cli_safety] run_command: CLI Safety Gate Violation: Ad-hoc internal module probe via python -c [gate: cli_safety] (use Along CLI, code search tools, or a scratch/ script) detected in...
- 2026-10-09T19:20:28Z test pass (along test)

### Review step-1

#### Review Step 1: Warn on Uncommitted Attributed Files in along wrap (REQ-1)

VERDICT: PASS

##### Checks
1. File Integrity: PASS. Modified files verified non-zero size.
2. Automated Tests: PASS. `test_lifecycle_wrap.py` passed (18/18 tests green).
3. Diff & Scope Audit: PASS. Changes localized to `_warn_uncommitted_work` in `scripts/alongkit/lifecycle.py` and test verification.
4. Requirement Traceability: PASS. Fulfills REQ-1 (wrap emits warning with exact `along commit -i <slug> --paths ...` command).
5. Blast Radius: EXECUTED (PASS). `along graph-impact scripts/alongkit/lifecycle.py` healthy, 0 impacted nodes within 2 hops.
6. Clean Typography: PASS. Standard UTF-8 ASCII.

Gate Execution Manifest:
- Workspace Isolation: EXECUTED (PASS) [mode: inherit (default)]
- File Integrity: EXECUTED (PASS)
- Automated Tests: EXECUTED (PASS) [test_lifecycle_wrap.py]
- Diff Scope Audit: EXECUTED (PASS)
- Requirement Traceability: EXECUTED (PASS) [REQ-1]
- Blast Radius: EXECUTED (PASS) [code-review-graph]
- Documentation Parity: SKIPPED (internal warning logic)
- Clean Typography: EXECUTED (PASS)

### Review step-2

#### Review Step 2: Group Uncommitted Changes by Done Issue in along session list and doctor (REQ-2)

VERDICT: PASS

##### Checks
1. File Integrity: PASS. Modified files verified non-zero size.
2. Automated Tests: PASS. `test_parallel_closeout.py` passed (36/36 tests green).
3. Diff & Scope Audit: PASS. `done_issues_attribution` implemented, `closeout_status`, `format_closeout_status`, and `handle_doctor_command` updated to group uncommitted changes by wrapped/done issue.
4. Requirement Traceability: PASS. Fulfills REQ-2 (`along session list` and `along doctor` group uncommitted changes by done issue).
5. Blast Radius: EXECUTED (PASS). `along graph-impact scripts/alongkit/closeout.py` healthy, 0 nodes impacted within 2 hops.
6. Clean Typography: PASS. Standard UTF-8 ASCII.

Gate Execution Manifest:
- Workspace Isolation: EXECUTED (PASS) [mode: inherit (default)]
- File Integrity: EXECUTED (PASS)
- Automated Tests: EXECUTED (PASS) [test_parallel_closeout.py]
- Diff Scope Audit: EXECUTED (PASS)
- Requirement Traceability: EXECUTED (PASS) [REQ-2]
- Blast Radius: EXECUTED (PASS) [code-review-graph]
- Documentation Parity: SKIPPED (covered in final wrap documentation review)
- Clean Typography: EXECUTED (PASS)

### Review step-3

#### Review Step 3: Enable along session close on done slugs (REQ-3)

VERDICT: PASS

##### Checks
1. File Integrity: PASS. All modified files non-empty.
2. Automated Tests: PASS. `test_parallel_closeout.py` passed (37/37 tests green, including `test_closeout_wrapped_issue_commits_attributed_files`).
3. Diff & Scope Audit: PASS. `_entity_files` and `run_closeout` updated to resolve wrapped/done issue attribution, construct ready items, and commit attributed + entity files via `along commit`.
4. Requirement Traceability: PASS. Fulfills REQ-3 (`along session close` accepts done slug and commits its files).
5. Blast Radius: EXECUTED (PASS). `along graph-impact scripts/alongkit/closeout.py` healthy, 0 nodes impacted within 2 hops.
6. Clean Typography: PASS. Standard UTF-8 ASCII.

Gate Execution Manifest:
- Workspace Isolation: EXECUTED (PASS) [mode: inherit (default)]
- File Integrity: EXECUTED (PASS)
- Automated Tests: EXECUTED (PASS) [test_parallel_closeout.py]
- Diff Scope Audit: EXECUTED (PASS)
- Requirement Traceability: EXECUTED (PASS) [REQ-3]
- Blast Radius: EXECUTED (PASS) [code-review-graph]
- Documentation Parity: SKIPPED (covered in final step documentation review)
- Clean Typography: EXECUTED (PASS)

### Review step-4

#### Review Step 4: Stop-gate warning and full regression verification (REQ-4)

VERDICT: PASS

##### Checks
1. File Integrity: PASS. All modified files non-empty.
2. Automated Tests: PASS. Full repository test suite passed (1147/1147 tests green, skipped=2). Target test `test_uncommitted_wrap_before_stop_warns` in `tests/test_session_records.py` green.
3. Diff & Scope Audit: PASS. `check_uncommitted_wrap_before_stop` in `scripts/alongkit/hooks/predicates.py`, default gate `wrapped_work_uncommitted` with `HookMode.SHADOW` in `scripts/alongkit/hooks/config.py` and `scripts/alongkit/hooks/default_gates.yaml`.
4. Requirement Traceability: PASS. Fulfills REQ-4 (non-blocking stop gate warning in shadow mode by default when an issue wraps without committing attributed files).
5. Blast Radius: EXECUTED (PASS). Graph impact evaluated on `scripts/alongkit/hooks/predicates.py`. Full test suite clean.
6. Documentation Parity: PASS. `docs/topic--declarative-gates-and-traceability.md`, `docs/topic--parallel-sessions.md`, `docs/topic--cli-reference.md`, `docs/topic--runtime-hooks-and-gates.md` updated and synchronized via `along kb sync`. `along hook verify` confirms bidirectional anchor (30/31 active and anchored).
7. Clean Typography: PASS. Verified via `along sanitize` (816 files clean, 0 banned characters).

Gate Execution Manifest:
- Workspace Isolation: EXECUTED (PASS) [mode: inherit (default)]
- File Integrity: EXECUTED (PASS)
- Automated Tests: EXECUTED (PASS) [full test suite 1147 tests]
- Diff Scope Audit: EXECUTED (PASS)
- Requirement Traceability: EXECUTED (PASS) [REQ-4]
- Blast Radius: EXECUTED (PASS) [code-review-graph]
- Documentation Parity: EXECUTED (PASS) [docs/ updated and kb-synced]
- Clean Typography: EXECUTED (PASS)
