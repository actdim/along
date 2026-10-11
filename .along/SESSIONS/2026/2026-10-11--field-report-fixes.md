---
protocol: along
protocol_version: "4.4.9"
date: 2026-10-11
slug: field-report-fixes
agent: claude-code
branch: main
commit: b6e22fb
summary: Fixed 8 field-reported gate/entity defects and added gate tiers, recorded human-authorized bypasses and gate stats
milestone: v4.5.0-multi-user-merge-automation
issues_advanced: []
issues_completed: [task--field-report-fixes]
decisions: [ADR-2026-10-11--gate-friction-fixes]
risks_logged: []
spikes_conducted: []
---

# Session: Field report fixes

## Summary
Fixed 8 field-reported gate/entity defects and added gate tiers, recorded human-authorized bypasses and gate stats

## Decisions
- [ADR-2026-10-11--gate-friction-fixes]

## Blackboard Record

Execution mode: direct; plan revision 1; approved: true.

### Attributed Files

| Path | Kind | Edits | Last edit | Sessions |
| --- | --- | --- | --- | --- |
| `.along/DECISIONS/ADR-2026-10-11--gate-friction-fixes.md` | state | 1 | 2026-10-11T17:41:08Z | claude--1f15c9eb-976b-4360-b2de-82fefae47317 |
| `.along/ISSUES/bug--plan-approval-self-and-lost.md` | state | 1 | 2026-10-11T17:45:52Z | claude--1f15c9eb-976b-4360-b2de-82fefae47317 |
| `.along/ISSUES/feat--gate-friction-and-bypass-accountability.md` | state | 1 | 2026-10-11T17:45:53Z | claude--1f15c9eb-976b-4360-b2de-82fefae47317 |
| `dashboard/core/collector.py` | source | 2 | 2026-10-11T17:18:41Z | claude--1f15c9eb-976b-4360-b2de-82fefae47317 |
| `dashboard/core/graph.py` | source | 3 | 2026-10-11T17:09:34Z | claude--1f15c9eb-976b-4360-b2de-82fefae47317 |
| `dashboard/schemas/metrics.py` | source | 1 | 2026-10-11T17:18:41Z | claude--1f15c9eb-976b-4360-b2de-82fefae47317 |
| `docs/topic--architecture.md` | docs | 1 | 2026-10-11T17:40:02Z | claude--1f15c9eb-976b-4360-b2de-82fefae47317 |
| `docs/topic--cli-reference.md` | docs | 18 | 2026-10-11T17:38:50Z | claude--1f15c9eb-976b-4360-b2de-82fefae47317 |
| `docs/topic--domain-model.md` | docs | 1 | 2026-10-11T17:40:32Z | claude--1f15c9eb-976b-4360-b2de-82fefae47317 |
| `docs/topic--runtime-hooks-and-gates.md` | docs | 6 | 2026-10-11T17:39:41Z | claude--1f15c9eb-976b-4360-b2de-82fefae47317 |
| `docs/topic--session-lifecycle.md` | docs | 2 | 2026-10-11T17:39:55Z | claude--1f15c9eb-976b-4360-b2de-82fefae47317 |
| `docs/topic--setup-and-workflow.md` | docs | 3 | 2026-10-11T17:40:15Z | claude--1f15c9eb-976b-4360-b2de-82fefae47317 |
| `scripts/along_commit.py` | source | 10 | 2026-10-11T17:26:13Z | claude--1f15c9eb-976b-4360-b2de-82fefae47317 |
| `scripts/along_exec.py` | source | 19 | 2026-10-11T17:35:08Z | claude--1f15c9eb-976b-4360-b2de-82fefae47317 |
| `scripts/along_hook.py` | source | 1 | 2026-10-11T17:21:11Z | claude--1f15c9eb-976b-4360-b2de-82fefae47317 |
| `scripts/along_version_bump.py` | source | 5 | 2026-10-11T17:27:34Z | claude--1f15c9eb-976b-4360-b2de-82fefae47317 |
| `scripts/along_wrap.py` | source | 2 | 2026-10-11T17:27:01Z | claude--1f15c9eb-976b-4360-b2de-82fefae47317 |
| `scripts/alongkit/budget.py` | source | 5 | 2026-10-11T17:35:07Z | claude--1f15c9eb-976b-4360-b2de-82fefae47317 |
| `scripts/alongkit/bypass.py` | source | 4 | 2026-10-11T17:40:20Z | claude--1f15c9eb-976b-4360-b2de-82fefae47317 |
| `scripts/alongkit/closeout.py` | source | 1 | 2026-10-11T17:16:20Z | claude--1f15c9eb-976b-4360-b2de-82fefae47317 |
| `scripts/alongkit/entities.py` | source | 7 | 2026-10-11T17:09:09Z | claude--1f15c9eb-976b-4360-b2de-82fefae47317 |
| `scripts/alongkit/gates.py` | source | 3 | 2026-10-11T17:15:53Z | claude--1f15c9eb-976b-4360-b2de-82fefae47317 |
| `scripts/alongkit/gatestats.py` | source | 2 | 2026-10-11T17:40:20Z | claude--1f15c9eb-976b-4360-b2de-82fefae47317 |
| `scripts/alongkit/gitgates.py` | source | 4 | 2026-10-11T17:08:58Z | claude--1f15c9eb-976b-4360-b2de-82fefae47317 |
| `scripts/alongkit/hooks/adapters/claude.py` | source | 1 | 2026-10-11T17:21:05Z | claude--1f15c9eb-976b-4360-b2de-82fefae47317 |
| `scripts/alongkit/hooks/config.py` | source | 2 | 2026-10-11T17:30:43Z | claude--1f15c9eb-976b-4360-b2de-82fefae47317 |
| `scripts/alongkit/hooks/declarative.py` | source | 2 | 2026-10-11T17:30:44Z | claude--1f15c9eb-976b-4360-b2de-82fefae47317 |
| `scripts/alongkit/hooks/default_gates.yaml` | source | 8 | 2026-10-11T17:31:05Z | claude--1f15c9eb-976b-4360-b2de-82fefae47317 |
| `scripts/alongkit/hooks/models.py` | source | 1 | 2026-10-11T17:21:04Z | claude--1f15c9eb-976b-4360-b2de-82fefae47317 |
| `scripts/alongkit/hooks/predicates.py` | source | 13 | 2026-10-11T17:33:37Z | claude--1f15c9eb-976b-4360-b2de-82fefae47317 |
| `scripts/alongkit/hooks/shellparse.py` | source | 4 | 2026-10-11T17:32:01Z | claude--1f15c9eb-976b-4360-b2de-82fefae47317 |
| `scripts/alongkit/hooks/shellwrite.py` | source | 1 | 2026-10-11T17:32:53Z | claude--1f15c9eb-976b-4360-b2de-82fefae47317 |
| `scripts/alongkit/lifecycle.py` | source | 18 | 2026-10-11T17:26:51Z | claude--1f15c9eb-976b-4360-b2de-82fefae47317 |
| `scripts/alongkit/repo.py` | source | 1 | 2026-10-11T17:07:50Z | claude--1f15c9eb-976b-4360-b2de-82fefae47317 |
| `scripts/alongkit/session.py` | source | 5 | 2026-10-11T17:23:44Z | claude--1f15c9eb-976b-4360-b2de-82fefae47317 |
| `scripts/alongkit/verify.py` | source | 3 | 2026-10-11T17:40:21Z | claude--1f15c9eb-976b-4360-b2de-82fefae47317 |
| `skills/along-commit/SKILL.md` | source | 1 | 2026-10-11T17:41:00Z | claude--1f15c9eb-976b-4360-b2de-82fefae47317 |
| `skills/along-init/protocol.md` | source | 2 | 2026-10-11T17:36:04Z | claude--1f15c9eb-976b-4360-b2de-82fefae47317 |
| `skills/along-team/SKILL.md` | source | 2 | 2026-10-11T17:40:55Z | claude--1f15c9eb-976b-4360-b2de-82fefae47317 |
| `skills/along-version-bump/SKILL.md` | source | 1 | 2026-10-11T17:41:10Z | claude--1f15c9eb-976b-4360-b2de-82fefae47317 |
| `skills/along-wrap/SKILL.md` | source | 2 | 2026-10-11T17:41:09Z | claude--1f15c9eb-976b-4360-b2de-82fefae47317 |
| `tests/test_cli_safety_patterns.py` | source | 1 | 2026-10-11T17:33:07Z | claude--1f15c9eb-976b-4360-b2de-82fefae47317 |
| `tests/test_commit.py` | source | 1 | 2026-10-11T17:29:31Z | claude--1f15c9eb-976b-4360-b2de-82fefae47317 |
| `tests/test_context_budget.py` | source | 2 | 2026-10-11T17:36:46Z | claude--1f15c9eb-976b-4360-b2de-82fefae47317 |
| `tests/test_entity_reference_integrity.py` | source | 1 | 2026-10-11T17:10:02Z | claude--1f15c9eb-976b-4360-b2de-82fefae47317 |
| `tests/test_gate_friction.py` | source | 2 | 2026-10-11T17:40:27Z | claude--1f15c9eb-976b-4360-b2de-82fefae47317 |
| `tests/test_hooks_claude.py` | source | 2 | 2026-10-11T17:24:09Z | claude--1f15c9eb-976b-4360-b2de-82fefae47317 |
| `tests/test_lifecycle_wrap.py` | source | 3 | 2026-10-11T17:29:43Z | claude--1f15c9eb-976b-4360-b2de-82fefae47317 |
| `tests/test_projection_autosync.py` | source | 1 | 2026-10-11T17:07:01Z | claude--1f15c9eb-976b-4360-b2de-82fefae47317 |
| `tests/test_release_engine.py` | source | 1 | 2026-10-11T17:29:44Z | claude--1f15c9eb-976b-4360-b2de-82fefae47317 |
| `tests/test_session_bindings.py` | source | 1 | 2026-10-11T17:23:58Z | claude--1f15c9eb-976b-4360-b2de-82fefae47317 |
| `tests/test_session_records.py` | source | 1 | 2026-10-11T17:33:38Z | claude--1f15c9eb-976b-4360-b2de-82fefae47317 |
| `tests/test_shell_classification.py` | source | 1 | 2026-10-11T17:05:54Z | claude--1f15c9eb-976b-4360-b2de-82fefae47317 |
| `tests/test_skills_and_scripts.py` | source | 1 | 2026-10-11T17:29:43Z | claude--1f15c9eb-976b-4360-b2de-82fefae47317 |
| `tests/test_subproject_and_team_gates.py` | source | 1 | 2026-10-11T17:11:32Z | claude--1f15c9eb-976b-4360-b2de-82fefae47317 |
| `tests/test_subproject_model.py` | source | 1 | 2026-10-11T17:11:31Z | claude--1f15c9eb-976b-4360-b2de-82fefae47317 |
| `tests/test_verify_policy.py` | source | 1 | 2026-10-11T17:18:08Z | claude--1f15c9eb-976b-4360-b2de-82fefae47317 |
| `tests/test_workspace_containment.py` | source | 1 | 2026-10-11T17:40:21Z | claude--1f15c9eb-976b-4360-b2de-82fefae47317 |

