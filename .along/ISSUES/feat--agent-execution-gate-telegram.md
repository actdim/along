---
protocol: along
protocol_version: "4.0.1"
slug: agent-execution-gate-telegram
type: feat
status: open
priority: high
created: 2026-09-23
updated: 2026-09-23
agent: antigravity
tags: [telegram, live-card, execution-gate, permission-hook, fail-safe, human-in-the-loop]
milestone: v5.0.0-agent-run-protocol-and-observability
blocked_by: [feat--agent-run-protocol-core]
related: [feat--agent-runtime-runner-antigravity]
parent: feat--agent-run-protocol-and-observability
---

# Execution Gate & Telegram Live Status Card

## Goal
Implement an interactive execution gate that pauses autonomous agent runs before high-risk operations and renders an in-place updating Live Status Card in Telegram with progress milestones and inline approval/rejection buttons.

## Problem Statement
Autonomous agents operating in background or VPS environments can execute destructive commands (e.g. `rm -rf`, `git push --force`, remote API mutations) without oversight. Sending flood-style chat notifications creates alert fatigue and loses context. An ergonomic, noise-free operator interface is required.

## Technical Specifications

### 1. Synchronous Blocking Permission Hook
- Implement pre-execution guard hook invoked before tool execution.
- High-risk heuristic classification:
  - Destructive filesystem commands (`rm`, `shutil.rmtree`, formatting).
  - Dangerous Git operations (`push --force`, `reset --hard`, branch deletions).
  - External network egress (deploy scripts, production API mutations).
- When a dangerous pattern matches, the hook blocks process execution, generates an approval request ID, and dispatches a callback event.

### 2. Telegram Live Status Card Pattern
- Single in-place editable message per run (`editMessageText`) via Telegram Bot API:
  - **Header**: `[Run #421] Task: feat--auth-refresh | Status: WAITING FOR APPROVAL`
  - **Milestone Progress**: Compact checklist showing completed steps:
    ```text
    [x] Read package.json
    [x] Search codebase (AST)
    [x] Run unit tests (14/14 passed)
    [!] Dangerous action: Deploy to staging
    ```
  - **Inline Action Buttons**:
    - `[ Approve ]` (sends callback data `approve:<req_id>`)
    - `[ Reject ]` (sends callback data `reject:<req_id>`)
    - `[ View Trace ]` (direct URL to OpenObserve/Aspire trace dashboard)
- Upon decision, the message updates in-place to record the decision and actor:
  `[x] Action approved by @admin at 14:22`.

### 3. Fail-Safe Timeout & Security
- Configurable decision timeout (default: 120 seconds). If the user does not respond within the window, the hook automatically aborts with exit code 1 (`Action rejected: decision timed out`).
- Strict user authorization: callback queries are validated against an authorized Telegram `user_id` allowlist.
- Secret sanitization: command strings displayed in Telegram are sanitized to strip passwords and API keys.

## Acceptance Criteria
- [ ] Blocking permission hook halts tool execution until callback received.
- [ ] Telegram Bot creates and updates a single message per run without chat flooding.
- [ ] Inline approval and rejection callbacks successfully unblock or terminate the hook process.
- [ ] Timeout fail-safe automatically aborts execution if no response is received within timeout window.
- [ ] Unauthorized Telegram user interactions are rejected and logged.
