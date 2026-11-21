# Implementation Plan: Fix OpenCode V2 Hook Crash & Runner CLI Contract

## Context & Root Cause Analysis

In OpenCode live sessions, every shell tool execution instantly crashed with:
```json
{"error":{"type":"unknown","message":"undefined is not an object (evaluating 'output.env')"}}
```
This caused terminal UI black-screen flickers, broken execution streams, and frozen agent sessions.

### Identified Defects

1. **`scripts/alongkit/hooks/opencode_plugin.js:256`**:
   - In OpenCode V2, `ctx.shell.hook("create.before", async (event) => ...)` passes only **one** argument: `event` (`{ command, cwd, env, timeout, ... }`).
   - The plugin registered `async (input, output) => handleShellEnv(input, output)`.
   - `handleShellEnv` extracted `sid` and then unconditionally evaluated `output.env = output.env || {}`.
   - Since `output` was `undefined`, JavaScriptCore (JSC in Bun) threw `TypeError: undefined is not an object (evaluating 'output.env')`.
   - This unhandled hook exception killed the tool execution pipeline inside the OpenCode host process.

2. **`scripts/alongkit/runner/opencode.py`**:
   - `OpenCodeRunner` configured `brief_via_stdin = True` and omitted `prompt` in `build_command`.
   - `opencode run` CLI does **not** read from stdin; it expects `opencode run [message..]` as positional CLI arguments.
   - Piped prompts are ignored or hang the CLI.

3. **`scripts/alongkit/commands/ops.py`**:
   - `--timeout <val>` swallowed `ValueError` with `except ValueError: timeout = None`. Invalid timeout values silently bypassed timeout enforcement.
   - `record.get("exit_code") or 0` mapped `None` to `0`, falsely reporting abnormal terminations as successful.

4. **`scripts/alongkit/runner/base.py`**:
   - Dry-run payload omitted `env_overrides` and `base_url`, hiding environment configuration during validation.

5. **`tests/test_opencode_runtime.py`**:
   - The test only checked that hook names were pushed to a mock array during `setup(ctx)`. It never invoked the registered hook functions, hiding the fatal runtime crash.

---

## Proposed Changes

### 1. `scripts/alongkit/hooks/opencode_plugin.js`
- Rewrite `handleShellEnv(input, output)`:
  - If `sid` is present:
    - If `output && typeof output === "object"`, mutate `output.env`.
    - If `input && typeof input === "object"`, mutate `input.env`.
  - Guard all property accesses against `null` or `undefined`.
- Update `extractSessionId`:
  - Support OpenCode V2 event structures (`event?.properties?.sessionID`, `event?.data?.sessionID`, `event?.info?.id`).
- Add defensive null-checks in `handlePreTool`, `handlePostTool`, `handleStop`, and `handlePrompt`.

### 2. `scripts/alongkit/runner/opencode.py`
- Set `brief_via_stdin: bool = False`.
- In `build_command(self, prompt: Optional[str] = None)`:
  - If `prompt`: append `prompt` to `cmd` as a positional argument.

### 3. `scripts/alongkit/commands/ops.py`
- In `--timeout` parser: raise an error on non-integer input with exit code 1.
- In return statement: `ret = record.get("exit_code"); return ret if ret is not None else 1`.

### 4. `scripts/alongkit/runner/base.py`
- Include `"env_overrides": self.env_overrides or {}` and relevant runtime environment settings in `dry_payload`.

### 5. `tests/test_opencode_runtime.py`
- Update `test_node_plugin_module_contract`:
  - Execute registered hooks with mock event payloads:
    - `shell.create.before` with `{ command: "git status", cwd: "/test" }` and `undefined` output.
    - `shell.env` with `{ cwd: "/test" }` and `{ env: {} }`.
    - `tool.execute.before` with `{ tool: "bash", input: { command: "ls" } }`.
    - `session.idle` and `session.stop`.
  - Assert that all hooks complete without throwing `TypeError`.
- Add unit test in `tests/test_runtime_adapters.py` verifying `OpenCodeRunner.build_command("Brief text")` includes `"Brief text"` in command arguments and sets `brief_via_stdin = False`.

---

## Verification Plan

### Automated Tests
1. Run Node contract integration test:
   `python -m unittest tests/test_opencode_runtime.py`
2. Run runtime adapter tests:
   `python -m unittest tests/test_runtime_adapters.py`
3. Run runtime contract tests:
   `python -m unittest tests/test_runtime_contracts.py`
4. Run full Along test suite:
   `python .along/scripts/test.py`
