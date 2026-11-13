# Living Plan: issue-test-scoping-policy

## Revision 1 (2026-11-13T14:34:46Z, plan approve --plan-file)

# Plan: feat--issue-test-scoping-policy

Execution Mode: Role-Based - the scope crosses the engine (`verify`, `gates`, `testruns`, `lifecycle`), the CLI, the Stop hook, skills, protocol and KB. Run it through `along-team`. The four phases below are the step loops. Each phase ends green and is committed separately via `/along-commit` bound to `issue-test-scoping-policy`.

## Context

The ticket (`feat--issue-test-scoping-policy`) states the problem, the current engine state and REQ-1..10. In short, three gaps lead to a full suite on every wrap, sometimes twice:

- the verify policy is per-repository only;
- test runs cannot be scoped;
- a test run that dirties the tree silently defeats green-run reuse.

The ticket's original idea of always passing `-n` from wrap to `along_commit.py` is rejected: `-n` also skips the syntax, link and typography gates and records a bypass.

What exists and must be reused, not duplicated:

- `scripts/alongkit/verify.py`:
  - `VerifyPolicy`, `load_policy(repo_root)` (reads `verify` from `.along/config.json`), `policy_problems(repo_root, policy)`, `run_checks`;
  - `test_inert_globs`, `is_test_inert_path`, `docs_only_change`.
- `scripts/alongkit/gates.py:113` `run_test_gate(repo_root, label)`: applies the policy, reuses a green run by `tree_hash`, runs the hook, records the run.
- `scripts/alongkit/testruns.py`: `tree_hash`, `record_run(repo_root, ok, tree, source)`, `green_run_for(repo_root, tree)`, `baseline_note`.
- `scripts/alongkit/session.py`:
  - `record_plan_approval_event` (~1570), `plan_approval_events`;
  - `attributed_files(ctx, slug) -> {path: {...}}` (~1264);
  - `resolve_active_session` (~850), `resolve_bound(repo_root, key) -> (ctx_root, slug)` (~879).
- `scripts/alongkit/proc.py`: `child_env(extra=None, base=None)` (~87), `run_capture(cmd, cwd, env=...)` (~105). Passing `env=` replaces the base environment, so always build it with `child_env(extra=...)`.
- Entities and front matter:
  - `entities.find_issue_by_slug(repo_root, slug)` returns a dict with `type` and `frontmatter`;
  - `entities.update_issue_frontmatter(repo_root, slug, updates)`;
  - `frontmatter.plain()`. The ruamel round trip keeps nested mappings, and new mappings are written in flow style.
- Tests:
  - `tests/hermetic.py` (`make_repo_fixture`, `isolated_home_env`);
  - `_Fixture` in `tests/test_verify_policy.py` (`hook(name, body)`, `policy(**verify)`);
  - `GitFixture` in `tests/test_parallel_closeout.py`;
  - `_GitRepo` in `tests/test_wrap_engine_writes.py`.

## Design decisions (settled, do not re-open)

1. **Policy values.**
   - Repository level (`.along/config.json`) stays `required | none`.
   - Issue level allows `required | affected | scoped | none`.
   - The hook sees `ALONG_TEST_MODE = full | affected | scoped`, where `required` maps to `full`.
2. **Issue block** in front matter, flow style:
   ```yaml
   verify: {tests: scoped, scope: api, reason: "API-only change", tracked_by: "", checks: []}
   ```
   Validation:
   - every mode other than `required` needs `reason`;
   - `none` needs `tracked_by` for every issue type except `spike`;
   - `scoped` needs `scope` declared in `.along/config.json` under `verify.scopes` (`{"<name>": ["<glob>", ...]}`);
   - `checks` follows the existing `CHECK_NAMES` rule.
