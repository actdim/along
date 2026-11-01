---
protocol: along
protocol_version: "4.5.4"
slug: deepseek-runtime-adapter
type: feat
status: open
priority: medium
created: 2026-10-30
updated: 2026-10-30
agent: antigravity
tags: [deepseek, runtime, runner, adapter, cli]
milestone: v5.2.0-external-harness-expansion
blocked_by: []
related: [feat--deepseek-harness-bridge, feat--agent-runtime-adapters-claude-codex-opencode]
---

# DeepSeek Runtime Adapter for Headless CLI Orchestration

## Goal

Provide first-class headless CLI runner support for DeepSeek models (DeepSeek-V3, DeepSeek-R1) in `along run deepseek` and `along orchestrate [--scout|--architect|--implementer|--reviewer] deepseek`, enabling cost-effective reasoning and code modification in heterogeneous multi-agent loops.

## Problem Statement

Currently, `scripts/alongkit/runner/` defines adapters for `claude` (Claude Code), `codex` (OpenAI Codex), `opencode`, and `generic`. DeepSeek is frequently requested as an economical and capable reasoning model for Scout, Architect, or Implementer phases. However:
1. `deepseek` is not registered in `RUNNER_MAP` or `ORCHESTRATOR_RUNTIMES`. Running `along orchestrate --implementer deepseek` raises an argument choice error.
2. `RUNTIME_ENV_ALLOW` sets do not include `DEEPSEEK_API_KEY` or `DEEPSEEK_BASE_URL`, so child runner processes have their credentials stripped unless manually passed through.
3. Users must manually configure `opencode` with custom environment overrides and model flags, which creates unnecessary friction.

## Requirements

### 1. Runner Registration and CLI Recognition (REQ-1)
- Register `deepseek` in `alongkit.runner.RUNNER_MAP` and `alongkit.orchestrator.ORCHESTRATOR_RUNTIMES`.
- Support `along run deepseek [options]` and `along orchestrate --scout deepseek --implementer deepseek`.

### 2. Execution Backend Strategy (REQ-2)
- Implement `DeepSeekRunner` (derived from `BaseRunner` or backed by `OpenCodeRunner`/compatible headless driver).
- Default to `deepseek-chat` for general tasks and `deepseek-reasoner` when reasoning mode is requested.
- Support default endpoint `https://api.deepseek.com` and custom endpoints (local Ollama or vLLM).

### 3. Environment Isolation & Allowlist (REQ-3)
- Declare `DEEPSEEK_API_KEY`, `DEEPSEEK_BASE_URL`, and `DEEPSEEK_MODEL` in the runner's `RUNTIME_ENV_ALLOW`.
- Ensure other provider keys (Anthropic, Telegram token, OpenAI) are strictly excluded from the child environment.

### 4. Output Parsing & Error Handling (REQ-4)
- Parse stdout/stderr and exit codes cleanly, mapping outcome to `done`, `fail`, `needs-input`, or `timeout`.

## Acceptance Criteria

- [ ] `deepseek` is accepted as a valid runtime by `along run` and `along orchestrate`.
- [ ] Runner constructs valid CLI execution command with `--model` and API endpoint parameters.
- [ ] Child environment contains `DEEPSEEK_API_KEY` but excludes unrelated provider secrets.
- [ ] Unit tests added to `tests/test_runtime_adapters.py` and green.
