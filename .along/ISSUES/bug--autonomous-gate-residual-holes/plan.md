# Living Plan: bug--autonomous-gate-residual-holes

Execution Mode: Role-Based (along-team: crosses hooks, session, orchestrator and CLI; > 3 files)

## Context

Closes the autonomous-profile holes left by `feat--autonomous-gate-profile` (a8ea884). The most urgent
one is live in the ordinary interactive mode: an agent can approve its own plan by writing
`.along/.session/<slug>/state.json` or a binding through the shell, which no gate sees (file tools are
already blocked by `APPROVAL_RECORD_PATTERNS`; `.along/.session/` is git-ignored, so the Stop-time
working-tree check misses it). The ticket holds REQ-1..4, 6, 7 and the acceptance criteria. REQ-5 (a real
Telegram escalation handler) is out of scope: it moved to `feat--agent-execution-gate-telegram`; this plan
keeps escalation fail-closed and makes sure it can never loosen another gate.

Facts the steps rely on (verified 2026-10-29):

- Profile resolution: `profiles.resolve_active_profile_with_source` (`scripts/alongkit/profiles.py`):
  session binding / state (`session.get_session_profile`), then env `ALONG_PROFILE` / `ALONG_AUTONOMOUS`,
  then `.along/config.json` / `config.yaml` (`load_config_profile`), then default.
  `profiles.validate_profile` accepts `autonomous`, so `along start --profile autonomous`
  (`commands/lifecycle.py`) stores it in the binding and `state.json`.
- `containment.is_autonomous(event)` (`hooks/containment.py`) is true for env, payload `profile`, payload
  `permission_mode` in `AUTONOMOUS_PERMISSION_MODES`, or the resolved profile. It is used for two
  different things: turning ASK into DENY (stricter; fine from any source) and, in
  `predicates.check_mutation_authorization`, skipping the phase check after plan approval (a loosening).
- Loosenings under autonomous today: (a) `check_mutation_authorization` returns None for an approved plan
  whose phase is not execution when the profile is autonomous or `is_autonomous(event)`; (b)
  `session.is_plan_approved` guesses the single in-progress slug for a session with no slug and no key;
  (c) `hooks/engine.py` `HookEngine.evaluate` routes a gate's deny to `route_escalation` and `continue`s
  past that gate when the handler allows.
- Legitimate approvals append a ledger `approve` event (`session.append_event(..., "approve")`):
  `session.record_plan_approval` (ExitPlanMode hook), `commands/lifecycle.py` for `along start --approved`
  and `along plan approve`. The orchestrator's `session.approve_plan` runs outside agent turns.
- The turn baseline is taken on UserPromptSubmit in `predicates.record_tool_activity` (activity trace
  `.along/diagnostics/activity/<key>.json`, key `turn_baseline`); Stop handling is in
  `check_mutation_authorization` (`HookEventType.STOP` branch).
- Shell gates match explicit forms per segment (`shellparse.split_segments`, e.g. `_SHELL_DELETION_CMD_RE`);
  the project does not classify commands as read-only (see the `shellparse` module docstring).

## Steps

