---
protocol: along
protocol_version: "4.9.0"
slug: opencode-shell-env-runner-fix
type: bug
status: done
completed: 2026-11-21
priority: high
created: 2026-11-21
updated: 2026-11-21
agent: antigravity
tags: [opencode, runtime, hooks, runner, bug]
blocked_by: []
related: [bug--opencode-runtime-v2-hardening]
plan_status: approved
---

# Fix OpenCode V2 hook crash and runner CLI contract

## Problem Statement

During live OpenCode sessions, every shell tool execution crashes with:
`{"error":{"type":"unknown","message":"undefined is not an object (evaluating 'output.env')"}}`
resulting in terminal UI black-screen flickers, broken execution streams, and completely stalled agent sessions.

Root causes identified in code:
1. `scripts/alongkit/hooks/opencode_plugin.js`: In OpenCode V2, `ctx.shell.hook("create.before", async (event) => ...)` passes only one argument (`event = { command, cwd, env, timeout }`) without a second `output` parameter. The plugin implementation unconditionally dereferences `output.env = output.env || {}`, throwing a fatal `TypeError` in Bun's JavaScriptCore runtime.
2. `tests/test_opencode_runtime.py`: The Node.js plugin contract test only asserted that hook names were registered into an array during `setup(ctx)`. It never invoked the registered hook functions with mock event payloads, creating false confidence.
3. `scripts/alongkit/runner/opencode.py`: `OpenCodeRunner` sets `brief_via_stdin = True` and does not pass the prompt in `build_command`. However, `opencode run` expects the prompt strictly as positional CLI arguments (`opencode run [message..]`), ignoring piped stdin or hanging.
4. `scripts/alongkit/commands/ops.py`: `--timeout` parsing swallows `ValueError` silently, and `record.get("exit_code") or 0` returns 0 when `exit_code` is `None`.
5. `scripts/alongkit/runner/base.py`: Dry-run payload omits `env` and `env_overrides`, making it impossible to verify `OPENAI_BASE_URL` without executing.

## Requirements

- REQ-1: `opencode_plugin.js` MUST guard against undefined `output` in `handleShellEnv` and mutate `input.env` (for V2 `create.before`) or `output.env` (for V1 `shell.env`) safely without throwing TypeErrors.
- REQ-2: `opencode_plugin.js` MUST defensively validate arguments in all hook handlers (`handlePreTool`, `handlePostTool`, `handleStop`, `handlePrompt`) so missing optional parameters never crash the OpenCode host process.
- REQ-3: `tests/test_opencode_runtime.py` MUST invoke registered hooks under Node.js with realistic V2 payloads (including single-argument `shell.create.before` and `execute.before`) and assert clean execution.
- REQ-4: `scripts/alongkit/runner/opencode.py` MUST configure `brief_via_stdin = False` and append prompt arguments to the CLI command array in `build_command`.
- REQ-5: `scripts/alongkit/commands/ops.py` MUST validate `--timeout` integers explicitly and raise or exit on invalid input rather than silently setting `None`, and preserve non-None exit code checks.
- REQ-6: `scripts/alongkit/runner/base.py` MUST expose configured environment variables and overrides in `dry_run` payload output.

## Acceptance Criteria

- [x] `handleShellEnv` handles both V1 `(input, output)` and V2 `(event)` signatures without throwing when `output` is undefined.
- [x] Node contract test in `tests/test_opencode_runtime.py` invokes all hook callbacks and passes hermetically.
- [x] `OpenCodeRunner.build_command` appends positional message arguments when prompt is provided.
- [x] Runner tests verify command construction for `OpenCodeRunner` with prompt.
- [x] All automated tests pass via `python .along/scripts/test.py`.
