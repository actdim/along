---
protocol: along
protocol_version: "4.4.6"
date: 2026-10-06
slug: parallel-session-closeout
agent: claude-code
branch: main
commit: 0b7028c
summary: 'Parallel sessions closed in one step: session event ledger (attribution per issue, telemetry projection), test-run reuse by tree hash, readiness (along session list), closeout approval, along session close (tests once, wrap, commits by attribution, push once, resumable), issue reopen, doctor checks'
issues_advanced: []
issues_completed: [feat--parallel-session-closeout]
decisions: [ADR-2026-10-05--session-event-ledger-feeds-telemetry]
risks_logged: []
spikes_conducted: []
---

# Session: Parallel session closeout

## Summary
Parallel sessions closed in one step: session event ledger (attribution per issue, telemetry projection), test-run reuse by tree hash, readiness (along session list), closeout approval, along session close (tests once, wrap, commits by attribution, push once, resumable), issue reopen, doctor checks

## Decisions
- [ADR-2026-10-05--session-event-ledger-feeds-telemetry]

## Blackboard Record

Execution mode: role-based; plan revision 1; approved: true.

| Step | Title | Status | Retries | Review |
| --- | --- | --- | --- | --- |
| 1 | Session event ledger and attribution (REQ-1, REQ-2) | passed | 0 | yes |
| 2 | One test run per completion (REQ-8) | passed | 0 | yes |
| 3 | Readiness and session list (REQ-3, REQ-4) | passed | 0 | yes |
| 4 | Closeout approval, issue reopen, doctor (REQ-6, REQ-7, REQ-9) | passed | 0 | yes |
| 5 | along session close (REQ-5) | passed | 0 | yes |
| 6 | Scenario and failure tests | passed | 0 | yes |
| 7 | Docs, protocol line, review, reinstall, end to end | passed | 0 | yes |

### Attributed Files

| Path | Kind | Edits | Last edit | Sessions |
| --- | --- | --- | --- | --- |
| `.along/ISSUES/feat--parallel-session-closeout.md` | state | 1 | 2026-10-06T15:23:11Z | claude--7e75283b-4cde-4db6-a1dc-1bd8bbd3ef2f |

### Plan

#### Living Plan: parallel-session-closeout

Title: Close parallel sessions in one step
Revision: 1 - Baseline

##### Execution Mode
Role-Based (along-team). Workspace: inherit. Size: XL (new module, hooks, CLI, commit path,
protocol line; ~10 source files, 2-3 test files, 4 docs).

##### Requirement Traceability
| REQ | Step |
| --- | --- |
| REQ-1 attribution (all paths, path kind, per-slug cap, test results) | 1 |
| REQ-2 durable attribution (blackboard, session log) | 1 |
| REQ-8 one test run per completion (tree hash reuse) | 2 |
| REQ-3 readiness, REQ-4 `along session list` | 3 |
| REQ-6 closeout approval, REQ-7 `issue reopen`, REQ-9 doctor | 4 |
| REQ-5 `along session close` | 5 |
| scenario test, all REQs end to end | 6 |
| docs, protocol line | 7 |

##### Steps
- [ ] Step 1: Session event ledger and attribution (REQ-1, REQ-2; ADR session-event-ledger)
  - `session.record_event(repo_root, key, kind, path=None, ok=None)`: one JSONL line
    `{schema: 1, ts, session, slug, kind, path, path_kind, ok}` appended to the bound slug's
    `.along/.session/<slug>/events.jsonl` (append, no rewrite; works for parallel hook
    processes). `path` is POSIX, relative to the git top. `path_kind`: `state` (`.along/**`),
    `docs` (`docs/**`, root `*.md`), else `source`. Cap per slug (2000 events: oldest edit events
    dropped first, test/plan/approve kept).
  - A failed append is reported on stderr and counted in
    `<diagnostics>/ledger_errors.json` (per slug); readiness marks that issue blocked.
  - Capture points: PostToolUse edit (`record_tool_activity`, every repo path except
    `.along/.session/**` and diagnostics); test runs with result (`trace_test_run`); plan
    recorded, plan approved. Unbound sessions record nothing (their edits show up as
    unattributed changes).
  - Telemetry second step (`along_hook.py`): the PostToolUse span event carries the same record
    (new conventions `along.session.key`, `along.event.kind`, `along.event.path`,
    `along.event.path_kind`); fail-open as today.
  - `session.load_events(repo_root, slug)`, `attributed_files(repo_root, slug)`; the Blackboard
    Record gets an `### Attributed Files` table (path, kind, edits, last edit) so the session log
    keeps the attribution after the purge.
  - The activity trace stays as it is for test-before-stop and the zero-byte audit.
