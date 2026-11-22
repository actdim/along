---
protocol: along
protocol_version: "4.9.1"
slug: local-llm-runtime-harness
type: feat
status: open
priority: high
created: 2026-11-22
updated: 2026-11-22
agent: antigravity
tags: [epic, harness, local-llm, llamacpp, testing, runtimes]
blocked_by: []
related: [feat--autonomous-multi-runtime-mvp, feat--agent-run-protocol-and-observability]
children:
  - feat--local-llm-substrate-env-config
  - feat--runtime-integration-tests-local-llm
  - feat--local-llm-micro-orchestrator
  - feat--webdev-nl-local-runner
---

# Epic: Local LLM Runtime Harness & Integration Substrate

## Problem

Along's governance protocol, mechanical hooks (PreToolUse/Stop), multi-agent supervisor (`along orchestrate`), and WebDev browser verification (`along webdev`) currently lack an offline, local-first execution and testing harness:

1. **Test Verification Gap**: Unit tests rely on mocks and cannot detect real CLI drift (Codex, OpenCode, DSH, Claude Code). Integration tests against real binaries were missing because cloud APIs are expensive, non-deterministic, or unavailable in offline environments.
2. **Missing Substrate Binding**: While modern local inference engines (such as `llama-server` build 12255 with Qwen2.5-Coder-7B) natively provide OpenAI Responses API, Chat Completions, and Anthropic Messages API on local ports (e.g. `127.0.0.1:8080`), Along lacked standardized `.env` binding, lifecycle auto-start, and a documented tools directory contract.
3. **Supervisor Cloud Dependency**: The cross-runtime supervisor required cloud models for reasoning, brief synthesis, and gate denial diagnosis, preventing autonomous offline operation.
4. **Open-Ended WebDev Testing**: Browser scenario testing could not self-heal or adapt selectors without cloud LLM calls.

## Goal & Architecture

Provide an end-to-end Local LLM Runtime Harness for Along on Windows and Linux hosts:
- Connects Along directly to a local inference engine (`llama-server`) running at `http://127.0.0.1:8080` (or configured via `.env`).
- Exercises real agent CLIs (`codex`, `opencode`, `dsh`, and `claude`) in self-contained integration tests to mechanically verify hook interception and gate enforcement.
- Provides a local micro-orchestrator capable of synthesizing briefs, evaluating step reviews, and triaging gate denials autonomously.
- Powers autonomous, self-healing WebDev browser verification from natural language instructions.

## Child Work Packages

| Package | Slug | Priority | Description |
| --- | --- | --- | --- |
| WP-1 | `feat--local-llm-substrate-env-config` | High | Environment variables (`.env`, `ALONG_*`), tools directory contract (`docs/topic--local-llm-substrate.md`), and lifecycle helper (`alongkit.local_llm`). |
| WP-2 | `feat--runtime-integration-tests-local-llm` | High | Self-contained E2E integration test suite (`tests/test_runtime_e2e_local.py`) verifying real CLI binaries against local inference. |
| WP-3 | `feat--local-llm-micro-orchestrator` | Medium | Local reasoning layer in `alongkit.orchestrator` for autonomous offline multi-agent dispatch (`along orchestrate --local`). |
| WP-4 | `feat--webdev-nl-local-runner` | Medium | Natural language WebDev test runner with self-healing selector loop (`along webdev run-nl --auto-heal`). |

## Requirements

### 1. Unified Substrate Configuration (REQ-1)
- The harness MUST be configurable via `.env` without hardcoding machine-specific absolute paths into Git.
- The harness MUST support probing `/health` and managing external server lifecycle via PowerShell/scripts on Windows.

### 2. Deterministic Integration Verification (REQ-2)
- Integration tests MUST execute real installed binaries against `127.0.0.1:8080` with model `local`.
- Both authorized tool execution (gate pass) and blocked unauthorized execution (gate denial) MUST be asserted.

### 3. Local Autonomous Dispatch (REQ-3)
- The supervisor MUST support offline operation (`--local`), replacing cloud LLM calls with structured JSON prompts to the local model (`qwen2.5-coder:7b`).

### 4. Self-Healing Browser Testing (REQ-4)
- WebDev execution MUST support compiling natural language to Playwright actions and repairing broken selectors using DOM context through the local model.

## Acceptance Criteria

- [ ] All 4 child work packages are implemented, tested, and closed.
- [ ] Real runtime integration tests for Codex, OpenCode, and DSH pass on local Windows harness.
- [ ] Documented directory contract published in `docs/topic--local-llm-substrate.md`.
- [ ] Zero cloud API dependencies required for local integration testing and local orchestration.