- [ ] Step 1: Trusted source for the autonomous profile (REQ-1)
  - `profiles.resolve_active_profile_with_source`: a session or config source that names `autonomous`
    is skipped (resolution falls through to the next source); `autonomous` is returned only from env.
    Keep `strict` / `standard` / `light` from every source as today.
  - Add `profiles.autonomous_from_env() -> bool` (env only) and use it for every loosening:
    `check_mutation_authorization`'s phase skip (replace `resolve_active_profile(...) == AUTONOMOUS or
    containment.is_autonomous(event)` in the approved-plan branch with `autonomous_from_env()`), and
    `HookEngine.evaluate`'s `is_auto` for escalation routing.
  - `containment.is_autonomous`: drop the payload `profile` key; keep env and `permission_mode` (they only
    turn ASK into DENY). Its fallback to `resolve_active_profile` now only sees env.
  - `session.is_plan_approved`: delete the `is_auto` block and the single-in-progress-slug guess (runners
    pass `ALONG_ISSUE_SLUG`; nothing else needs it).
  - `along start --profile autonomous` and `bind_session(..., profile="autonomous")` from the CLI: exit 2
    with "the autonomous profile is set by the operator environment (ALONG_PROFILE / ALONG_AUTONOMOUS)".
  - `along doctor` (if it reports the profile): warn when a repo config or session names `autonomous`.
  - Tests (`tests/test_autonomous_gate_profile.py`): invert `test_resolution_via_config_json_top_level`,
    `..._hooks_section`, `..._session_binding` (autonomous from these sources resolves to the next source,
    not autonomous); payload `profile: autonomous` does not make `is_autonomous` true; `permission_mode:
    bypassPermissions` still turns ASK into DENY but does not skip the phase check; `along start --profile
    autonomous` exits 2. Update `test_unapproved_plan_denied_in_autonomous_profile_even_on_antigravity` and
    the plan-approval tests to set autonomy through env only.

- [ ] Step 2: Shell writes to approval records (REQ-2, layer 1: before the command runs)
  - Extend `APPROVAL_RECORD_PATTERNS` (`hooks/predicates.py`) with the ledger
    `.along/.session/*/events.jsonl` and the activity traces `.along/diagnostics/activity/**`
    (file tools never need to write them; hooks and the CLI write them from Python).
  - New `check_approval_record_shell_write` in `predicates.py`, wired into
    `check_mutation_authorization`'s PreToolUse branch for shell tools (`run_command`, `execute_command`,
    `bash`, `shell`; reuse `_extract_command`). Per segment (`shellparse.split_segments`), deny when the
    segment names an approval record (regex over `/` and `\`, quoted or not:
    `.along[\\/].session[\\/](bindings[\\/]|[^\\/\s"']+[\\/](state\.json|events\.jsonl)|plan-approvals\.jsonl)`
    and `.along[\\/]diagnostics[\\/]activity[\\/]`) **and** has an explicit write form:
    redirection `>` / `>>` / `1>` / `&>` to that path, `tee`, `cp`, `mv`, `install`, `rm`, `truncate`,
    `sed -i`, `dd of=`, PowerShell `Set-Content` / `Add-Content` / `Out-File` / `Copy-Item` /
    `Move-Item` / `Remove-Item` / `New-Item` / `Clear-Content`, `[IO.File]::Write*`, or an inline
    interpreter (`python -c`, `py -c`, `node -e`, `perl -e`, `ruby -e`, `pwsh -c` / `powershell -Command`)
    whose code names the record. Reads (`cat`, `type`, `Get-Content`, `jq` without `-i`, `grep`) pass.
    Message: `PLAN_REQUIRED [gate: require-plan-approval]: '<path>' is an approval record; only the along
    CLI writes it.` Bound or unbound session, any profile (same as the file-tool rule).
  - Reuse `shellwrite._lex` / `_unquote` if they fit; do not add a read-only classifier.
  - Tests (new class in `tests/test_autonomous_gate_profile.py` or a new
    `tests/test_approval_record_shell_guard.py`): each write form above for `state.json`, a binding,
    `events.jsonl`, `plan-approvals.jsonl` and an activity trace, in bash and PowerShell spelling, is
    denied through `HookEngine(config=HooksConfig(profile="standard"))`; `cat` / `Get-Content` of the
    same paths and `echo x > src/a.txt` are allowed by this check.

- [ ] Step 3: Stop-time revocation of forged approvals (REQ-2, layer 2: whatever text matching misses)
  - On UserPromptSubmit (`record_tool_activity`), store `approval_baseline` in the activity trace next to
    `turn_baseline`: for the session key, `{"slug", "binding_approved": bool, "state_approved": bool,
    "ledger_approves": <count of "approve" events in the slug's events.jsonl>}`.
  - At Stop (`check_mutation_authorization` STOP branch, before the working-tree check): recompute; if
    `binding_approved` or `state_approved` went False -> True and the ledger `approve` count did not grow,
    revoke: `session.update_state(ctx, slug, phase="planning", plan_approved=False)` and clear the
    binding's `plan_approved` / `approved_slug` (through `session.save_binding`), append a ledger `deny`
    event, and return `PLAN_REQUIRED [gate: require-plan-approval]: the plan for '<slug>' was marked
    approved this turn without 'along plan approve' or the user's plan-mode approval; the approval was
    revoked. Ask the user to approve the plan.`
  - No baseline (first turn, unbound session): skip.
  - Tests: simulate UserPromptSubmit, then write `plan_approved: true` into `state.json` with
    `session.save_state` (stands in for a script) and send Stop: Stop is denied and `is_plan_approved` is
    False afterwards. With `along plan approve` (or `session.record_plan_approval`) in the same turn: Stop
    passes and the approval stays.

- [ ] Step 4: Escalation never loosens a gate and runs only on PreToolUse (REQ-3, REQ-4)
  - `HookEngine.evaluate` (`hooks/engine.py`): remove escalation routing from inside the gate loop; a
    gate's deny is final (audit, `record_gate_denial`, return) whatever `classify_escalation` says.
  - The post-loop escalation check runs only when `event.event_type == HookEventType.PRE_TOOL_USE` and
    `profiles.autonomous_from_env()`; it may deny (handler missing, denied, timed out) but an allow only
    means "no objection" for an operation every gate already allowed.
  - `hooks/escalation.py`: remove the duplicate `TimeoutError` in the except tuple.
  - Tests: a workspace-containment (or credential-store) deny with an escalation handler that returns
    allow stays a deny; a PostToolUse event for `git push origin main` under env autonomy yields no
    escalation record and no denial; the existing escalation tests keep passing.

- [ ] Step 5: Release detection (REQ-6)
  - `escalation._is_tag_or_release`: for `python` / `python.exe` / `py` invocations, skip the script path
    and read the subcommand after the first argument that ends in `along_exec.py` or `along_version_bump.py`
    (or a bare `along`); treat `version-bump`, `bump`, `release` as release operations.
  - Add `gh release create|edit|upload|delete` and `git push --tags` / `git push <remote> <tag-ref>`
    (`refs/tags/`, `v*` refspecs with `--tags` or `--follow-tags`) as tag/release operations.
  - `git tag` with only listing / inspection arguments (`-l`, `--list`, `-n`, `--contains`, `--points-at`,
    `--sort`, `-v`, `--verify`, no positional tag name being created) is not an escalation.
  - `escalation._is_git_push_default_branch`: treat `+main`, `+master`, `HEAD:main`, `+refs/heads/main`
    and `--force` / `-f` / `--force-with-lease` pushes to a default branch as default-branch pushes.
  - Tests: extend `test_classify_tag_or_release` / `test_classify_push_to_default_branch` with
    `python scripts/along_exec.py version-bump`, `gh release create v1`, `git push --tags`,
    `git push origin +main`, `git push origin HEAD:main`; assert `git tag -l`, `git tag --list 'v*'`,
    `git tag --contains HEAD` are not escalations.

- [ ] Step 6: Architect self-approval needs operator opt-in (REQ-7)
  - `CrossRuntimeOrchestrator.run_architect_phase` (`scripts/alongkit/orchestrator.py`): after the plan is
    validated, approve it (`session.approve_plan` + `approved_by: architect`) only when
    `os.environ.get("ALONG_ARCHITECT_SELF_APPROVAL", "").lower() in ("1", "true", "yes")`. Otherwise call
    `session.set_plan_status(repo_root, slug, "needs-approval")` (the plan already lives in the issue folder
    via `session.plan_path`), set the session status `needs-input`, and return
    `{"phase": "architect", "status": "needs-input", "reason": "the architect's plan waits for the user's
    approval (along plan approve <slug>)"}`. A rerun after `along plan approve` takes the
    `run_issue_plan_phase` path and skips the architect.
  - Daemon: the needs-input reply already carries `reason`; no change needed beyond checking the text.
  - Document the variable in `docs/topic--autonomous-environment.md` (runner daemon section) and in the
    orchestrator section of `docs/topic--along-protocol.md` if it describes self-approval.
  - Tests (`tests/test_orchestrator.py`): without the variable, `run_architect_phase` returns needs-input,
    `plan_approved` stays False and the ticket says `plan_status: needs-approval`; with it set, today's
    behavior (approved, phase execution). Update `test_phased_lifecycle_success` to set the variable.

- [ ] Step 7: Docs, full suite, closeout
  - `docs/topic--along-protocol.md`: the autonomous profile comes from the operator environment only;
    approval records are closed to file tools and explicit shell writes, forged approvals are revoked at
    Stop; escalation never overrides another gate.
  - Confirm each new test fails on the code before this ticket (stash the source changes, run, restore).
  - `python .along/scripts/test.py -q` green; `along sanitize`; `git diff --stat` review.
  - Commit through `/along-commit` (one commit per step or one for the ticket), then
    `along wrap autonomous-gate-residual-holes --summary "..." --no-decisions`.

## Out of scope

- REQ-5, a real escalation handler: `feat--agent-execution-gate-telegram` (Approve / Reject cards, the hook
  waits on a local decision file written by the daemon).
- OS / container isolation against deliberate multi-file forgery: `bug--autonomous-container-build-and-firewall`.

## Rules for the executing agent

- Deviations that still meet the ticket's requirements and acceptance criteria: resolve and record with
  `along plan revise autonomous-gate-residual-holes --plan-file <path> --reason "..."`.
- A requirement that cannot be met or must change: `along plan rework autonomous-gate-residual-holes
  --reason "..."`, stop, and ask the user.
