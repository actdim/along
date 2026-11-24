# Plan: OpenCode/DSH runtime integration defects

Issue: `bug--opencode-runtime-integration-defects`
Execution Mode: Role-Based

## Current state

Verified on 2026-11-24 against OpenCode `2.3.2` (installed at
`%LOCALAPPDATA%\mise\installs\opencode\2.3.2\opencode.exe`), Python suite `1998 tests OK`.

- `scripts/alongkit/hooks/opencode_plugin.js` exports `{ id, setup }` and registers
  `tool.execute.before/after`, `session.hook("idle")`, `session.hook("stop")`,
  `session.hook("prompt")`, `shell.hook("env")`, `shell.hook("create.before")`, plus a
  V1-style `ctx.event.subscribe(callback)` fallback.
- OpenCode 2.3.2 triggers only these session hooks: `experimental.idle`,
  `experimental.model.resolve`, `experimental.ws.handshake/receive/send`, `fork`,
  `http.request/response`, `model.request`, `prompt`, `retry`, `title`; the only shell
  trigger is `create.before`; tool triggers are `execute.before` and `execute.after`.
  `idle`, `stop` and `env` are dead registrations, and `ctx.event.subscribe` takes
  `{ types }` and returns an async iterable, not a callback.
- Consequence: `Stop` gates never run in a real session. All 100 `Stop` audit entries have
  `conversation_id: "ses-1"` (the Node contract test payload); the real session
  `ses_df2945772ffehbopt9n6kv1lc9` produced tool entries and a prompt record only.
- `scripts/alongkit/runner/opencode.py:75-95` builds `opencode run --format json --dir ...`
  and pins `cli_version = "1.18.32"`; 2.3.2 removed `--dir`, and
  `tests/test_runtime_adapters.py:107` asserts the flag.
- `scripts/alongkit/commands/ops.py:278` accepts only
  `claude|claude-code|codex|opencode|generic`, so `along run deepseek|deepseek-harness|dsh`
  falls through to the command proxy even though `RUNNER_MAP` and `ORCHESTRATOR_RUNTIMES`
  list them.
- `scripts/alongkit/runtime.py:200-205` treats an installed OpenCode plugin as mechanical
  when its text contains `along-gates` and `setup`; `enforcement_level` ignores heartbeat
  coverage, so `along doctor` reports `mechanical` with dead Stop gates.
- Both `~/.config/opencode/plugins/along-gates.js` (current) and the gitignored project
  `.opencode/plugins/along-gates.js` (2026-11-13) are loaded in the same run.
- `scripts/alongkit/hooks/adapters/generic.py:34-67` does not map `read`, `glob`, `grep`,
  `webfetch`, `skill`, `task`, `todowrite`.
- `scripts/alongkit/runner/deepseek.py` is a DSH (`dsh`) runner, not the DeepSeek HTTP API
  runner described by `feat--deepseek-runtime-adapter`; `format_usage_summary` is used only
  by tests and `get_opencode_session_tokens` has no caller.
- `feat--opencode-runtime-integration` REQ-8/REQ-9 (doctor projection check, stale plan
  header lint) are absent from `doctor.py` and `issue.py`.

## Goal

Make the OpenCode integration truthful and usable on the installed runtime: real lifecycle
gates, a headless runner that actually starts, and a doctor that reports `mechanical` only
when lifecycle hooks demonstrably fire. Restore consistency between the runtime registry and
the CLI, and close the accumulated acceptance-criteria gaps without touching unrelated
subsystems.

## Decisions to confirm in step 1

- D1: Support OpenCode 2.x only. Drop the V1 `AlongPlugin` export and the `--dir` path
  instead of maintaining a 1.18.32 branch. Minimum supported runtime becomes 2.3.2,
  recorded in a fixture and in `docs/topic--runtime-hooks-and-gates.md`.
- D2: `experimental.idle` is the Stop-equivalent signal. Evaluate the Stop gates once per
  idle per session, skip `background: true` idle events, and keep `prompt` recording
  separate.