### Plan

#### Living Plan: field-report-fixes

##### Revision 1 (2026-10-11T17:46:17Z, plan approve --plan-file)

#### Fix the 8 field-reported Along defects

##### Context

Field report (2026-10-11, filed as 8 issues in `.along/ISSUES/`) from a workspace with a nested
subproject. Two blockers (cross-context `parent` rejected; test gate unusable without tests),
three serious gate defects (wrap ordering, cwd-based boundary, plan self-approval), three
improvements. User asked to fix all urgently.

Execution Mode: Role-Based (> 3 files, several subsystems) via `along-team` blackboard, one
step per issue, tests after each step. Work anchored to issues; `along start` per step.

Step 0: `along issue sync` (projection is stale), `along sanitize` on the 8 new issue files,
create issue `feat--gate-friction-and-bypass-accountability` (Step 9).

Order: 0 -> 9a, 9b (remove friction first) -> 1 -> 4 -> 3 -> 2 -> 5 -> 9c, 9d, 9e -> 6 -> 7 -> 8.
Each step: tests green before the next; issue closed with `along issue done` at its end.

##### Step 1 - bug--cross-context-parent-dangling

Root cause: `entities.ancestor_entity_keys` (scripts/alongkit/entities.py:1382-1400) returns
nothing when the context has `.git` and stops at the first `.git` upward; commit/baseline
checks (`gitgates._entity_snapshot` :404, `baseline_entity_problems` :462) snapshot only the
current git top's `.along/`.