3. **Only an approved snapshot counts.**
   - `along plan approve` reads the issue's `verify` block, validates it, and refuses to approve on problems, listing them.
   - It stores the plain dict as `verify` in the approve event in `.along/.session/plan-approvals.jsonl`. That file is already closed to agent writes (`APPROVAL_RECORD_PATTERNS`, `predicates.py:203`).
   - Gates read the snapshot of the latest approve event, never the front matter.
   - If the front matter differs from the snapshot, gates print a warning (`verify changed after plan approval; using the approved policy; re-approve the plan to apply it`) and use the snapshot.
4. **Effective policy.** `load_effective_policy(repo_root, slug)` returns the issue snapshot when `slug` is given and has one (`source="issue"`). Otherwise it returns the repository policy (`source="repo"`, or `"default"` when undeclared). Callers pass `slug` explicitly; `slug=None` means repository policy.
5. **`affected` with no files** (empty attributed set) falls back to `full` and says so.
6. **Run coverage.**
   - A run record carries `mode` and `scope`.
   - A green `full` run covers any request. A legacy record without `mode` counts as `full`.
   - An `affected` or `scoped` run covers only a request with the same mode and scope on the same tree.
   - A `full` request is never satisfied by a partial run.
7. **`along test`.**
   - Without flags it runs the effective policy of the bound issue.
   - `--full` forces full; `--scope <name>` and `--affected` force a mode.
   - The flags are stripped before the hook's args.
8. **No blanket bypass.** `_auto_commit_wrapped_work` keeps passing `-n` only when wrap itself got `-n`. Double runs are prevented by coverage-aware reuse plus a hermeticity warning.
9. **Callers and the policy they use:**

   | Caller | Policy |
   |--------|--------|
   | wrap | bound slug |
   | `along_commit.py` | `-i` slug |
   | Stop hook | slug from `session.resolve_active_session` |
   | `closeout.py` | full |
   | `along_version_bump.py` | full |

## Phase 1: hermeticity warning (REQ-1)

1. `scripts/alongkit/lifecycle.py`, wrap pre-flight test gate (~1225-1243):
   - Take `before = set(repo.working_tree_changes(repo_root) or [])` and `tree_before = testruns.tree_hash(repo_root)` before `gates.run_test_gate`. Take the same after it.
   - If `tree_after != tree_before`, print to stderr:
     `[Warning] Wrap Quality Gate: the test run changed the working tree (<up to 10 paths from after - before, or "files already modified">); add them to .gitignore or ignore_paths in .along/rules/gates.yaml, or the pre-commit gate runs the suite again.`
   - Never fail on it.
2. Add no `-n` change to `_auto_commit_wrapped_work` (~796-878). Pin the behavior with tests instead.
3. Tests in `tests/test_lifecycle_wrap.py`, using a fake `.along/scripts/test.py` that runs one unittest:
   - a hook that also writes `out.log` gives the warning, and the auto-commit message has no bypass trailer;
   - a clean hook leaves exactly one run in `test_runs.json` after wrap plus auto-commit (the pre-commit run was reused).
4. Commit: `fix: warn when wrap test run dirties the tree (refs #issue-test-scoping-policy)`.

## Phase 2: issue-level verify policy (REQ-2, 3, 4, 7)

1. **`scripts/alongkit/verify.py`**
   - Constants: `TESTS_AFFECTED = "affected"`, `TESTS_SCOPED = "scoped"`, `ISSUE_TEST_POLICIES = (required, affected, scoped, none)`. `TEST_POLICIES` (repository) stays `(required, none)`.
   - `VerifyPolicy` gains `scope: str = ""`, `source: str = "default"` and `issue: str = ""`.
     - `describe()`: `tests: scoped (api) - <reason> (issue feat--x)`; the repository and default forms stay as today.
     - New method `hook_mode()` maps `required` to `full`, `affected` to `affected` and `scoped` to `scoped`.
   - `load_scopes(repo_root) -> Dict[str, List[str]]` reads `verify.scopes`. Invalid shapes are reported through `policy_problems`.
   - `policy_from_block(block, source, issue="") -> VerifyPolicy`: shared parsing for the config block and the snapshot. Refactor `load_policy` onto it.
   - `policy_problems(repo_root, policy, issue_type=None)` applies decision 2 when `source == "issue"`; the repository rules are unchanged.
   - `load_effective_policy(repo_root, slug=None) -> VerifyPolicy` implements decision 4.
     - The snapshot comes from `session.approved_verify_snapshot`.
     - The issue is resolved in its own context; use `entities.reference_context` to find the owning `.along/`, as nested contexts exist.
     - It prints the drift warning of decision 3.