- D3: `deepseek` stays a DSH alias. The DeepSeek HTTP API runner is split into a new ticket;
  this ticket corrects the claims, makes the alias reachable, and removes `--base-url`
  wiring for adapters that do not support it.
- D4: Read-only OpenCode tools (`read`, `glob`, `grep`, `webfetch`, `list`) are an explicit
  allowlist, not `unmapped_tool`; `skill`, `task`, `todowrite` are mapped and gated.

## Steps

1. **Capture the live runtime contract**
   - Record `opencode --version` and `opencode run --help` (2.3.2) as
     `tests/fixtures/runtimes/opencode/2.3.2/{version.txt,help.txt}`; keep the 1.18.32
     fixture only for history.
   - Add `tests/fixtures/runtimes/opencode/2.3.2/contract.json` with `run_flags`,
     `tool_hooks`, `session_hooks`, `shell_hooks`, sourced from the recorded help and the
     installed binary.
   - Add one constant/loader so tests, the installer and the doctor read the same contract.
   - Verify: no behavior change yet; contract tests prove the loader finds the fixture.

2. **Fix plugin lifecycle coverage** (`scripts/alongkit/hooks/opencode_plugin.js`)
   - Replace `session.hook("idle")`/`("stop")` with `session.hook("experimental.idle")`;
     map the payload `{ sessionID, background }`, skip background idle, and dedupe Stop
     evaluation per session.
   - Remove the `ctx.event.subscribe(callback)` fallback (dead by contract) or rewrite it as
     `for await (const event of ctx.event.subscribe({ types }))` with an AbortController;
     prefer removal unless a second signal is needed.
   - Remove `shell.hook("env")`; keep `shell.hook("create.before")` as the only env path.
   - Drop the V1 `AlongPlugin` export per D1; keep `{ id: "along-gates", setup }`.
   - Make `setup` idempotent across duplicate plugin copies with a process-wide guard that
     does not mask a genuine re-setup after reload.
   - Update `tests/test_opencode_runtime.py` to invoke the registered hooks with real 2.3.2
     payload shapes and assert: `experimental.idle` registered, `idle`/`stop`/`env` absent,
     one Stop evaluation per idle, payload `sessionID` propagated, no throw when optional
     fields are missing.
   - Verify: Node contract tests alone (hermetic, no model call).

3. **Fix the headless runner and CLI reachability**
   - `runner/opencode.py`: drop `--dir`, keep `cwd`; resolve the binary version once per run
     and reject runtimes outside the supported range with an explicit error; keep
     `--format json`, `--auto`, `-m`, and the positional prompt.
   - `commands/ops.py`: derive the accepted `along run` targets from `RUNNER_MAP` (keeping
     the `antigravity|agy` branch separate) so `deepseek`, `deepseek-harness` and `dsh` reach
     their runner; pass `--base-url` only to adapters that declare support.
   - `runner/deepseek.py`: label the runner as DSH, resolve `dsh --version` when the binary
     exists, mark the version unverified otherwise, and either wire `format_usage_summary`
     into the run summary/record or delete it; delete `get_opencode_session_tokens` unless
     it is used by the doctor work in step 4.
   - Tests: fixture-driven flag assertions (a used flag missing from `help.txt` fails),
     CLI reachability for every `RUNNER_MAP` key, dry-run payloads for opencode/deepseek/dsh,
     and a regression test for the old `--dir` command.
   - Verify: `along run opencode --dry-run`, `along run dsh --dry-run`,
     `along run deepseek --dry-run` produce adapter payloads, not command-proxy errors.

4. **Make doctor truthful** (`scripts/alongkit/runtime.py`, `commands/doctor.py`)
   - `along_hooks_registered("opencode")`: require the contract hook names, compare the
     installed plugin with the source template (stale copy), and detect a second copy of the
     same plugin id (global plus project).
   - Heartbeat: add a lifecycle heartbeat updated only for `Stop`/`experimental.idle`/
     `UserPromptSubmit`, keeping the existing per-runtime key backward compatible;
     `enforcement_level` requires both valid registration and a fresh lifecycle heartbeat.
   - `doctor.py`: print the duplicate/stale warnings and the reason when the level degrades
     to `advisory`.
   - Tests: `setup`-only plugin reports advisory; valid names without a lifecycle heartbeat
     report advisory; valid names plus lifecycle heartbeat report mechanical; duplicate copy
     warns; other runtimes (claude/codex/antigravity) keep their current verdicts.

