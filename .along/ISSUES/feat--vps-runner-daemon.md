---
protocol: along
protocol_version: "4.1.0"
slug: vps-runner-daemon
type: feat
status: open
priority: high
created: 2026-09-27
updated: 2026-09-27
agent: antigravity
tags: [vps, runner, daemon, service, worker-pool, long-polling, webhook, systemd]
milestone: v5.0.0-agent-run-protocol-and-observability
blocked_by: [feat--agent-run-protocol-core]
related: [feat--agent-execution-gate-telegram, feat--agent-runtime-runner-antigravity]
parent: feat--agent-run-protocol-and-observability
---

# VPS Runner Host Daemon & Background Process Supervisor

## Goal
Implement a persistent background runner daemon (`along daemon`) for hosting autonomous agent execution loops on remote VPS instances, managing Telegram polling or webhook ingress, worker execution queues, worktree isolation, process supervision, and health monitoring.

## Problem Statement
Autonomous agent execution on remote servers requires an always-on host process to receive remote triggers (`/run`, `/task`) and manage execution lifecycles. Without a dedicated daemon:
1. Remote execution relies on fragile interactive SSH sessions or ad-hoc terminal multiplexers (tmux/screen).
2. Incoming Telegram webhooks or polling updates have no persistent dispatcher to receive and validate commands.
3. Multiple concurrent tasks risk collisions in the working tree without centralized worktree allocation and concurrency queues.
4. Process crashes or network dropouts leave orphaned processes and corrupted lock files.

## Technical Specifications

### 1. Daemon CLI Architecture
- Implement daemon management subcommands under `along daemon`:
  - `along daemon start [--mode polling|webhook] [--concurrency <int>] [--port <int>]`: Spawns or enters the long-running host supervisor.
  - `along daemon stop`: Sends graceful termination signal to the running supervisor.
  - `along daemon status`: Displays daemon PID, active worker runs, memory footprint, and uptime.
  - `along daemon logs [-f]`: Tails supervisor stdout/stderr logs.
- Provide a standard systemd service unit template (`along-runner.service`) supporting auto-restart on failure.

### 2. Ingress & Dispatch Loop
- **Long-Polling Mode (Default)**:
  - Fetches updates via Telegram Bot API long-polling (`getUpdates`).
  - Operates behind NAT/firewalls without requiring a public IP or inbound open ports on the VPS.
- **Webhook Mode (Production / High Volume)**:
  - Listens on configured local port with secret token validation (`X-Telegram-Bot-Api-Secret-Token`).
- **Security Guard**:
  - Rejects commands from unauthorized `user_id` or unregistered chat groups before worker allocation.

### 3. Worker Pool & Worktree Isolation
- Maintain an internal execution queue prioritizing critical operational tasks.
- For each dispatched task, initialize an isolated git worktree (`.along/worktrees/run-<id>`) using `alongkit.worktree`.
- Enforce strict concurrency limits (default: 1 concurrent agent task per repository, configurable).
- Automatically tear down ephemeral worktrees and flush pending OTel telemetry upon run completion.

### 4. Process Supervision & Crash Recovery
- Supervise child agent processes (Antigravity, Claude Code, Codex, OpenCode) with timeout monitors.
- Handle `SIGTERM` / `SIGINT` gracefully: notify Telegram status card of interruption, release locks, and clean up child processes.
- Persistent run state file (`~/.along/daemon-state.json`) prevents duplicate runs across daemon restarts.

## Acceptance Criteria
- [ ] `along daemon` CLI implemented supporting start, stop, status, and logs.
- [ ] Long-polling Telegram event dispatcher functional without inbound network ports.
- [ ] Worker pool safely isolates concurrent or sequential runs in dedicated worktrees.
- [ ] Systemd unit template tested and verified for Linux VPS deployments.
- [ ] Clean process cleanup and state recovery verified upon unexpected termination.