- New helper `repo.context_chain(start)` -> list of `.along/` owners from nearest up to
  `session.binding_root` (walk via `repo.find_context` from `dirname(owner)`; stop at home /
  outermost `.along/` owner, not at `.git`; treat `.git` file and dir the same).
- `ancestor_entity_keys` uses `context_chain` (searches ISSUES + done, other entity dirs).
- `gitgates` snapshot checks pass ancestor keys from the working tree as an extra
  `external_keys` argument to `validate_entities` (ancestors are outside the repo, so the
  working tree is the only source).
- Self-parent: in `validate_entities` (:1619) if parent equals own key/slug, resolve against
  ancestor keys only; if not found there -> `invalid self-parent reference` error (counts
  as integrity error via `is_integrity_error`). Record choice in an ADR.
- `_resolve_ref` (:1340): honour `root:` qualifier (resolve only in outermost context);
  other `kind:` prefixes keep current behaviour.
- `issue sync` output prints `parent <key> (found in <ctx rel path>)` for cross-context hits.
- Dashboard `graph.py:229`: stop forcing `feat--` prefix; add external parent as a stub node
  labelled with its context instead of dropping the edge.
- Tests (tests/test_entity_reference_integrity.py, add `parent` param to `_er_issue`): root
  parent + sub git child (sync, commit snapshot, wrap pass); same-sub parent; missing ->
  dangling; self-parent -> resolves to root / errors if absent; ws/sub/subsub. Revise
  `test_ancestor_context_resolves_and_stops_at_git` (:127).