- [ ] Step 2: One test run per completion (REQ-8)
  - `gitgates.tree_hash(repo_root)`: `git write-tree` of the working tree (tracked + untracked,
    not ignored) through a temporary index, leaving out `.along/` and the KB projections that wrap
    regenerates (`docs/INDEX.md`, `docs/decisions/INDEX.md`, `llms.txt`, `llms-full.txt`).
  - Test runs record `{tree_hash, ok, ts}` in `<diagnostics>/test_runs.json` (last 20).
    `gates.run_repository_tests` (wrap, commit, bump) skips the run and says so when the last green
    run has the same hash; `along test` always runs (it is the explicit request) and records.
  - Tests: reuse on same tree, re-run after a source change, no reuse after a red run.
- [ ] Step 3: Readiness and `along session list` (REQ-3, REQ-4)
  - New `scripts/alongkit/closeout.py` (pure functions + one `git status --porcelain -z -uall`):
    `closeout_status(repo_root) -> List[dict]` over every in-progress issue, every binding, every
    orphan blackboard. Per item: sessions (bindings, last event time), attributed files that are
    still changed (exclusive / shared with which issues), last edit vs last green test (ledger),
    acceptance criteria ticked/total (`entities.acceptance_criteria(body)`, new), plan recorded,
    ledger errors; verdict `ready` / `blocked` with reasons. Repository level: unattributed
    changes, staged files, merge/rebase in progress, conflict markers.
  - `along session list [--json]` prints it (nested `.along/` contexts included).
- [ ] Step 4: Closeout approval, `issue reopen`, doctor (REQ-6, REQ-7, REQ-9)
  - `along plan approve --closeout <slug>... | --ready` (only after the user's explicit yes):
    `session.record_closeout_approval(repo_root, key, slugs)` stores
    `closeout: {slugs, approved_at}` in this session's binding (created when the session has
    none). `consume_completion_token` / gc keep a binding that still holds a closeout set.
  - Plan gate: `along commit -i <slug>` passes when the slug is in this session's closeout set
    (next to the token branch); `_held_commit_reason` names "closeout not approved".
  - `along session close` itself is an Along state command (passes the plan gate), so the command
    checks the approval: every selected slug must be in the closeout set (`--dry-run` excepted);
    consumed when the closeout finishes.
  - `along issue reopen <slug>`: `done/` -> `ISSUES/`, `status: open`, `completed` removed,
    sibling links restored, `ISSUES.md` recompiled, in a `FileTransaction`.
  - `along doctor`: bindings older than the gc age, orphan blackboards (exists), in-progress
    issues with no binding.
- [ ] Step 5: `along session close [<slug>...] | --ready [--dry-run] [--push]` (REQ-5)
  1. Refuse during merge / rebase / cherry-pick, with unmerged paths or conflict markers in
     changed files, or with staged files outside the closeout (the commit path commits the whole
     index).
  2. Select issues; not-ready ones are listed with their blockers and left untouched.
  3. Plan the commits BEFORE any wrap (the ledger is purged by wrap) and persist the run in
     `.along/.session/.closeout.json`: files attributed to exactly one selected issue -> one
     commit per issue; files shared by several selected issues -> one combined commit with all
     refs; files also attributed to a non-selected issue or to nobody -> not committed, reported.
  4. Test suite once for the whole closeout (step 2 reuse applies); stop before any wrap when it
     fails. (Deviation from the issue's order "wrap, then tests": tests first changes nothing
     the tests see, and a red suite then leaves every issue untouched.)
  5. Per issue: `execute_wrap(no_verify=True, decisions=[], summary=...)` (archives the
     blackboard with its attributed files, issue done, session log, HISTORY).
  6. Commits via `along_commit.py --paths ... -i <slug>` (subprocess, gates on, test run reused):
     exclusive groups with their issue file move and session log, then combined groups, then the
     projections (`ISSUES.md`, `HISTORY.md`, KB indexes) in the last commit.
  7. `--push`: one `git push` at the end.
  8. Idempotent: a re-run reads `.closeout.json` and continues (wrapped issues not re-wrapped,
     committed groups skipped); the file is removed when the run finished.
- [ ] Step 6: Scenario and failure tests
  - Real git fixture with a bare remote; two simulated sessions on two issues: exclusive files, one
    shared file, one unattributed file, one not-ready issue. Assert: three commits (two exclusive,
    one combined, plus the projections commit), refs, the unrelated change uncommitted, one push;
    idempotent re-run after an injected failure; red tests stop before any wrap; fresh session
    with closeout approval; no approval -> refused; reopen.