2. **`scripts/alongkit/session.py`**
   - `record_plan_approval_event(..., verify: Optional[Dict] = None)` writes `verify` when it is given.
   - `approved_verify_snapshot(repo_root, slug) -> Optional[Dict]`: the `verify` of the latest event when that event is `approve`, else None.
3. **`scripts/alongkit/commands/lifecycle.py`**, plan approve paths (approve ~424, `_approve_ahead` ~549, batch `--from`):
   - Before recording, load the issue front matter `verify`.
   - Validate it with `policy_problems(..., issue_type=<type>)`. On problems, print them and exit 1 without recording.
   - Otherwise pass the plain dict to `record_plan_approval_event`.
4. **`scripts/alongkit/gates.py`**: `run_test_gate(repo_root, label="Quality Gate", slug=None, files=None) -> str`.
   - `policy = verify.load_effective_policy(repo_root, slug)` replaces `load_policy`. Validate as today, passing `issue_type` for issue policies.
   - `none` runs checks as today and prints `policy.describe()`.
   - Otherwise:
     - Print `-> [label] <policy.describe()>`.
     - Compute `mode`/`scope`, applying the decision 5 fallback when `files` is empty in `affected` mode.
     - Reuse check: `testruns.green_run_for(repo_root, tree, mode, scope)`.
     - Run the hook with `env=proc.child_env(extra={"ALONG_TEST_MODE": mode, "ALONG_TEST_SCOPE": scope, "ALONG_ATTRIBUTED_FILES": <path or "">})`. The attributed file is created with `tempfile.mkstemp` and holds one repo-relative POSIX path per line; it is deleted in `finally`.
     - Record with `mode`/`scope`. Land the `testruns` signature change from Phase 3 step 1 in this same commit.
   - `run_repository_tests(repo_root, label)` (~101) stays repository-only.
5. **Callers**
   - Wrap (`lifecycle.py` ~1238): `run_test_gate(repo_root, "Wrap Quality Gate", slug=clean_slug, files=sorted(combined_changes))`, with `combined_changes` as already computed there.
   - `scripts/along_commit.py:168`: `slug=parsed.issue`, `files=planned`.
   - `closeout.py:699` and `along_version_bump.py:535`: unchanged, so full.
6. **CLI, `scripts/alongkit/commands/issue.py`**
   - `create` (~40) and `update` (~457) accept `--verify-tests`, `--verify-scope`, `--verify-reason`, `--verify-tracked-by` and `--verify-checks a,b`; `update` also accepts `--verify-clear`.
   - Build the block, then validate it with `policy_problems(..., issue_type)`. On problems, print them and exit 2 before writing.
   - Write the block with `entities.update_issue_frontmatter`. Create writes its f-string first, then calls update.
   - The help text in `handle_issue_command` (~758) lists the flags.
7. **`along issue show`**: `entities/query.py` `get_issue_summary` (~288) adds `verify` (front matter) and `verify_effective` (`describe()` of the effective policy), to both text and `--json` output.
8. **Tests**
   - Extend `tests/test_verify_policy.py`:
     - each mode's validation, the spike exemption, an undeclared scope;
     - precedence (issue snapshot over repository, repository when there is no snapshot);
     - the drift warning.
   - New `tests/test_issue_verify_policy.py`:
     - CLI flags write and validate the block;
     - `plan approve` stores the snapshot and refuses an invalid block;
     - a gate with a fake hook that dumps `os.environ` `ALONG_*` to a JSON file sees the right mode, scope and attributed list, and the temp file is gone after the run.
