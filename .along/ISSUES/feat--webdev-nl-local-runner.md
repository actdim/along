---
protocol: along
protocol_version: "4.9.1"
slug: webdev-nl-local-runner
type: feat
status: open
priority: medium
created: 2026-11-22
updated: 2026-11-22
agent: antigravity
tags: [webdev, playwright, nl-compiler, local-llm, self-healing]
blocked_by: [feat--local-llm-substrate-env-config]
related: [feat--runtime-integration-tests-local-llm, feat--local-llm-micro-orchestrator]
parent: feat--local-llm-runtime-harness
---

# WebDev NL Scenario Runner & Autonomous Self-Healing via Local LLM

## Problem

Along includes the `along-webdev` skill and Playwright/Chrome for Testing runtime, featuring an initial `NLScenarioCompiler` that translates natural language into declarative JSON browser actions.

However, browser testing currently lacks an autonomous feedback and verification loop:
1. **Fragile Selectors**: Web applications frequently undergo layout or DOM attribute changes. If an action fails (e.g. selector `#btn-login` is missing, or button text changed), the test execution immediately halts with an error.
2. **Open-Ended Loop**: The compiler only works in a single forward pass without receiving execution feedback. There is no automated inspection of DOM snapshots or screenshots to repair failing steps.
3. **No Autonomous Local Verification**: Developers cannot run a complete, self-healing UI test scenario offline using the local LLM (`qwen2.5-coder:7b`) without cloud API dependencies.

## Requirements

### 1. Direct Local LLM Integration (REQ-1)
- The WebDev compiler (`alongkit.webdev.compiler`) MUST bind directly to the local LLM substrate configured via `.env` (`http://127.0.0.1:8080/v1`).
- The compiler MUST accept natural language test instructions in Russian and English (e.g. `"открой /login, введи admin, нажми Войти, проверь появление .dashboard"`).

### 2. Autonomous Self-Healing Loop (REQ-2)
- When a step in a compiled scenario fails during browser execution:
  - The runner MUST capture a sanitized DOM excerpt around the target container and extract error metadata.
  - The runner MUST query the local LLM with the failure context:
    - Target action (e.g. click, fill).
    - Failed selector.
    - Simplified DOM HTML excerpt.
  - The local LLM MUST return a corrected step JSON object with an updated selector or strategy (e.g. text locator, role, or updated CSS class).
  - The runner MUST retry the step with the repaired instruction (max 2 retries per step).

### 3. CLI Subcommand & Evidence Generation (REQ-3)
- Along MUST provide a dedicated CLI command:
  - `along webdev run-nl "<instruction>" [--url <base_url>] [--auto-heal] [--screenshot]`
- The execution MUST produce structured evidence in `.along/webdev/results/`:
  - Step trace (`steps.json`).
  - Final screenshot proof (`final.png`).
  - Self-healing log recording original selector vs repaired selector (if repair occurred).

### 4. Origin & Security Boundary (REQ-4)
- Browser navigation MUST remain strictly confined to allowed local origins (`localhost`, `127.0.0.1`, and explicit dev server ports) to prevent SSRF or unauthorized external browsing.

## Implementation Plan

1. **Compiler Enhancement**:
   - Update `alongkit.webdev.compiler` to support dynamic prompt adaptation and structured JSON schema enforcement for Qwen2.5-Coder.
2. **Self-Healing Engine**:
   - Implement `SelfHealingBrowserLoop` in `alongkit.webdev.runner` to capture DOM context and execute the repair cycle.
3. **CLI Router Integration**:
   - Expose `along webdev run-nl` in `scripts/along_webdev.py` and `scripts/along_exec.py`.
4. **Verification**:
   - Unit tests in `tests/test_webdev_autofix.py` with mock DOM excerpts.
   - End-to-end browser test against a local mock HTML test server.

## Acceptance Criteria

- [ ] `along webdev run-nl` compiles and executes multi-step scenarios against local web servers.
- [ ] If a button selector changes, self-healing loop discovers the element by text/role and completes the test.
- [ ] Evidence (JSON trace and screenshots) is written to `.along/webdev/results/`.
- [ ] Confinement to local origins is strictly enforced.