5. **Complete the adapter tool map and audit hygiene**
   - `hooks/adapters/generic.py` / `opencode.py`: add an explicit read-only set
     (`read`, `glob`, `grep`, `webfetch`, `list`) bypassed before the `unmapped_tool` audit,
     and map `skill`, `task`, `todowrite` to gated tool names.
   - Document the decision in `docs/topic--runtime-hooks-and-gates.md`.
   - Tests: every OpenCode tool name recorded in the audit is either mapped or read-only;
     no `unmapped_tool` for `skill`/`task`.

6. **Close the remaining ticket-AC gaps**
   - `commands/doctor.py`: verify that `ISSUES.md` plan annotations match front matter
     `plan_status`, and report mismatches as a warning.
   - `commands/issue.py lint`: flag a `plan.md` with `Status: proposed` or
     `Status: needs approval` when `plan_status: approved`.
   - `commands/issue.py find`: carry the front matter `title` (fallback to H1) in the
     discovery payload.
   - `hooks/config.py`: prune a stale project `along-gates.js` when installing globally.
   - Tests for all four, including a legacy issue without `title:`.

7. **Hygiene and verification**
   - Test cleanup: `tests/test_docs.py:25-92`, `tests/test_skills_and_scripts.py:1757-1768`
     and `:1977`, and replace the vacuous fence regex in
     `tests/test_system_comparisons.py:64-69` with a real opening-fence counter.
   - Full gate: `python .along/scripts/test.py`, `along sanitize`, `along issue lint`,
     `along doctor`, and `git diff --stat`.
   - Manual live check (explicit step, may consume one model call): a trivial
     `opencode run` in this repo produces a `PreToolUse` audit entry plus a lifecycle
     heartbeat, and `along doctor` still reports `mechanical`; before step 4 it must report
     `advisory`.
   - Update `docs/topic--runtime-hooks-and-gates.md`, `docs/topic--cli-reference.md` and the
     runtime matrix; add an ADR for D1 (2.x only) and D2 (idle as Stop).
   - Wrap with `along wrap opencode-runtime-integration-defects` and record decisions.

## Acceptance criteria

- [ ] A real OpenCode 2.3.2 session writes an idle/Stop audit entry with its real `ses_...`
  id; the Node contract test proves the hook name and single evaluation.
- [ ] `along run opencode --dry-run` builds a command `opencode run` accepts on 2.3.2, and a
  live trivial run completes.
- [ ] `along run dsh --dry-run` and `along run deepseek --dry-run` reach the DSH runner.
- [ ] `along doctor` reports `advisory` for a `setup`-only plugin and `mechanical` only
  after valid hook names and a lifecycle heartbeat.
- [ ] A duplicate plugin copy is reported by doctor and pruned by a global install.
- [ ] OpenCode sessions produce no `unmapped_tool` for read-only tools, `skill`, `task` or
  `todowrite`.
- [ ] `along doctor entities` flags a projection/front-matter `plan_status` mismatch and
  `along issue lint` flags a stale `Status: proposed` header.
- [ ] `along issue find` prints the title for issues that have one.
- [ ] The fence test fails on an unclosed fence in the guarded document.
- [ ] `along sanitize` is clean and `python .along/scripts/test.py` is green.

## Scope notes

- Crosses a JS plugin, the Python runner layer, the CLI parser, runtime/doctor reporting,
  adapters, installers, tests and docs: use the role-based step loop with a review after
  each step, and keep steps 2-3 independent so they can land separately.
- Do not touch `feat--cursor-agent-and-rules-integration` or its plan; another session owns
  it. Do not touch Antigravity, the gate engine, telemetry spans, or the DeepSeek HTTP API.
- Pre-existing lint warnings across the other 33 issues are out of scope unless the new
  `plan_status` check produces them.
- Every new defect found outside these requirements is filed as a separate issue, not fixed
  here.