9. Commit: `feat: issue-level verify policy snapshotted at plan approval (refs #issue-test-scoping-policy)`.

## Phase 3: run coverage, `along test` modes, Stop hook (REQ-5, 6)

1. **`scripts/alongkit/testruns.py`** (signature lands in Phase 2; this step completes the callers)
   - `record_run(repo_root, ok, tree, source, mode="full", scope="")` stores both fields.
   - `green_run_for(repo_root, tree, mode="full", scope="")` applies decision 6 to the latest run on that tree that satisfies coverage. A red run on the tree with the same coverage still blocks, as today: take the last run with matching coverage, not just the last run.
   - Update the callers: `lifecycle.py:234`, `closeout.py:740` (full), `along_version_bump.py:877` (full), `commands/session.py:47-49` (evidence line shows mode/scope).
2. **`along test` flags.** `scripts/along_exec.py` (~360), for `cmd == "test"` only, pops `--full`, `--affected` and `--scope <name>` from `extra_args` before `build_interpreter_cmd`, and passes them to `lifecycle.run_lifecycle_command(..., test_mode=..., test_scope=...)`.
3. **`scripts/alongkit/lifecycle.py` `run_lifecycle_command`** (~208)
   - Resolve the effective policy of the bound issue (`session.resolve_bound` with `session.current_session_key()`) unless the flags force a mode.
   - Validate with the same `policy_problems`; `none` runs checks as today.
   - Affected files: `session.attributed_files(ctx, slug)` keys plus `repo.working_tree_changes`.
   - Pass the same env dict to `_run_tee` (~257; add an `env` parameter, `Popen(env=...)`) and to the distill path (`proc.run_capture(..., env=...)`).
   - Record with mode/scope. `session.trace_test_run` gets the mode in its label.
4. **This repo's hook `.along/scripts/test.py`** (record calls at 263 and 328) records `mode=os.environ.get("ALONG_TEST_MODE") or "full"` and `scope=os.environ.get("ALONG_TEST_SCOPE", "")`. It still runs its normal suite, since this repo declares no scopes. Add `ALONG_TEST_*` handling to the generated template `lifecycle.render_lifecycle_script` only as a commented example; generated hooks inherit the env anyway.
5. **Stop hook, `scripts/alongkit/hooks/predicates.py`**
   - Trace (~606-622): when a lifecycle test command starts, parse `--full`, `--affected` and `--scope X` from it and store `last_test_mode`/`last_test_scope` next to `last_test_time`.
   - `check_test_before_stop` (~1621):
     - The reuse check uses `green_run_for(tree, mode, scope)` of the effective policy (bound slug from `event_session_key` + `session.resolve_bound`).
     - `has_source_edits` is cleared only when the last test command's mode covers the effective policy, by decision 6. A plain `along test` covers it by construction (decision 7).
     - On a non-covering run, the message adds `the last run was <mode> (<scope>); the approved policy needs <mode>`.
6. **Tests**
   - Extend `TestTestRunReuse` in `tests/test_parallel_closeout.py` and `TestTreeHashReuse` in `tests/test_lifecycle_test_evidence.py`:
     - scoped is not reused for full;
     - full is reused for scoped;
     - a legacy record counts as full;
     - `scoped(api)` is not reused for `scoped(web)`.
   - A predicate test: `along test --scope api` under a full policy leaves the Stop gate armed.
   - An `along_exec` test: the flags never reach the hook's argv.
7. Commit: `feat: scoped test runs with coverage-aware reuse (refs #issue-test-scoping-policy)`.

## Phase 4: protocol, skills, KB, doctor (REQ-8, 9, 10)

1. **`skills/along-init/protocol.md`** (6139 of 6144 bytes; checked by `tests/test_context_budget.py:95`)
   - Line 38: `tests run after your last edit` becomes `tests (per the approved verify policy) run after your last edit`.
   - Recover at least 31 bytes by tightening wording elsewhere without dropping any rule or gate id.
   - Then refresh the managed block in root `AGENTS.md` with `along init` (idempotent; refreshes only the managed block). Never hand-edit it.