- [ ] Step 7: Docs, protocol line, review, reinstall, end to end
  - New `docs/topic--parallel-sessions.md` (guide: working in parallel, attribution, readiness,
    closing out); `docs/topic--cli-reference.md` (`session list|close`, `plan approve
    --closeout`, `issue reopen`, `doctor`); `docs/topic--runtime-hooks-and-gates.md` (ledger, test
    reuse, closeout approval); `docs/topic--session-lifecycle.md` (attributed files).
  - One line in `skills/along-init/protocol.md` "Multi-Agent & Multi-Branch Concurrency" (and the
    repository AGENTS.md block): "Close finished parallel work with `along session list` /
    `along session close --ready` after the user's approval (`along plan approve --closeout`)."
  - Full suite, typography, kb-sync, reinstall, live `along session list` on this repository.

##### Known limits (documented, not solved here)
- Changes made by shell commands (sed, generators, `git mv`) are not attributed; they are reported
  as unattributed and never committed by closeout.
- Readiness cannot know whether a parallel agent is still typing; it shows each session's last
  event time, and the user decides.
- Attribution is per machine plus the session log; a closeout from another machine sees only what
  was archived.

##### Commit scope
Only this ticket's files, via `along commit --paths ... -i parallel-session-closeout`.

### Research

#### Research & Findings: parallel-session-closeout

Verified 2026-10-06 against main after e053888 (completion tokens) and 0b7028c (session records).

##### Target Symbols and Files
- Activity trace (`hooks/predicates.py`): `get_activity_trace_path` (:178, per key under
  diagnostics), `load_activity_trace` (:190, no schema), `save_activity_trace` (:204, swallows
  OSError), `record_tool_activity` (:227): edits on PostToolUse -> `session.trace_event` (all repo
  paths except `.along/.session/**`, diagnostics) and `edited_files` (`is_source_edit` only, global
  `[-200:]`); test runs on PreToolUse, no result. Readers of the activity file:
  `check_test_before_stop`, `along_exec._tests_evidence_line`, `gates.session_edited_files`
  (zero-byte audit), `circuit.py:358`.
- Test results with ok: `gates.run_repository_tests` (gates.py:110) and
  `lifecycle.run_lifecycle_command` -> `session.trace_test_run` (text only).
- Telemetry: `telemetry/conventions.py` has `along.issue.slug`, `along.run.*`, `along.turn.*`,
  `tool.name`, `process.exit.code`; NO `along.session.*`. Hook branch `along_hook.py:424-462`
  (only with `ALONG_RUN_ID` and an active Tracer; after `evaluate_event`, i.e. after the ledger
  capture point).
- Bindings: `session.py` `load/save_binding`, `bind_session`, `record_plan_approval`,
  `completion_tokens` (:398), `consume_completion_token` (:414, deletes an empty binding: must
  also keep a closeout set), `gc_bindings` (:336), `resolve_active_session` (:450).
- Plan gate token branch: `predicates.check_mutation_authorization` :632-636;
  `_held_commit_reason` :692.
- `along_commit.main(argv)` (:85): root from cwd; full suite per call unless `-n` (which skips
  all gates); commits the WHOLE index (pre-staged foreign files leak); one `(refs #slug)`; exits
  via `sys.exit`. `issue done` / wrap move files with write + `os.remove`, so `--paths` needs old
  and new paths (git add of a deleted path stages the deletion).
- entities: `scan_issues` (no body), `find_issue_by_slug`, `CLOSED_ISSUE_STATUSES`,
  `frontmatter.update(..., remove=())`; no acceptance-criteria parser; no `issue reopen`.
- along_exec: `handle_issue_command` dispatch (:630-642), `handle_session_command` (:1025;
  `list`/`close` before :1047), `handle_plan_command` approve (:977), doctor orphans (:1441).
  `session`, `plan`, `issue` are Along state commands: they pass the plan gate.
- git: `proc.git`, `gitgates._git_out`; no `--porcelain -z` helper; no merge/rebase detection
  (`rev-parse --git-path` pattern exists in `gitgates.hooks_dir`); conflict markers only for
  staged diffs (`predicates.find_added_conflict_markers`); no tree-hash helper;
  `repo.diagnostics_dir`.
- `transaction.FileTransaction`: protect/write/rollback/commit, files only.
- Tests to reuse: `tests/test_commit.py::_init_git_repo`, `tests/test_session_records.py`
  (`_post_edit`, `RecordFixture`, `ArchiveFixture`), `tests/test_session_bindings.py`
  (`SessionFixture`). No bare-remote push fixture.
