---
protocol: along
protocol_version: "4.8.1"
date: 2026-11-13
slug: opencode-runtime-v2-hardening
agent: antigravity
branch: main
commit: 6a3f472
summary: 'fix(opencode): v2 plugin definition, complete lifecycle coverage and argument normalization'
issues_advanced: []
issues_completed: [bug--opencode-runtime-v2-hardening]
decisions: []
files: [.gitignore, docs/topic--runtime-hooks-and-gates.md, install.ps1, install.sh, scripts/alongkit/commands/doctor.py, scripts/alongkit/entities/vocabulary.py, scripts/alongkit/hooks/adapters/generic.py, scripts/alongkit/hooks/config.py, scripts/alongkit/hooks/opencode_plugin.js, scripts/alongkit/runtime.py, tests/test_opencode_runtime.py]
---

# Session: Opencode runtime v2 hardening

## Summary
fix(opencode): v2 plugin definition, complete lifecycle coverage and argument normalization

## Decisions
- None (confirmed at wrap: no architectural decisions).

## Blackboard Record

Execution mode: role-based; plan revision 1; approved: true.

| Step | Title | Status | Retries | Review |
| --- | --- | --- | --- | --- |
| 1 | OpenCode V2 Plugin Rewrite | passed | 0 | yes |
| 2 | Tool Argument Normalization in Adapters | passed | 0 | yes |
| 3 | Runtime Agent Detection Hardening | passed | 0 | yes |
| 4 | Installers, Update Engine, and Repository Hygiene | passed | 0 | yes |
| 5 | Doctor Diagnostics Freshness & Honesty | passed | 0 | yes |
| 6 | Automated Verification & Session Wrap | passed | 0 | yes |

Plan: kept with the issue (`plan/plan.md`, 1 revision(s)).

### Execution Trace

#### Execution Trace: opencode-runtime-v2-hardening
- 2026-11-13T10:59:11Z plan approved (along plan approve) approved_via: cli-unverified, plan_sha256: c6a4d89790c7
- 2026-11-13T11:13:52Z test pass (Wrap Quality Gate)

### Review step-1

#### Step 1 Review: OpenCode V2 Plugin Rewrite

VERDICT: PASS

##### Findings
- `scripts/alongkit/hooks/opencode_plugin.js` rewritten with OpenCode V2 standard definition (`export default { id: "along-gates", async setup(ctx) }`) and V1 backwards-compatible export (`AlongPlugin`).
- Hook coverage expanded: `ctx.tool.hook("execute.before")`, `ctx.tool.hook("execute.after")`, `ctx.session.hook("idle")`, `ctx.session.hook("stop")`, `ctx.session.hook("prompt")`, `ctx.shell.hook("env")`, `ctx.shell.hook("create.before")`, and fallback `ctx.event.subscribe`.
- Session ID cache mechanism implemented to retain active session key across turns and inject into `shell.env` even when input lacks `sessionID`.
- Process spawn hardened: 10-second timeout, Python interpreter candidate resolution (`ALONG_PYTHON`, project venv, global venv, `py -3`, `python3`, `python`), diagnostic file logging to `~/.along/diagnostics/opencode-hook.log`, and Error throw on non-zero exit code.
- Live verification: deployed to `~/.config/opencode/plugins/along-gates.js`, verified via `opencode debug info` and confirmed zero errors or warnings in `opencode.log`.

### Review step-2

#### Step 2 Review: Tool Argument Normalization in Adapters

VERDICT: PASS

##### Findings
- `GenericCliAdapter` and `OpenCodeAdapter` updated to parse OpenCode camelCase and Code Mode parameters:
  - `newString` normalized to `ReplacementContent` and `content`.
  - `oldString` normalized to `OldString` and `Target`.
  - `filePath` normalized to `TargetFile`.
  - `execute` tool's `{ code }` parameter normalized to `CommandLine` when tool indicates command execution.
- Verified with unit tests `test_parse_edit_tool_camel_case` and `test_parse_execute_code_tool` in `tests/test_opencode_runtime.py`. All tests pass.

### Review step-3

#### Step 3 Review: Runtime Agent Detection Hardening

VERDICT: PASS

##### Findings
- `detect_agent()` in `scripts/alongkit/entities/vocabulary.py` updated to check explicit markers (`cowork`, `claude-code`, `antigravity`, `codex`, `opencode`) before evaluating generic `AGENT`.
- Added filter to ignore boolean/numeric flag values (`"1"`, `"0"`, `"true"`, `"false"`, `"yes"`, `"no"`) in `AGENT`, preventing OpenCode's `AGENT=1` from corrupting agent detection to `"1"`.
- Unit tests `test_detect_agent_ignores_boolean_agent_flag`, `test_detect_agent_ignores_boolean_agent_flag_without_markers`, and `test_detect_agent_accepts_valid_agent_string` pass cleanly.

### Review step-4

#### Step 4 Review: Installers, Update Engine, and Repository Hygiene

VERDICT: PASS

##### Findings
- Updated `install.ps1` to include `'opencode' { $OpencodeHome }` in runtime hook installation switch.
- Updated `install.sh` to include `opencode) target_home="$OPENCODE_HOME" ;;` in runtime hook installation loop.
- Updated `install_opencode_hooks` in `scripts/alongkit/hooks/config.py` to prune obsolete `along-opencode-plugin.js` when deploying `along-gates.js`.
- Added `.opencode/` to `.gitignore`.
- Verified installer conformance via `test_installers.py` (20 passed).
- Verified `along hook install --runtime opencode --global` runs idempotently.

### Review step-5

#### Step 5 Review: Doctor Diagnostics Freshness & Honesty

VERDICT: PASS

##### Findings
- `along_hooks_registered("opencode")` in `scripts/alongkit/runtime.py` updated to verify V2 syntax: requires `"setup"` in addition to `"along-gates"` or `"along_hook"`.
- `_doctor_runtime_checks` in `scripts/alongkit/commands/doctor.py` updated to calculate heartbeat freshness:
  - Outputs time delta (e.g. `(0m ago)`, `(2h ago)`).
  - Emits `[WARN]` if the last hook run is stale (>= 24 hours ago).
- Verified with `along doctor`: correctly calculated and displayed `(0m ago)` for recent runs.

### Review step-6

#### Step 6 Review: Automated Verification & Session Wrap

VERDICT: PASS

##### Findings
- Added `TestOpenCodeNodePluginContract` in `tests/test_opencode_runtime.py`:
  - Dynamically imports ESM `opencode_plugin.js` via Node.js.
  - Verifies default export definition with `id: "along-gates"` and `setup` function.
  - Verifies named `AlongPlugin` export.
  - Passes mock context and asserts all 8 hook registrations (`tool.execute.before`, `tool.execute.after`, `session.idle`, `session.stop`, `session.prompt`, `shell.env`, `shell.create.before`, `event.subscribe`).
- Executed unit tests in `test_opencode_runtime.py` (13 tests passed).
- Executed multi-subproject tests in `test_multi_subproject_find.py` (5 tests passed).
- Executed installer tests in `test_installers.py` (20 tests passed).
- Verified repository typography with `along sanitize`: 1237 files scanned, 0 banned characters.
- Live test on Windows host: deployed to `~/.config/opencode/plugins/along-gates.js` and verified with `opencode debug info` and zero error entries in `opencode.log`.
- All acceptance criteria satisfied.
