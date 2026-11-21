---
protocol: along
protocol_version: "4.9.1"
slug: webdev-local-llm-engine
type: feat
status: done
completed: 2026-11-22
priority: medium
created: 2026-11-21
updated: 2026-11-22
agent: antigravity
tags: [webdev, local-llm, offline, compiler, runner]
milestone: v5.2.0-external-harness-expansion
blocked_by: [feat--deepseek-runtime-adapter]
related: [feat--along-webdev-runner, feat--along-report-engine]
plan_status: approved
---

# Self-Contained Offline NL-to-WebDev Step Compiler and Runner

## Goal
Implement a self-contained, offline natural-language-to-WebDev execution engine in `along webdev nl`. This engine translates high-level natural language verification instructions (e.g. "open http://localhost:3000, type admin into login field, click Submit, assert profile badge is visible, take screenshot") into validated `along-webdev` Playwright/YAML scenarios without requiring external cloud API keys or online model connectivity.

## Problem
Currently, browser verification in external harnesses (DSH, Claude Code, OpenCode) requires an active cloud model or paid API access to translate developer intent into execution steps. In air-gapped, CI, or cost-constrained environments without internet access or LLM credentials:
1. Agents without browser integration cannot perform UI regression tests.
2. Developers cannot execute ad-hoc conversational browser checks locally without spinning up expensive cloud LLMs.
3. No standard bridge exists between natural language instructions and Along's existing deterministic `AlongWebDevRunner` substrate.

## Requirements

### 1. Pluggable Local Inference Substrate (REQ-1)
- Implement `LocalInferenceClient` in `scripts/alongkit/webdev/local_llm.py`.
- Support auto-discovery of local OpenAI-compatible endpoints (`http://127.0.0.1:11434/v1` for Ollama, `http://127.0.0.1:8080/v1` for llama-server / vLLM).
- Provide a deterministic fallback rule-based template parser for standard patterns when no local server daemon is running.
- Respect `ALONG_LOCAL_LLM_ENDPOINT` and `ALONG_LOCAL_LLM_MODEL`.

### 2. Natural Language Scenario Compiler (REQ-2)
- Implement `NLScenarioCompiler` in `scripts/alongkit/webdev/compiler.py`.
- Translate input natural language sentences into structured YAML steps: `navigate`, `click`, `fill`, `assert_visible`, `screenshot`, `wait_for`.
- Enforce security constraints: validate navigation targets against allowed host/origin whitelist, block navigation to untrusted external schemes, and redact sensitive tokens.

### 3. CLI Integration in Along WebDev (REQ-3)
- Extend `scripts/along_webdev.py` with subcommand `along webdev nl "<instruction>"`.
- Options:
  - `--url <base_url>`: Default base URL for relative navigation paths.
  - `--backend {auto,local-http,template}`: Inference backend selection.
  - `--dry-run`: Output generated YAML scenario to stdout without launching browser.
  - `--run`: Immediately dispatch compiled scenario to `AlongWebDevRunner`.

### 4. Verification and Hermetic Tests (REQ-4)
- Add comprehensive unit tests in `tests/test_webdev_local_llm.py`.
- Test template compiler, mock local HTTP response parsing, origin security validation, and runner execution integration.

## Acceptance Criteria
- [x] `along webdev nl` command exists and accepts conversational verification instructions.
- [x] Compiler parses natural language into valid Along WebDev scenario schemas.
- [x] Navigation outside allowed origins is rejected with clear error message.
- [x] Unit tests pass hermetically without network or external model access.