- Docs: `docs/topic--runtime-hooks-and-gates.md` 2.8/2.9, `docs/topic--cli-reference.md`
  (`along session`, `along plan`, `along issue`, `along doctor`), `docs/topic--architecture.md`
  section 4; protocol template `skills/along-init/protocol.md` :21-29 (mirrored in AGENTS.md).

##### Constraints & Risks
- ADR-2026-10-05--session-event-ledger-feeds-telemetry: one versioned event record, PostToolUse
  as the single capture point, ledger first then span event, ledger is the source of truth,
  failed ledger writes reported (readiness blocked), telemetry fail-open.
- Hook cost: no git process in the hook path; ledger append must be O(1) (JSONL append, not a
  rewrite).
- Concurrency: binding / trace files have no locking; a JSONL append per event is the safest
  shape for parallel hook processes.
- Path forms: git top vs context root, Windows case; attribution must normalize to POSIX paths
  relative to the git top before matching `git status`.
- Commit isolation: `along_commit` commits the whole index; closeout must refuse when foreign
  files are already staged.
- Shell-made changes (sed, git mv, generators) are not seen by PostToolUse: they appear as
  unattributed and are never committed by closeout.
- Wraps rewrite `.along/` and KB projections, so a tree hash used for test reuse must leave
  them out or every commit after a wrap re-runs the suite.

##### Architectural Patterns
- Pure readiness functions over files + one `git status` call (closeout.py), CLI as thin glue.
- Approval lives in the session binding (like completion tokens), consumed by the action.
- Idempotent multi-step command with a persisted run state, like `.pending_worktrees.json`.

### Execution Trace