2. **`skills/along-init/protocol-reference.md`**
   - Completion checklist item 1, Tests (two places, ~110 and ~121): tests follow the effective verify policy; `none` is a recorded, legitimate skip, not a bypass.
   - New section `## Testing Invariants`: `ignore_paths`, the policy levels and precedence, the snapshot at approval and drift, `ALONG_TEST_MODE` / `ALONG_TEST_SCOPE` / `ALONG_ATTRIBUTED_FILES`, run coverage, `along test --full|--affected|--scope`, the hermeticity warning, `--no-commit` for local experiment files.
3. **Skills**
   - `skills/along-wrap/SKILL.md`: the effective policy in the test gate, the hermeticity warning, when to use `--no-commit`.
   - `skills/along-test/SKILL.md`: the flags, the default of following the bound issue's policy, the runner contract with a `test.py` mapping example.
4. **KB**
   - `docs/topic--setup-and-workflow.md` "Test Policy (`verify`)" (~257): the issue level, scopes, and the target-repository guidance from the ticket (choosing spike/scoped/none, a scoped `test.py`, an `AGENTS.md` Project specifics example).
   - `docs/topic--cli-reference.md`: `along test` (~71), `along issue create|update|show` flags, `along commit` reuse (~451).
   - `docs/topic--declarative-gates-and-traceability.md`: `test_before_stop` (~86) coverage note.
   - Then `/along-kb-sync`.
5. **Doctor**, `scripts/alongkit/commands/doctor.py` (~556)
   - Print `Verify: <effective repository policy>`.
   - Validate `verify.scopes` (shape, non-empty globs) and `ignore_paths` (list of non-empty strings).
   - For every open issue with a `verify` block, run `policy_problems`. Errors give `[FAIL]`; a block not yet approved gives `[WARN]`.
6. **Tests:** doctor (`[FAIL]` on an undeclared scope); `tests/test_context_budget.py` stays green.
7. Commit: `docs: document scoped testing and verify policy (refs #issue-test-scoping-policy)`.

## Verification

- After each phase:
  - `along test` (quiet) for the whole suite;
  - `along sanitize`, `along lint`, `along issue lint`;
  - `git diff --stat` to check for unintended deletions.
- End-to-end in a temp repo (`hermetic.make_repo_fixture`, git-initialized) with a fake `.along/scripts/test.py` that writes its `ALONG_*` env to `env.json`:
  1. Declare `verify.scopes.api = ["src/api/**"]`, then `along issue create feat e2e --title E2E --verify-tests scoped --verify-scope api --verify-reason "api only"`, `along plan approve e2e --plan-file plan.md`, `along start e2e`, and edit `src/api/x.py`.
  2. `along test` prints `tests: scoped (api)`, and `env.json` has `ALONG_TEST_MODE=scoped`.
  3. Edit the issue's `verify` to `none`: a drift warning, and the run stays scoped.
  4. `along wrap e2e --summary s --no-decisions`: one run is recorded, the pre-commit gate reuses it, and the commit has no bypass trailer.
  5. Repeat with a hook that writes `out.log`: the hermeticity warning appears.
- `along doctor` on this repo prints `Verify: tests: required (default)` with no new `[FAIL]`.

## Out of scope

- `along issue find` is referenced in `AGENTS.md` but missing from the CLI; file a separate issue.
- Engine-side mapping of files to test suites; it stays in each repository's `test.py`.

## Closeout

- `along graph-impact` on the final diff; update any affected `docs/topic--*.md` it names.
- Record an ADR via `/along-decision-sync`: "Issue-level verify policy is taken from the plan-approval snapshot; wrap never auto-bypasses pre-commit gates; partial test runs never satisfy a full request."
- `along wrap issue-test-scoping-policy --summary "..." --decisions <ADR key>`.
