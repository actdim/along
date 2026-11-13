---
protocol: along
protocol_version: "4.8.1"
slug: opencode-runtime-v2-hardening
type: bug
status: done
completed: 2026-11-13
priority: high
created: 2026-11-13
updated: 2026-11-13
agent: antigravity
tags: [runtime, opencode, hooks, v2, gates, hardening]
blocked_by: []
related: [feat--opencode-runtime-integration]
plan_status: approved
---

# OpenCode Runtime V2 Plugin Hardening and Lifecycle Hook Completeness

## Problem Statement

A live field evaluation of the OpenCode integration in OpenCode 1.18.32 identified critical failures across loading, lifecycle coverage, installer configuration, and argument normalization:
1. P0: Plugin fails to load in OpenCode 1.18.32 with `PluginModule.LoadError: Plugin must export a default definition with an id and an effect or setup function. (cause: SchemaError(Expected object at ["default"]))` because the plugin exported a V1 function instead of a V2 definition object `{ id, setup }`.
2. P0: Official installers (`install.ps1`, `install.sh`) omitted `opencode` from the hook registration switch loop, leaving the plugin uninstalled during standard setup.
3. P0: `shell.env` in 1.18.32 passes `{ cwd }` without `sessionID`, leaving session binding unpopulated unless cached from tool events.
4. P1: `along doctor` gave a false "mechanical" status by checking file substring existence without validating V2 syntax or heartbeat freshness.
5. P1: Hook spawn in `opencode_plugin.js` was fail-open without timeout, hardcoded `python`, and swallowed spawn errors silently.
6. P1: OpenCode lacked Stop and UserPromptSubmit lifecycle equivalents; Stop gates were never evaluated.
7. P1: Tool argument normalization in `GenericCliAdapter` and `OpenCodeAdapter` missed OpenCode's camelCase schemas (`newString`, `oldString`, and `execute` tool's `{ code }`).
8. P2: `detect_agent()` in `vocabulary.py` read `AGENT=1` and set runtime to `"1"`, falling back to advisory.
9. P2: Tests only tested Python mocks without running Node against the actual plugin script.

## Requirements

- REQ-1: `scripts/alongkit/hooks/opencode_plugin.js` MUST default-export `{ id: "along-gates", async setup(ctx) }` for OpenCode V2, and retain `AlongPlugin` named export for backwards compatibility.
- REQ-2: In `setup(ctx)`, the plugin MUST register `ctx.tool.hook("execute.before")`, `ctx.tool.hook("execute.after")`, `ctx.session.hook("idle")` / `ctx.session.hook("stop")` (for Stop-gate evaluations), `ctx.session.hook("prompt")` (for prompt turn baselines), and `ctx.shell.hook("env")` / `ctx.shell.hook("create.before")`.
- REQ-3: `opencode_plugin.js` MUST implement a session ID cache across tool and prompt events, injecting session keys even when `shell.env` receives `{ cwd }` without `sessionID`.
- REQ-4: `runAlongHook` MUST use a configurable timeout (default 10s), resolve Python interpreter intelligently (`ALONG_PYTHON`, venv python, `py -3`, `python3`, `python`), log errors to `~/.along/diagnostics/opencode-hook.log`, and throw errors on gate denial.
- REQ-5: `GenericCliAdapter` and `OpenCodeAdapter` MUST normalize `newString`, `oldString`, `filePath`, and `execute` tool's `code` parameter into standard `ReplacementContent`, `TargetFile`, and `CommandLine`.
- REQ-6: `detect_agent()` in `vocabulary.py` MUST ignore boolean or numeric flag values (`"1"`, `"0"`, `"true"`, `"false"`) in `AGENT` and prioritize specific runtime markers (`OPENCODE_SESSION_ID`, `OPENCODE_AGENT`, `OPENCODE_CLI`).
- REQ-7: `install.ps1` and `install.sh` MUST include `opencode` in their global hook registration loops, mapping `$OpencodeHome` / `$OPENCODE_HOME`, and prune obsolete `along-opencode-plugin.js`.
- REQ-8: `along doctor` MUST verify that the installed OpenCode plugin exports V2 definition syntax and check heartbeat freshness before reporting mechanical enforcement.
- REQ-9: Repository `.gitignore` MUST include `.opencode/` to avoid committing local plugin installations.
- REQ-10: Hermetic Node integration test MUST execute `opencode_plugin.js` under `node` to verify definition structure, hook registrations, and payload serialization.

## Acceptance Criteria

- [x] `opencode_plugin.js` exports `{ id: "along-gates", async setup(ctx) }` and loads cleanly in OpenCode 1.18.32 with 0 errors.
- [x] Tool hooks, session idle/stop hooks, and shell env hooks register successfully in OpenCode.
- [x] `GenericCliAdapter` and `OpenCodeAdapter` correctly parse `newString`, `oldString`, and `code` parameters.
- [x] `detect_agent()` identifies OpenCode correctly when `AGENT=1` is set.
- [x] `install.ps1` and `install.sh` register hooks for `opencode` target.
- [x] `along doctor` validates V2 plugin structure and heartbeat freshness.
- [x] `.gitignore` contains `.opencode/`.
- [x] Node integration test verifies plugin loading and hook registration.
- [x] All automated tests pass hermetically.