##### Step 2 - bug--test-gate-no-tests-policy

Today only `along test` checks executed-test count (lifecycle.py:228-258); commit/wrap/bump/
closeout use `gates.run_repository_tests` (gates.py:88) on exit code only.

- New `alongkit/verify.py`: `load_verify_policy(root)` reads `.along/config.json` `verify`
  (defaults `tests: required`); validates `none` needs `reason` + existing `tracked_by`
  (resolved via Step 1 chain); `run_checks(root, checks)` runs lifecycle hooks
  (`get_lifecycle_script_path` / `detect_lifecycle_action` / `run_lifecycle_command`);
  allowed check names = `LIFECYCLE_ACTIONS` minus dev/debug, plus `typecheck` as a hook name
  (`.along/scripts/typecheck.py` required, else misconfig error).
- `run_repository_tests` -> returns a result enum (pass / fail / misconfigured / no-tests):
  honours policy; on `required` also applies `tests_ran` (same as `along test`);
  misconfig detection: `npm error Missing script`, runner not found (exit 127 / FileNotFound),
  missing runner config -> message
  `Test hook misconfigured: ... Fix .along/scripts/test.py or set verify.tests = "none"`.
  Callers (along_commit.py:116, lifecycle.py:740, along_version_bump.py:390, closeout.py:626)
  print the matching message.
- Counting: strip ANSI with `distill._ANSI_RE` before `_TEST_COUNT_RES`; set `NO_COLOR=1`,
  `FORCE_COLOR=0` in `proc.child_env` for test runs; resolve `npm test` to the underlying
  script (read package.json `scripts.test`) for known-runner detection.
- Generator: `detect_lifecycle_action` (lifecycle.py:315) and `gates.detect_test_command`
  (gates.py:70): drop `--silent`; no `test` script -> return unconfigured (not verified).
- `along doctor` + `along status` + dashboard metrics: show `tests: none - <reason> (<tracked_by>)`.
- Optional change-aware skip: if staged files are only `*.md`, `.along/**` (not scripts),
  `docs/**`, `llms*.txt` and a `package.json` diff touching only `version` -> skip with note
  (reuse `predicates.is_doc_edit`).
- Update docs mentioning `--silent`: topic--cli-reference.md, topic--architecture.md,
  topic--setup-and-workflow.md, llms-full.txt; fix test_lifecycle_hooks.py:101.
- Tests: the 5 acceptance cases on tempfile node fixtures (fake npm via a stub script on PATH).

##### Step 3 - bug--wrap-not-transactional

`lifecycle.execute_wrap` (lifecycle.py:659-900).
- Move graph gate before any mutation: validate on a projected state (issue as done) by
  passing an `overrides` map {key: status done, path in done/} to `validate_entities`, or by
  running the gate on the current tree plus the status change in memory. Gate failure with
  `force_reason` -> continue, record `forced: graph-gate - <reason>` in session log.
- Move `append_trace` calls (:716, :726) inside the transaction (protect blackboard file).
- KB sync subprocess (:842): protect files it writes or run in-process with tx; else
  `tx.mark_unrestorable`.
- Pass `force_reason` explicitly to `write_session_record(reason=...)`.
- Test: failed wrap leaves `git status --porcelain` identical; forced wrap records reason.

