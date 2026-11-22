---
protocol: along
protocol_version: "4.9.1"
slug: runtime-integration-tests-local-llm
type: feat
status: open
priority: high
created: 2026-11-22
updated: 2026-11-22
agent: antigravity
tags: [integration, tests, runtimes, codex, opencode, dsh, local-llm]
blocked_by: [feat--local-llm-substrate-env-config]
related: [feat--local-llm-micro-orchestrator, feat--webdev-nl-local-runner]
parent: feat--local-llm-runtime-harness
---

# Real Runtime Integration Tests with Local LLM (Codex, OpenCode, DSH)

## Problem

Along relies on mechanical PreToolUse and Stop hooks to enforce its governance protocol (such as `require-active-issue`, `workspace-containment`, and `untracked-exports`). 

Existing tests in `tests/test_hooks_*.py` and `tests/test_runner_*.py` are hermetic unit tests relying on mocks. Mocks only verify Along's internal protocol parsing, but cannot detect contract drift when external CLI binaries (`codex`, `opencode`, `dsh`) change their internal tool schemas, JSONL streaming events, or permission handling.

Without integration tests executing real CLI binaries against a local OpenAI-compatible inference engine:
1. Breaking changes in runtime CLI versions remain undetected until real developer deployment.
2. Hook registration across `.codex/`, `.opencode/`, and system environments is not verified against actual subprocess executions.
3. Turn parsing and token extraction in `alongkit.runner` cannot be validated under real streaming conditions.

## Requirements

### 1. Self-Contained E2E Test Suite (REQ-1)
- The test suite MUST reside in `tests/test_runtime_e2e_local.py` and be registered in `tests/_integration.py`.
- The suite MUST be opt-in and execute only when:
  - An explicit flag or environment variable is set (`ALONG_REAL_E2E=1` or `ALONG_LOCAL_LLM=1`), OR
  - The local server at `http://127.0.0.1:8080/health` responds with `{"status": "ok"}`.
- If the server is unreachable and auto-start is disabled, the suite MUST skip gracefully (`self.skipTest(...)`) without failing standard test runs.

### 2. Runtime Coverage (REQ-2)
- The test suite MUST test all installed agent CLI binaries on the host:
  - **OpenAI Codex (`codex`)**:
    - Executes `codex exec` with temporary arguments `-c model_provider=llamacpp`, `-c model_providers.llamacpp.base_url=http://127.0.0.1:8080/v1`, `-c model_providers.llamacpp.wire_api=responses`, `-m local`.
    - Verifies real tool calls trigger `along_hook.py`.
  - **OpenCode (`opencode`)**:
    - Executes `opencode` with an isolated configuration targeting `http://127.0.0.1:8080/v1` and model `local`.
    - Verifies `opencode_plugin.js` hook execution.
  - **DeepSeek Harness (`dsh`)**:
    - Executes `dsh` with `DEEPSEEK_BASE_URL=http://127.0.0.1:8080/v1` and `DEEPSEEK_MODEL=local`.
  - **Claude Code (`claude`)** (conditional):
    - If `llama-server` supports native Anthropic Messages API (`/v1/messages`), executes `claude -p` targeting `http://127.0.0.1:8080`.

### 3. Verification Scenarios & Assertions (REQ-3)
- **Scenario A: Gate Pass (Authorized Execution)**:
  - Repository has an active issue with status `in-progress` and approved plan.
  - Prompt: `"Create a file named along_test_marker.txt with content 'OK' using your write tool. Do not do anything else."`
  - Assertions:
    - PreToolUse hook allows the tool call.
    - File `along_test_marker.txt` is created on disk.
    - CLI process exits with code 0.
    - Runner parses output and usage tokens without exception.
- **Scenario B: Gate Denial (Unauthorized Execution)**:
  - Repository has NO active issue (or plan is not approved).
  - Prompt commands file modification.
  - Assertions:
    - PreToolUse hook denies the action.
    - File is NOT created or modified on disk.
    - CLI process reports gate failure or halts.
    - Gate denial record is written to `.along/diagnostics/`.

## Implementation Plan

1. **Test Fixtures & Sandbox Scaffold**:
   - Create sandbox helper that initialises a clean temporary directory with `along init` and registers target runtime hooks via `along hook install --runtime <R>`.
2. **Subprocess Execution Harness**:
   - Implement subprocess wrappers passing proper environment and flags to `codex`, `opencode`, and `dsh`.
3. **Integration Test Module**:
   - Write `tests/test_runtime_e2e_local.py` implementing Scenarios A and B for each runtime.
   - Register module in `tests/_integration.py`.
4. **Convenience Runner Script**:
   - Add `scripts/harness/run-local-tests.ps1` for one-command test execution on Windows.

## Acceptance Criteria

- [ ] `tests/test_runtime_e2e_local.py` runs end-to-end against local `llama-server` running Qwen2.5-Coder-7B.
- [ ] Codex, OpenCode, and DSH passes and denials are mechanically verified.
- [ ] Test gracefully skips when `llama-server` is not running.
- [ ] Registered in `tests/_integration.py` and compatible with `python .along/scripts/test.py --integration`.
