---
protocol: along
protocol_version: "4.0.1"
slug: multi-runtime-and-omnichannel-expansion
type: feat
status: open
priority: medium
created: 2026-09-23
updated: 2026-09-23
agent: antigravity
tags: [multi-runtime, claude, codex, opencode, omnichannel, discord, slack, mattermost, matrix, epic]
milestone: v6.0.0-multi-runtime-and-omnichannel-expansion
blocked_by: [feat--agent-run-protocol-and-observability]
related: []
parent: null
---

# Multi-Runtime Adapters & Omnichannel Chat Integration (Epic)

## Goal
Expand Along execution observability and interactive human-in-the-loop control across heterogeneous agent runtimes (Claude Code, OpenAI Codex, OpenCode) and omnichannel messaging platforms (Discord, Slack, Mattermost, Matrix/Element).

## Core Architectural Pillars

### 1. Universal Runtime Interoperability
- Provide standardized adapters mapping diverse runtime execution models into normalized AEP/OpenTelemetry spans.
- Support both vendor cloud CLIs (Claude, Codex) and fully open-source, local-first runtimes (OpenCode with Ollama/vLLM for air-gapped environments).

### 2. Transport-Agnostic Notification Gateway
- Abstract the Live Status Card operator interface behind a clean `NotificationGateway` abstraction:
  - `send_run_card(run_id, title) -> card_id`
  - `update_progress(card_id, step, status)`
  - `request_approval(card_id, prompt, actions) -> decision`
- Decouple agent core logic from chat transport implementations.

### 3. Air-Gapped & Corporate Compliance Support
- Enable fully private, on-premise execution control using self-hosted messengers (Mattermost, Matrix) that operate without external internet egress to public bot APIs.

## Child Issues
- `[feat--agent-runtime-adapters-claude-codex-opencode]`: Multi-runtime adapters for Claude Code, Codex, and OpenCode.
- `[feat--agent-chat-adapters-discord-slack-mattermost-matrix]`: Omnichannel chat adapters for Discord, Slack, Mattermost, and Matrix.

## Acceptance Criteria
- [ ] Telemetry normalization verified across Claude Code, Codex, and OpenCode runs.
- [ ] Headless execution with local models verified via OpenCode adapter.
- [ ] Live Status Card rendering and interactive approval callbacks functional across Discord, Slack, Mattermost, and Matrix.
