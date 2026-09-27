---
protocol: along
protocol_version: "4.1.0"
slug: agent-interactive-stdin-bridge
type: feat
status: open
priority: high
created: 2026-09-27
updated: 2026-09-27
agent: antigravity
tags: [telegram, bridge, stdin, interactive, human-in-the-loop, clarification, ask-question]
milestone: v5.0.0-agent-run-protocol-and-observability
blocked_by: [feat--agent-execution-gate-telegram]
related: [feat--agent-runtime-runner-antigravity, feat--agent-runtime-adapters-claude-codex-opencode]
parent: feat--agent-run-protocol-and-observability
---

# Telegram Interactive Clarification & Stdin Bridge

## Goal
Implement a bidirectional interactive bridge connecting running agent input requests (stdin prompts, `ask_question` tool calls, and clarification questions) to the remote Telegram operator interface, enabling operators to provide crucial answers and decisions to unblock agents during remote execution.

## Problem Statement
Current execution gate mechanisms (`[feat--agent-execution-gate-telegram]`) focus strictly on binary permission approvals (`[Approve]`, `[Reject]`) for dangerous tool actions. However, autonomous agents frequently require operator feedback during execution:
1. Interactive choice prompts (e.g. `ask_question` tool selecting architecture, trade-offs, or file targets).
2. Clarification questions when requirements are underspecified.
3. Interactive terminal prompts reading from process stdin.

Without an interactive clarification bridge, remote agent runs on a VPS either stall indefinitely waiting for stdin input, or fail prematurely when timeouts expire.

## Technical Specifications

### 1. Interactive Question & Prompt Interception
- Intercept interactive prompts across supported agent runtimes:
  - **Tool Invocations**: Intercept calls to `ask_question` or equivalent interactive subagent tools.
  - **Process Stdin**: Detect when child agent processes enter blocking read states on stdin.
- Transition run state to `WAITING_FOR_INPUT` and emit an AEP clarification event:
  - `prompt_id`: Unique identifier for the question turn.
  - `question`: Explanatory text directed to the operator.
  - `options`: Optional list of selectable responses (with recommended flags).
  - `allow_custom`: Boolean indicating if free-form text answers are accepted.

### 2. Telegram Presentation & Response Routing
- **Multi-Choice Prompts**:
  - Render selectable options as Telegram inline keyboard buttons for one-tap answers.
  - Example: `[ (1) PostgreSQL ]` `[ (2) SQLite ]`
- **Free-Form Text Responses**:
  - Operator replies directly to the question message or uses `/answer <text>`.
- **In-Place Card Update**:
  - Upon receiving an answer, update the Live Status Card in-place:
    `[x] Clarification answered by @operator: "PostgreSQL"`
  - Prevent duplicate submissions from multiple operators via atomic callback resolution.

### 3. Stdin Injection & Tool Callback Resolution
- When the daemon receives the operator response:
  - **For Stdin Prompts**: Writes the sanitized text string followed by newline directly to the child process stdin stream.
  - **For Tool Hooks**: Resolves the pending hook callback promise with the selected option or text payload.
- Record operator decision and attribution in OpenTelemetry span attributes:
  - `along.operator.answer_by = "@username"`
  - `along.operator.response_time_ms = <int>`

### 4. Fail-Safe Timeout & Default Fallbacks
- Configurable operator response timeout (default: 300 seconds).
- If the operator fails to respond before timeout:
  - If a recommended option was marked by the agent, automatically select the recommended default and log a warning.
  - Otherwise, terminate the run safely with status `TIMED_OUT_WAITING_FOR_INPUT` without leaving orphaned background processes.

## Acceptance Criteria
- [ ] Multi-choice questions (`ask_question`) rendered as inline Telegram callback buttons.
- [ ] Free-form text questions accept operator replies and pipe input directly into process stdin.
- [ ] In-place Live Status Card updates reflect submitted answers without message flood.
- [ ] Atomic resolution prevents race conditions when multiple operators view the card.
- [ ] Configurable timeout handles unanswered questions safely with fallback or clean exit.
