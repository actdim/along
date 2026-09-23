---
protocol: along
slug: telegram-remote-operational-gateway-and-semi-autonomous-mode
title: "Telegram Remote Operational Gateway & Semi-Autonomous Mode vs Interactive IDE"
date: 2026-09-23
status: accepted
tags: [adr, architecture, decision, telegram, remote-gateway, semi-autonomous, execution-gate]
---

# ADR-2026-09-23--telegram-remote-operational-gateway-and-semi-autonomous-mode - Telegram Remote Operational Gateway & Semi-Autonomous Mode vs Interactive IDE

- Date: 2026-09-23
- Status: accepted
- Context:
  Autonomous agent runtimes need remote operational interfaces. However, relying on Telegram solely for passive notifications or approval gates restricts operators from initiating work remotely. Conversely, attempting to run full conversational coding dialogues ("prompt ping-pong") in Telegram leads to context degradation, token waste, lack of issue anchoring, and poor ergonomics compared to modern IDEs.
- Decision:
  1. **Strict Separation of Modes**:
     - **Semi-Autonomous Operational Mode (Chat Gateway)**: Dedicated to asynchronous task dispatch, referencing existing `.along/ISSUES/`, milestone tracking via Live Status Cards, synchronous approval checkpoints, and execution summaries. Zero conversational "ping-pong".
     - **Interactive Development Mode (Direct IDE Workspace)**: Deep pair-programming, exploratory coding, and line-by-line debugging remain in dedicated IDE environments (such as Antigravity remote sessions accessed via QR-code or web terminal).
  2. **Bidirectional Task Dispatch & Mandatory Anchoring**:
     - Remote commands (`/run <slug>`, `/task <title>`) must bind to or automatically create an active issue in `.along/ISSUES/` before execution begins (`[gate: require-active-issue]`).
  3. **Multi-Project & Room Context Routing**:
     - Telegram group chats and Forum Topics (thread IDs) map deterministically to workspace repository paths via daemon configuration, enforcing project isolation and preventing ambiguous execution.
  4. **Dual-Layer Issue Context Exploration**:
     - Native Telegram inline queries (`@alongbot issue ...`) and paginated status cards for low-latency text interaction.
     - Telegram Mini App (TMA / WebApp) backed by local dashboard endpoints for visual issue board browsing, DAG exploration, and one-tap task launch.
  5. **Safety & Concurrency**:
     - All remote runs execute in isolated Git worktrees (`.along/worktrees/run-<id>`).
     - Multi-operator approval callbacks are resolved atomically with operator attribution and fail-safe timeouts.
- Consequences:
  - Operators gain a clean, noise-free remote control plane for managing background tasks without turning the chat into an unruly terminal emulator or chatty chatbot.
  - Development ergonomics remain optimal: deep work happens in IDEs; operational monitoring and dispatch happen in chat.
