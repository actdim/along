---
protocol: along
protocol_version: "4.0.1"
slug: multi-runtime-and-omnichannel-expansion
type: feat
status: open
priority: medium
created: 2026-09-23
updated: 2026-09-27
agent: antigravity
tags: [multi-runtime, claude, codex, opencode, omnichannel, discord, slack, mattermost, matrix, epic]
milestone: v5.3.0-omnichannel-chat-expansion
blocked_by: [feat--agent-run-protocol-and-observability]
related: [feat--agent-runtime-adapters-claude-codex-opencode]
---

# Multi-Runtime Adapters & Omnichannel Chat Integration (Epic)

## Goal
Expand Along execution observability and interactive human-in-the-loop control across enterprise messaging platforms (Discord, Slack, Mattermost, Matrix/Element) building on top of the multi-runtime execution foundation established in v5.0.0.

## Core Architectural Pillars

### 1. Transport-Agnostic Notification Gateway
- Abstract the Live Status Card operator interface behind a clean `NotificationGateway` abstraction:
  - `send_run_card(run_id, title) -> card_id`
  - `update_progress(card_id, step, status)`
  - `request_approval(card_id, prompt, actions) -> decision`
- Decouple agent core logic from chat transport implementations.

### 2. Air-Gapped & Corporate Compliance Support
- Enable fully private, on-premise execution control using self-hosted messengers (Mattermost, Matrix) that operate without external internet egress to public bot APIs.

## Child Issues
- `[feat--agent-chat-adapters-discord-slack-mattermost-matrix]`: Omnichannel chat adapters for Discord, Slack, Mattermost, and Matrix.

## Note on Runtime Adapters
Runtime adapters for Claude Code, OpenAI Codex, and OpenCode were promoted to `v5.0.0` under `[feat--agent-runtime-adapters-claude-codex-opencode]` to support headless execution and remote VPS loops.

## Acceptance Criteria
- [ ] Omnichannel notification gateway interface defined and implemented.
- [ ] Live Status Card rendering and interactive approval callbacks functional across Discord, Slack, Mattermost, and Matrix.