#### Execution Trace: parallel-session-closeout
- 2026-10-06T09:13:08Z denied [require_plan_approval] run_command: Inquiry Read-Only Invariance [gate: require-plan-approval]: No approved plan for issue 'parallel-session-closeout' (phase: 'planning', plan_approved: false)....
- 2026-10-06T11:49:07Z plan approved (along plan approve)
- 2026-10-06T11:49:17Z step 1: pending -> in-progress
- 2026-10-06T11:50:20Z edit scripts/alongkit/session.py (x6)
- 2026-10-06T11:50:20Z edit scripts/along_exec.py
- 2026-10-06T11:50:21Z edit scripts/alongkit/session.py
- 2026-10-06T11:50:22Z edit scripts/alongkit/hooks/predicates.py
- 2026-10-06T11:50:42Z edit scripts/alongkit/telemetry/conventions.py
- 2026-10-06T11:50:42Z edit scripts/alongkit/hooks/predicates.py
- 2026-10-06T11:50:43Z edit scripts/along_hook.py
- 2026-10-06T11:50:55Z edit scripts/alongkit/hooks/models.py
- 2026-10-06T11:50:55Z edit scripts/alongkit/hooks/predicates.py
- 2026-10-06T11:50:56Z edit scripts/along_hook.py
- 2026-10-06T11:51:32Z edit tests/test_parallel_closeout.py
- 2026-10-06T11:54:15Z step 1: in-progress -> passed
- 2026-10-06T11:54:15Z step 2: pending -> in-progress
- 2026-10-06T11:54:46Z edit scripts/alongkit/testruns.py
- 2026-10-06T11:54:47Z edit scripts/alongkit/gates.py (x2)
- 2026-10-06T11:54:48Z edit scripts/alongkit/lifecycle.py (x2)
- 2026-10-06T11:55:00Z edit scripts/alongkit/testruns.py (x2)
- 2026-10-06T11:55:19Z edit tests/test_parallel_closeout.py
- 2026-10-06T11:58:30Z edit tests/test_release_engine.py (x3)
- 2026-10-06T11:58:30Z edit scripts/alongkit/testruns.py
- 2026-10-06T11:58:31Z denied [cli_safety] run_command: CLI Safety Gate Violation: In-place shell edit (sed -i / perl -i) detected in command: sed -i 's/\b_git(/_co_git(/g; s/\b_put(/_co_put(/g' tests/test_paralle...
- 2026-10-06T11:58:39Z edit tests/test_parallel_closeout.py (x2)
- 2026-10-06T11:59:02Z edit scripts/alongkit/testruns.py
- 2026-10-06T12:01:37Z step 2: in-progress -> passed
- 2026-10-06T12:01:37Z step 3: pending -> in-progress
- 2026-10-06T12:02:05Z edit scripts/alongkit/entities.py
- 2026-10-06T12:02:44Z edit scripts/alongkit/closeout.py
- 2026-10-06T12:03:00Z edit scripts/along_exec.py (x2)
- 2026-10-06T12:03:28Z edit scripts/alongkit/closeout.py
- 2026-10-06T12:03:29Z edit tests/test_parallel_closeout.py
- 2026-10-06T12:03:51Z edit scripts/alongkit/closeout.py (x2)
- 2026-10-06T12:03:52Z edit tests/test_parallel_closeout.py (x3)
- 2026-10-06T12:06:45Z step 3: in-progress -> passed
- 2026-10-06T12:06:46Z step 4: pending -> in-progress
- 2026-10-06T12:07:11Z edit scripts/alongkit/session.py
- 2026-10-06T12:07:13Z edit scripts/alongkit/hooks/predicates.py (x2)
- 2026-10-06T12:07:49Z edit scripts/along_exec.py (x6)
- 2026-10-06T12:08:36Z edit tests/test_parallel_closeout.py (x3)
- 2026-10-06T12:11:21Z step 4: in-progress -> passed
- 2026-10-06T12:11:21Z step 5: pending -> in-progress
- 2026-10-06T12:12:24Z edit scripts/alongkit/closeout.py
- 2026-10-06T12:12:39Z edit scripts/along_exec.py (x2)
- 2026-10-06T12:12:53Z edit tests/test_parallel_closeout.py
- 2026-10-06T12:13:18Z step 5: in-progress -> passed
- 2026-10-06T12:13:18Z step 6: pending -> in-progress
- 2026-10-06T12:15:07Z edit tests/test_parallel_closeout.py (x3)
- 2026-10-06T12:15:27Z edit scripts/alongkit/testruns.py (x2)
- 2026-10-06T12:16:19Z edit tests/test_parallel_closeout.py (x2)
- 2026-10-06T12:17:09Z edit scripts/alongkit/closeout.py (x4)
- 2026-10-06T12:17:48Z edit tests/test_parallel_closeout.py (x2)
- 2026-10-06T12:21:23Z step 6: in-progress -> passed
- 2026-10-06T12:21:23Z step 7: pending -> in-progress
- 2026-10-06T12:21:33Z edit skills/along-init/protocol.md
- 2026-10-06T12:21:33Z edit AGENTS.md
- 2026-10-06T12:22:01Z edit docs/topic--cli-reference.md (x5)
- 2026-10-06T12:22:16Z edit docs/topic--runtime-hooks-and-gates.md (x3)
- 2026-10-06T12:22:45Z edit docs/topic--session-lifecycle.md (x2)
- 2026-10-06T12:22:46Z edit docs/topic--parallel-sessions.md
- 2026-10-06T12:22:57Z edit .along/GLOSSARY.md
- 2026-10-06T12:23:14Z edit .along/ISSUES/feat--parallel-session-closeout.md
- 2026-10-06T15:18:47Z edit skills/along-init/protocol.md
- 2026-10-06T15:19:23Z edit AGENTS.md (x3)
- 2026-10-06T15:19:24Z edit skills/along-init/protocol.md
- 2026-10-06T15:19:56Z edit AGENTS.md (x3)
- 2026-10-06T15:23:11Z edit .along/ISSUES/feat--parallel-session-closeout.md
- 2026-10-06T15:26:12Z test pass (along test)
- 2026-10-06T15:26:26Z step 7: in-progress -> passed

### Review step-1

#### Review: Step 1 - Session event ledger and attribution (REQ-1, REQ-2)

VERDICT: PASS

- `session.py`: `bound_blackboard` (shared by trace and ledger, never the 'single' fallback);
  ledger `events.jsonl` per issue blackboard: `append_event` (one JSON line, append only;
  compaction past 400 KB keeps `EVENTS_MAX` = 2000, oldest edits dropped first),
  `record_event` (bound session, path made workspace-relative), `load_events` (tolerant, missing
  `schema` read as 1), `attributed_files`, `path_kind` (state / docs / source), failed writes
  reported on stderr and counted in `<diagnostics>/ledger_errors.json` (`ledger_errors`).
- Capture points: PostToolUse edits (`record_tool_activity`, ledger first, then the trace), test
  runs with result (`trace_test_run`), plan (`record_plan`, with the session key), approval
  (`record_accepted_plan`, `along plan approve`).
- Telemetry: `conventions.py` gains `along.session.key`, `along.event.{schema,kind,path,
  path_kind,ok}` and `ledger_event_attributes`; `HookEvent.ledger_event` carries the record from
  the engine to `along_hook.py`, whose PostToolUse span event now includes it (still fail-open,
  still only with a runner Tracer).
- Session log: `render_blackboard_markdown` adds `### Attributed Files` (path, kind, edits, last
  edit, sessions), so attribution survives the purge.
