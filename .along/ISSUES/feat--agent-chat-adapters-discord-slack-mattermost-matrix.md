---
protocol: along
protocol_version: "4.0.1"
slug: agent-chat-adapters-discord-slack-mattermost-matrix
type: feat
status: open
priority: medium
created: 2026-09-23
updated: 2026-09-23
agent: antigravity
tags: [chat-adapters, discord, slack, mattermost, matrix, omnichannel, on-prem]
milestone: v6.0.0-multi-runtime-and-omnichannel-expansion
blocked_by: [feat--agent-execution-gate-telegram]
related: []
parent: feat--multi-runtime-and-omnichannel-expansion
---

# Omnichannel Chat Adapters: Discord, Slack, Mattermost & Matrix

## Goal
Implement omnichannel messaging adapters behind the `NotificationGateway` interface, bringing the Live Status Card and interactive approval callbacks to Discord, Slack, Mattermost, and Matrix/Element.

## Problem Statement
While Telegram is ideal for individual developers and cloud workflows, enterprise teams require integration with corporate tools (Slack), developer communities require Discord, and security-conscious organizations require strictly self-hosted messengers (Mattermost, Matrix) that operate inside air-gapped corporate firewalls without public internet egress.

## Technical Specifications

### 1. Abstract Gateway Interface (`NotificationGateway`)
Define a unified interface:
- `create_run_card(run_id, title, metadata) -> card_id`
- `update_progress(card_id, step_name, status, details)`
- `prompt_approval(card_id, action_description, options) -> Promise<decision>`
- `finalize_run(card_id, final_status, summary)`

### 2. Platform-Specific Adapters
- **Discord (Priority 2)**:
  - Rich Embeds with color status indicators.
  - Interactive Message Components (Buttons).
  - Dedicated run threads per execution to maintain channel hygiene.
- **Slack (Enterprise Cloud)**:
  - Block Kit cards with sections, progress fields, and action buttons.
  - In-place message updates via `chat.update`.
- **Mattermost (Self-Hosted On-Premise)**:
  - REST API post updates (`PUT /posts/{post_id}`) with interactive action buttons.
  - 100% internal network operation without outbound cloud connections.
- **Matrix / Element (Decentralized Open Protocol)**:
  - Message replacement (`m.replace`) for in-place card updates.
  - Matrix Widgets support: embedding live Along trace dashboards directly into the chat client.

## Acceptance Criteria
- [ ] `NotificationGateway` abstraction implemented and tested.
- [ ] Discord adapter verified with Embeds, Buttons, and run threads.
- [ ] Slack adapter verified with Block Kit and interactive callbacks.
- [ ] Mattermost adapter verified in an isolated on-premise Docker environment.
- [ ] Matrix adapter verified with message edits and room widget embedding.