##### Step 4 - bug--subproject-boundary-cwd-context

`predicates.check_subproject_boundary` part 2 (hooks/predicates.py:1250-1265) uses
`os.getcwd()`. Replace with target-path context: nearest `.along/` above the absolute target
(`subproject_context`), then `_subproject_issue_ok` generalized to walk the parent chain
(Step 1 resolver, ISSUES + done, `[key]`/prefixed forms, any depth). Update
`TestBoundaryIgnoresBareManifest` (test_subproject_model.py:100); add test: same edit, 3 cwds,
same result.

##### Step 5 - bug--plan-approval-self-and-lost (+ debt--protocol-friction-cleanup REQ-1)

State: bindings `.along/.session/bindings/<runtime>--<sid>.json` (session.py:223-295);
no UserPromptSubmit handler exists.

- New hook event `UserPromptSubmit`: add to `HookEventType` (hooks/models.py:16), Claude
  adapter `EVENT_TYPE_MAP` (adapters/claude.py:17), `along_hook.py` `--event` choices,
  `hookpreflight.allow_response` (empty `{}` response), manifest in
  `hooks/config.py get_claude_hook_manifest`. Handler stores `last_user_prompt_at` in the
  binding (never blocks). Update tests/test_hooks_claude.py:379.
- `session.check_cli_approval(root, key, slug)`: reject when plan.md mtime / recorded plan
  time > `last_user_prompt_at` ("plan changed after the user's last message; show it and wait
  for a reply"). No timestamp recorded (runtime without the hook) -> allow, mark
  `approved_via: cli-unverified`. Applied to `plan approve` (along_exec.py:1150),
  `scratch approve` (:1888), `scratch phase --approve` (:1906), `scratch update --approve`
  (:1940), `start --approved` (:971).
- `record_plan_approval` stores `approved_via` (`exit-plan-mode` / `cli` / `cli-unverified`),
  `approved_at`, `plan_sha256`; also written to the session log approval line.
- Lost approval: `bind_session` (session.py:223) carries an `exit-plan-mode` approval to the
  newly bound slug when no user prompt arrived after `approved_at` and the plan hash still
  matches the pending/recorded plan; record the plan under the new slug. Update
  `test_approval_before_start_carries_to_first_slug_only` (test_session_bindings.py:153).
- Hint text (REQ-5 wording) in along_exec.py:983, predicates.py:735, skills/along-init/
  protocol.md:30 (+ AGENTS.md managed block via `along update`/merge, keep under 14336 B),
  skills/along-team/SKILL.md:210, docs topic--cli-reference, topic--runtime-hooks-and-gates,
  topic--session-lifecycle; regen llms-full.txt. Closes REQ-1 of debt--protocol-friction-cleanup.
- Skip REQ-6 (step-wise approval) - nice to have; leave open in the issue.
- Tests: approve rejected when plan newer than last prompt, accepted when older; approval
  survives `along start`; UserPromptSubmit stores timestamp.

##### Step 6 - bug--cli-safety-redirect-false-positive

Regex at hooks/predicates.py:61-63 ignores quoting. Replace the echo/printf entry with a
function check using `hooks/shellparse.py` tokenization: split into simple commands
(`; | && || \n`, plus `do/then/else` keywords as command position), skip quoted text; flag
only when command is echo/printf/Write-Output and has a redirect token `>`/`>>` (not `N>`,
`&>`, `>&N`) to a target other than /dev/null, $null, NUL; also flag `tee <path>` fed by
echo/printf and heredoc into a file (`cat <<EOF > path`). Keep `CliSafetyGate` sharing it
(gates.py:144; test_error_handling_and_io.py:109 asserts identity - adjust). Table of ~20 rows
in tests/test_cli_safety_patterns.py incl. the field repro and `echo "a -> b" | cat`.

##### Step 7 - bug--stop-hook-shadow-list-scope

`check_uncommitted_wrap_before_stop` (predicates.py:1048-1087): current-session issues =
completion tokens + bound slug + issues whose blackboard ledger records this session key
(session.py:884). Full list only for those; others collapse to
"N other sessions have uncommitted attributed files (`along session list`)". With no own
issues and others present -> one summary line only. Test in test_session_records.py
(TestWrapBeforeStop).

##### Step 8 - debt--agents-md-budget-project-specifics

`budget.py:152` measures whole AGENTS.md. Decision (ADR): limit applies to the managed block
(`scaffold.MANAGED_BLOCK_RE`); Project specifics gets its own soft limit (warn, default
4096 B), both overridable via `.along/config.json` `budget.agents_md_bytes` /
`budget.project_specifics_bytes`; FAIL/WARN text names the part and suggests moving specifics
to `docs/topic--*.md`. `along_exec.py:2329` passes config limits. Tests in
test_context_budget.py.

##### Step 9 - new issue feat--gate-friction-and-bypass-accountability (ADR)

Principle: reads never block, mechanical fixups are done by the hook, every block has a legal
exit, bypass is a human decision and is recorded, gate quality is measured.

- 9a Read-only classification (hooks/shellparse.py): add to `_ALONG_READ` `sanitize` (without
  `--write`/`--fix`), `issue show`, `milestone show`, `kb search`, `gates check`,
  `decision sync --check`, `graph-*` read modes, `dash` (read). Judge compound commands per
  segment: each segment must be read-only OR Along state OR verification (today the three
  predicates are OR-ed over the whole command, so `along issue sync && npm run build` fails).
  Tests in test_shell_classification.py.
- 9b `projection_sync_before_stop` (predicates.py:1090): content-based staleness via
  `entities.compile_issues_board` vs ISSUES.md (no mtime false positives); include subproject
  contexts. When stale: hook rewrites ISSUES.md itself (`sync_issues_board`) and reports
  "ISSUES.md auto-synced" instead of rejecting; if entity integrity fails, report it without
  blocking the stop (the commit/CI layers still enforce). Removes the plan-mode deadlock seen
  in this session. Tests (none exist today).
- 9c Bypass accountability: one helper `bypass.authorize(root, key, gate, reason)` used by
  `commit -n`, `wrap -n`, `wrap --force-reason`, `bump -n`, `scratch fallback`,
  `scratch purge --force`:
  - requires a non-empty `--reason` (new flag where missing);
  - when the runtime records user prompts (Step 5 hook), a user message must have arrived after
    the latest denial/failure of that gate in this session (the agent showed it and the human
    replied); otherwise refuse with "show the failure to the user and wait for a reply";
    runtimes without the hook -> allowed, tagged `unverified`;
  - recorded in session trace, `hooks_audit.jsonl` (`decision: bypass`), and for commits a
    trailer `Along-Bypass: <gate>; <reason>`.
  `start --approved` goes through Step 5 approval check and gets a trace line.
- 9d Gate tiers: `tier: invariant | process | advisory` in hooks/default_gates.yaml
  (declarative.py loads it). Invariant (workspace_containment, no_tracked_secrets,
  projection_protection, typography? - list in ADR): repo config cannot shadow/disable them
  (ignored with warning) and no bypass. Process: bypass via 9c. Advisory: always shadow.
  Profiles (feat--gate-strictness-profiles) stay a separate issue and build on the tier field.
  `along doctor` lists gates shadowed/disabled by repo config.
- 9e Gate stats: `along gates stats [--since]` aggregates `.along/diagnostics/hooks_audit.jsonl`
  per gate: deny / shadow / bypass counts and bypass ratio; `along doctor` prints the top gates
  by bypass ratio. Dashboard panel deferred (UI work) - noted in the issue.

##### Out of scope / needs your call

- The installed copy in `~/.along/bin` (used by the hooks) is likely older than the source
  (wrap symptom). Refreshing it (`install.ps1`) writes outside the workspace - I will ask
  before running it.
- The 10 uncommitted closed issues from other sessions are not touched.
- No commits without your request.

##### Verification

- After each step: `python .along/scripts/test.py -q` (zero failures), `along sanitize`.
- End-to-end on a temp workspace (ws + nested git sub): issue sync / commit / wrap with
  cross-context parent; node fixture without tests + `verify.tests: none`.
- Closeout: docs blast radius (cli-reference, architecture, setup-and-workflow, domain-model),
  `along kb-sync`, issues done, `along wrap`, projections, HISTORY.

### Execution Trace

#### Execution Trace: field-report-fixes
- 2026-10-11T17:05:37Z edit scripts/alongkit/hooks/shellparse.py (x3)
- 2026-10-11T17:05:42Z edit scripts/alongkit/hooks/predicates.py
- 2026-10-11T17:05:54Z edit tests/test_shell_classification.py
- 2026-10-11T17:06:45Z edit scripts/alongkit/hooks/predicates.py (x2)
- 2026-10-11T17:06:45Z edit scripts/alongkit/hooks/default_gates.yaml
- 2026-10-11T17:07:01Z edit tests/test_projection_autosync.py
- 2026-10-11T17:07:50Z edit scripts/alongkit/repo.py
- 2026-10-11T17:08:28Z edit scripts/alongkit/entities.py (x6)
- 2026-10-11T17:08:58Z edit scripts/alongkit/gitgates.py (x4)
- 2026-10-11T17:09:09Z edit scripts/alongkit/entities.py
- 2026-10-11T17:09:10Z edit scripts/along_exec.py
- 2026-10-11T17:09:34Z edit dashboard/core/graph.py (x3)
- 2026-10-11T17:10:02Z edit tests/test_entity_reference_integrity.py
- 2026-10-11T17:11:12Z edit scripts/alongkit/hooks/predicates.py (x2)
- 2026-10-11T17:11:31Z edit tests/test_subproject_model.py
- 2026-10-11T17:11:32Z edit tests/test_subproject_and_team_gates.py
- 2026-10-11T17:12:23Z edit scripts/alongkit/lifecycle.py (x4)
- 2026-10-11T17:12:27Z denied [cli_safety] run_command: CLI Safety Gate Violation: In-place shell edit (sed -i / perl -i) detected in command: sed -i 's/tx.protect(os.path.join(session.session_dir(repo_root, clean...
- 2026-10-11T17:12:33Z edit scripts/alongkit/lifecycle.py
- 2026-10-11T17:12:48Z edit tests/test_lifecycle_wrap.py
- 2026-10-11T17:14:55Z edit scripts/alongkit/verify.py (x2)
- 2026-10-11T17:15:29Z edit scripts/alongkit/lifecycle.py (x7)
- 2026-10-11T17:15:53Z edit scripts/alongkit/gates.py (x3)
- 2026-10-11T17:16:19Z edit scripts/along_commit.py (x3)
- 2026-10-11T17:16:20Z edit scripts/alongkit/lifecycle.py
- 2026-10-11T17:16:20Z edit scripts/alongkit/closeout.py
- 2026-10-11T17:16:21Z edit scripts/along_version_bump.py
- 2026-10-11T17:18:08Z edit tests/test_verify_policy.py
- 2026-10-11T17:18:26Z edit scripts/along_exec.py (x2)
- 2026-10-11T17:18:41Z edit dashboard/core/collector.py (x2)
- 2026-10-11T17:18:41Z edit dashboard/schemas/metrics.py
- 2026-10-11T17:19:51Z edit scripts/alongkit/hooks/predicates.py
- 2026-10-11T17:21:04Z edit scripts/alongkit/hooks/models.py
- 2026-10-11T17:21:05Z edit scripts/alongkit/hooks/adapters/claude.py
- 2026-10-11T17:21:06Z edit scripts/alongkit/hooks/config.py
- 2026-10-11T17:21:11Z edit scripts/along_hook.py
- 2026-10-11T17:21:45Z edit scripts/alongkit/session.py (x3)
- 2026-10-11T17:22:00Z edit scripts/alongkit/hooks/predicates.py
- 2026-10-11T17:22:22Z edit scripts/alongkit/session.py
- 2026-10-11T17:22:44Z edit scripts/along_exec.py (x8)
- 2026-10-11T17:23:44Z edit scripts/alongkit/session.py
- 2026-10-11T17:23:45Z edit scripts/along_exec.py
- 2026-10-11T17:23:58Z edit tests/test_session_bindings.py
- 2026-10-11T17:24:09Z edit tests/test_hooks_claude.py (x2)
- 2026-10-11T17:24:46Z edit scripts/alongkit/hooks/predicates.py
- 2026-10-11T17:25:42Z edit scripts/alongkit/bypass.py (x2)
- 2026-10-11T17:26:13Z edit scripts/along_commit.py (x7)
- 2026-10-11T17:26:51Z edit scripts/alongkit/lifecycle.py (x5)
- 2026-10-11T17:27:01Z edit scripts/along_wrap.py (x2)
- 2026-10-11T17:27:01Z edit scripts/along_exec.py
- 2026-10-11T17:27:34Z edit scripts/along_version_bump.py (x4)
- 2026-10-11T17:27:48Z edit scripts/along_exec.py (x3)
- 2026-10-11T17:27:58Z edit scripts/alongkit/hooks/predicates.py
- 2026-10-11T17:29:22Z edit scripts/alongkit/bypass.py
- 2026-10-11T17:29:31Z edit tests/test_commit.py
- 2026-10-11T17:29:43Z edit tests/test_lifecycle_wrap.py (x2)
- 2026-10-11T17:29:43Z edit tests/test_skills_and_scripts.py
- 2026-10-11T17:29:44Z edit tests/test_release_engine.py
- 2026-10-11T17:30:43Z edit scripts/alongkit/hooks/config.py
- 2026-10-11T17:30:44Z edit scripts/alongkit/hooks/declarative.py (x2)
- 2026-10-11T17:31:05Z edit scripts/alongkit/hooks/default_gates.yaml (x7)
- 2026-10-11T17:31:30Z edit scripts/alongkit/gatestats.py
- 2026-10-11T17:31:31Z edit scripts/along_exec.py (x2)
- 2026-10-11T17:32:01Z edit scripts/alongkit/hooks/shellparse.py
- 2026-10-11T17:32:02Z edit tests/test_gate_friction.py
- 2026-10-11T17:32:53Z edit scripts/alongkit/hooks/shellwrite.py
- 2026-10-11T17:32:54Z edit scripts/alongkit/hooks/predicates.py (x2)
- 2026-10-11T17:33:07Z edit tests/test_cli_safety_patterns.py
- 2026-10-11T17:33:37Z edit scripts/alongkit/hooks/predicates.py (x2)
- 2026-10-11T17:33:38Z edit tests/test_session_records.py
- 2026-10-11T17:35:07Z edit scripts/alongkit/budget.py (x5)
- 2026-10-11T17:35:08Z edit scripts/along_exec.py
- 2026-10-11T17:35:21Z edit tests/test_context_budget.py
- 2026-10-11T17:36:04Z edit skills/along-init/protocol.md (x2)
- 2026-10-11T17:36:46Z edit tests/test_context_budget.py
- 2026-10-11T17:36:51Z denied [fast_retrieval] grep_search: Manual Search Rejected [gate: fast-retrieval]: Manual directory search across 'D:\Src\my\actdim\public\along\docs' is forbidden to prevent latency and LLM to...
- 2026-10-11T17:37:37Z denied [test_before_stop] : Turn Completion Rejected [gate: test-before-stop]: Source files were modified in this session, but automated tests have not been executed afterward. A raw te...
- 2026-10-11T17:38:50Z edit docs/topic--cli-reference.md (x18)
- 2026-10-11T17:39:41Z edit docs/topic--runtime-hooks-and-gates.md (x6)
- 2026-10-11T17:39:55Z edit docs/topic--session-lifecycle.md (x2)
- 2026-10-11T17:40:02Z edit docs/topic--architecture.md
- 2026-10-11T17:40:15Z edit docs/topic--setup-and-workflow.md (x3)
- 2026-10-11T17:40:20Z edit scripts/alongkit/bypass.py
- 2026-10-11T17:40:20Z edit scripts/alongkit/gatestats.py
- 2026-10-11T17:40:21Z edit scripts/alongkit/verify.py
- 2026-10-11T17:40:21Z edit tests/test_workspace_containment.py
- 2026-10-11T17:40:27Z edit tests/test_gate_friction.py
- 2026-10-11T17:40:32Z edit docs/topic--domain-model.md
- 2026-10-11T17:40:55Z edit skills/along-team/SKILL.md (x2)
- 2026-10-11T17:41:00Z edit skills/along-commit/SKILL.md
- 2026-10-11T17:41:08Z edit .along/DECISIONS/ADR-2026-10-11--gate-friction-fixes.md
- 2026-10-11T17:41:09Z edit skills/along-wrap/SKILL.md (x2)
- 2026-10-11T17:41:10Z edit skills/along-version-bump/SKILL.md
- 2026-10-11T17:41:15Z denied [test_before_stop] : Turn Completion Rejected [gate: test-before-stop]: Source files were modified in this session, but automated tests have not been executed afterward. Run test...
- 2026-10-11T17:45:52Z edit .along/ISSUES/bug--plan-approval-self-and-lost.md
- 2026-10-11T17:45:53Z edit .along/ISSUES/feat--gate-friction-and-bypass-accountability.md
- 2026-10-11T17:46:17Z plan recorded: revision 1 (plan approve --plan-file)
- 2026-10-11T17:46:17Z plan approved (along plan approve)