- The diagnostics activity trace is unchanged (test-before-stop, zero-byte audit, circuit).
- Tests: `tests/test_parallel_closeout.py::TestLedger` (8).

Gate Execution Manifest:
- Workspace Isolation: EXECUTED (PASS) [mode: inherit (default)]
- File Integrity: EXECUTED (PASS)
- Automated Tests: EXECUTED (PASS) [python .along/scripts/test.py -q: 1028 OK]
- Diff Scope Audit: EXECUTED (PASS)
- Requirement Traceability: EXECUTED (PASS) [REQ-1, REQ-2]
- Blast Radius: DEGRADED (PASS) [static search: HookEvent constructors (default added last), record_plan callers, trace_test_run callers; code-review-graph offline]
- Documentation Parity: SKIPPED (docs in step 7)
- Clean Typography: EXECUTED (PASS)

### Review step-2

#### Review: Step 2 - One test run per completion (REQ-8)

VERDICT: PASS (after one fix loop: duplicate helper names `_git`/`_put` in the new test file and
`testruns._git`; missing library-module guard on `testruns.py`; the release engine's
byte-identity snapshot saw the new diagnostics record)

- New `scripts/alongkit/testruns.py`: `tree_hash` (git tree id of the working tree through a
  throwaway index: tracked + untracked, not ignored; `.along/` and KB projections `docs/INDEX.md`,
  `docs/decisions/INDEX.md`, `llms.txt`, `llms-full.txt` left out, `.along/scripts/` kept because
  the test hook defines the run), `record_run` / `load_runs` (`<diagnostics>/test_runs.json`,
  last 20), `green_run_for` (the last run on this tree, only if green).
- `gates.run_repository_tests` (wrap, commit, bump): hashes before running; reuses a green run on
  the same tree and says so; records every run. `lifecycle.run_lifecycle_command` (`along test`)
  always runs and records (tree hashed before the run).
- `tests/test_release_engine.py::snapshot_tree` skips `.along/diagnostics/` (git-ignored,
  machine-local); the byte-identity invariant is about the tree.
- Tests: `TestTestRunReuse` (3, real git fixture with a counting test hook).

Gate Execution Manifest:
- Workspace Isolation: EXECUTED (PASS) [mode: inherit (default)]
- File Integrity: EXECUTED (PASS)
- Automated Tests: EXECUTED (PASS) [python .along/scripts/test.py -q: 1031 OK]
- Diff Scope Audit: EXECUTED (PASS)
- Requirement Traceability: EXECUTED (PASS) [REQ-8]
- Blast Radius: DEGRADED (PASS) [static search: run_repository_tests callers (along_commit, execute_wrap, version bump), run_lifecycle_command; code-review-graph offline]
- Documentation Parity: SKIPPED (docs in step 7)
- Clean Typography: EXECUTED (PASS)

### Review step-3

#### Review: Step 3 - Readiness and session list (REQ-3, REQ-4)

VERDICT: PASS (after one fix loop: a fixture helper named `tested` was collected as a test, and
"test after the last edit" compared one-second timestamps; now ordered by ledger position)

- `entities.acceptance_criteria(body) -> (ticked, total)`: checkboxes under
  `## Acceptance Criteria` only, fences ignored.
- New `scripts/alongkit/closeout.py`: `git_top`, `path_key` (case-insensitive on Windows),
  `git_changes` (`git status --porcelain -z -uall`, renames report both paths),
  `operation_in_progress` (merge / rebase / cherry-pick / revert via `rev-parse --git-path`),
  `conflicted_paths` (unmerged codes, marker lines outside fences), `closeout_status` (items for
  in-progress issues, bound slugs and blackboards in the repository context and every bound
  context: sessions with last event, attributed files mapped to top-relative paths with
  `shared_with`, still-changed files, last edit / last test by ledger order, criteria, plan,
  ledger errors, verdict and reasons; repository: changed, unattributed, staged, operation,
  conflicts), `format_closeout_status`.
- `along session list [--json]`.
- Live run on this repository: lists this issue and the orphan `release-tags-not-pushed`
  blackboard (open issue, no plan); my edits show as unattributed until the reinstall (the
  installed hook predates the ledger).
- Tests: `TestAcceptanceCriteria` (1), `TestReadiness` (6) on a real git fixture.

Gate Execution Manifest:
- Workspace Isolation: EXECUTED (PASS) [mode: inherit (default)]
- File Integrity: EXECUTED (PASS)
- Automated Tests: EXECUTED (PASS) [python .along/scripts/test.py -q: 1038 OK]
- Diff Scope Audit: EXECUTED (PASS)
- Requirement Traceability: EXECUTED (PASS) [REQ-3, REQ-4]
- Blast Radius: DEGRADED (PASS) [new module; entities gains one function; session list subcommand; code-review-graph offline]
- Documentation Parity: SKIPPED (docs in step 7)
- Clean Typography: EXECUTED (PASS)

### Review step-4

#### Review: Step 4 - Closeout approval, issue reopen, doctor (REQ-6, REQ-7, REQ-9)

VERDICT: PASS

- `session.py`: `record_closeout_approval` (binding `closeout: {slugs, approved_at}`, created
  for a session with no binding), `closeout_approved` (lapses after the gc age),
  `consume_closeout_approval`; `_save_or_drop_binding` keeps a binding that still holds a slug,
  a token or a closeout set (`consume_completion_token` uses it).
- Plan gate: `along commit -i <slug>` passes on a completion token or a closeout approval of this
  session; a closeout approval is not a plan approval (source edits stay held); the held-commit
  message names the closeout path.
- CLI: `along plan approve --closeout <slug>... | --closeout --ready` (needs a session id; `--ready`
  takes the ready items of `closeout_status`; nothing to approve -> exit 2).
- `along issue reopen <slug>`: done/ -> ISSUES/, `status: open`, `completed` / `superseded_by` /
  `duplicate_of` removed, sibling links restored, ISSUES.md recompiled, in a FileTransaction;
  refuses when already open or not found.
- `along doctor`: stale bindings (`gc_bindings` dry run) and in-progress issues with no session
  bound, next to the orphan blackboards.
- Tests: `TestCloseoutApproval` (4), `TestReopenAndDoctor` (2).

Gate Execution Manifest:
- Workspace Isolation: EXECUTED (PASS) [mode: inherit (default)]
- File Integrity: EXECUTED (PASS)
- Automated Tests: EXECUTED (PASS) [python .along/scripts/test.py -q: 1044 OK]
- Diff Scope Audit: EXECUTED (PASS)
- Requirement Traceability: EXECUTED (PASS) [REQ-6, REQ-7, REQ-9]
- Blast Radius: DEGRADED (PASS) [static search: consume_completion_token callers (along_commit), check_mutation_authorization, issue dispatch, doctor; code-review-graph offline]
- Documentation Parity: SKIPPED (docs in step 7)
- Clean Typography: EXECUTED (PASS)

### Review step-5

#### Review: Step 5 - along session close (REQ-5)

VERDICT: PASS (end-to-end behavior is exercised by the step 6 scenario tests)

- `closeout.run_closeout(repo_root, keys, ready, dry_run, push, session_key)`:
  1. refuses during merge / rebase / cherry-pick / revert and with conflicts (exit 2);
  2. selects named or `--ready` issues; not-ready ones are listed with blockers and untouched;
  3. refuses with staged files (`along_commit` commits the whole index) and without a closeout
     approval of this session for every selected slug (exit 2, names the command);
  4. plans the groups BEFORE any wrap (`plan_closeout`) and persists the run in
     `.along/.session/.closeout.json`;
  5. tests once (`Closeout Quality Gate`), before any wrap; red -> nothing touched;
  6. wraps each issue (`execute_wrap(no_verify=True, decisions=[])`), records its entity files
     (issue file at both places, today's session log);
  7. commits via `along_commit.py --paths <absolute paths> -i <slug>` (gates on; the test gate
     reuses the closeout's green run): exclusive groups with their entity files, combined groups
     (all refs), then the changed projections;
  8. `--push`: one `git push`;
  9. idempotent: every phase is saved; a re-run resumes; the run file and the closeout approval
     are removed at the end.
- `plan_closeout`: a file goes to the group of exactly the selected issues it is attributed to;
  files also attributed to a non-selected issue are held back; unattributed changes are reported,
  never committed; every selected issue has its own group.
- CLI `along session close <slug>... | --ready [--dry-run] [--push]` (no args resumes a pending
  run). Live dry run on this repository: nothing ready, blockers listed, no writes.
- Tests: `TestCloseoutPlan` (2).

Gate Execution Manifest:
- Workspace Isolation: EXECUTED (PASS) [mode: inherit (default)]
- File Integrity: EXECUTED (PASS)
- Automated Tests: EXECUTED (PASS) [test_parallel_closeout + test_alongkit + test_rules: 127 OK; full suite in step 6]
- Diff Scope Audit: EXECUTED (PASS)
- Requirement Traceability: EXECUTED (PASS) [REQ-5]
- Blast Radius: DEGRADED (PASS) [new code paths only; reuses execute_wrap and along_commit unchanged; code-review-graph offline]
- Documentation Parity: SKIPPED (docs in step 7)
- Clean Typography: EXECUTED (PASS)

### Review step-6

#### Review: Step 6 - Scenario and failure tests

VERDICT: PASS (after two fix loops)

Fix loop 1 (test): the commit-listing helper mixed `--format` and `--name-only` output; rewritten
per commit.
Fix loop 2 (code, found by the scenario): the wraps' KB sync rewrote
`docs/topic--architecture.md` (source-hash front matter); it changed the tree hash (second test
run) and stayed uncommitted. `run_closeout` now fingerprints the changed files before the first
wrap (`content_fingerprint`, one `git hash-object`), computes the wrap byproducts afterwards, carries
the green run over to the wrapped tree only when every byproduct is Along state, docs or a KB
projection (`_is_wrap_byproduct`), and commits those byproducts with the projections. Also
`__pycache__` is left out of the tree hash (the syntax gate writes it).

`tests/test_parallel_closeout.py::TestCloseoutScenario` (7, real git repo + bare remote, three
sessions: alpha and beta ready, a shared file, gamma not ready, an unrelated untracked file):
- full closeout: 4 commits (alpha: its file + issue move + session log; beta likewise; shared
  file with both refs; projections + KB provenance), gamma and the unrelated file uncommitted,
  gamma still in progress, remote equals local after one push, exactly one test run, closeout
  approval consumed, the session log carries `### Attributed Files`;
- resume after a failed commit: a re-run finishes, 4 commits, no issue wrapped twice, run file
  removed;
- red tests: no commit, nothing wrapped;
- no approval / partial approval: exit 2, nothing done;
- named not-ready issue untouched, a file shared with an issue not closed now held back;
- a source change during the wraps: tests run again, the change is not committed;
- dry run writes nothing.

Gate Execution Manifest:
- Workspace Isolation: EXECUTED (PASS) [mode: inherit (default)]
- File Integrity: EXECUTED (PASS)
- Automated Tests: EXECUTED (PASS) [python .along/scripts/test.py -q: 1053 OK]
- Diff Scope Audit: EXECUTED (PASS)
- Requirement Traceability: EXECUTED (PASS) [REQ-1..REQ-9 end to end; scenario acceptance criterion]
- Blast Radius: DEGRADED (PASS) [static search; code-review-graph offline]
- Documentation Parity: SKIPPED (docs in step 7)
- Clean Typography: EXECUTED (PASS)

### Review step-7

#### Review: Step 7 - Docs, protocol line, review, reinstall, end to end

VERDICT: PASS (after one fix loop: AGENTS.md exceeded its 14 KB budget with the protocol line;
by the user's choice the line was shortened and this repository's Project specifics reworded
without dropping a fact, since `test_skills_and_scripts` requires the full skills list there:
14333 B of 14336 B)

- Docs: new `docs/topic--parallel-sessions.md` (guide); `docs/topic--cli-reference.md`
  (`issue reopen`, `session list|close`, `plan approve --closeout`, doctor sessions, commit after
  wrap / closeout, test reuse); `docs/topic--runtime-hooks-and-gates.md` (closeout approval, event
  ledger, test reuse, doctor); `docs/topic--session-lifecycle.md` (`events.jsonl`, pointer).
  Glossary: Session event ledger, Attribution, Closeout, Closeout approval. `along kb-sync`: 16
  articles, links OK. `along sanitize`: clean.
- Protocol line "Parallel Closeout" in `skills/along-init/protocol.md` and AGENTS.md (identical).
- Full suite 1053 OK. Global reinstall. End to end with the installed hooks in this session: the
  issue-file edit became a ledger `edit` record (path_kind state), `along test` a `test` record
  (ok true), `along session list` shows this issue `ready` (criteria 4/4, plan recorded, test after
  the last edit) and the orphan `release-tags-not-pushed` blackboard blocked with reasons.
- Not exercised live: `along session close` on this repository (my earlier edits predate the
  ledger and would stay unattributed); the scenario tests cover it on a real git repo with a remote.

Gate Execution Manifest:
- Workspace Isolation: EXECUTED (PASS) [mode: inherit (default)]
- File Integrity: EXECUTED (PASS)
- Automated Tests: EXECUTED (PASS) [along test: 1053 OK]
- Diff Scope Audit: EXECUTED (PASS) [other sessions' files untouched]
- Requirement Traceability: EXECUTED (PASS) [REQ-1..REQ-9]
- Blast Radius: DEGRADED (PASS) [static search; code-review-graph offline]
- Documentation Parity: EXECUTED (PASS)
- Clean Typography: EXECUTED (PASS)
