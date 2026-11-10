---
protocol: along
protocol_version: "4.7.0"
slug: workspace-activity-tracking
type: feat
status: open
priority: medium
created: 2026-11-07
updated: 2026-11-07
agent: antigravity
tags: [session, activity, concurrency, coordination, telemetry]
blocked_by: []
related: [feat--issue-drafts-lifecycle]
---

# Lightweight Untracked Workspace Activity Tracking and Heartbeat Engine

Introduce a machine-local workspace activity state file (`.along/.session/activity.json`) to track active processes, session heartbeats, and busy/idle states, enabling safe coordination for background loops and automated draft promotion.

## Context and Problem Statement

When autonomous background agents, test runners, and developer sessions operate within a repository, there is currently no lightweight, real-time mechanism to query whether the workspace is actively being mutated or is idle.

Checking `git status` or inspecting issue statuses only reveals static state, not live execution. Consequently, background loops (such as automated draft drainage, graph synchronization, or issue cleanup) cannot tell whether a test suite is currently executing or whether an agent is in the middle of a multi-step operation.

A machine-local, untracked activity heartbeat file allows processes to register their active presence, publish an ISO UTC heartbeat, and coordinate tasks without file collisions or git index locks.

## Requirements

- REQ-1 (Activity State File): Maintain an untracked JSON state file at `.along/.session/activity.json` with fields: `status` (`idle` | `busy`), `active_session_key`, `active_slug`, `last_ping` (ISO UTC), `runner_active` (boolean), and `process_pid`.
- REQ-2 (Heartbeat Updates): Lifecycle engines (`along start`, `along test`, `along scratch update`, and subagent hooks) MUST update `activity.json` with current timestamp and process information during execution.
- REQ-3 (Idle/Busy Evaluation): Provide `alongkit.session.get_workspace_activity(repo_root)` determining whether the repository is `busy` or `idle`. A repository is `busy` if a test runner is active or if the last ping from an open session is newer than the activity threshold (default 5 minutes).
- REQ-4 (CLI Inspection): Support `along session activity [--json]` and integrate real-time workspace activity status into `along doctor` and `along status`.
- REQ-5 (Idle Coordination Helper): Provide helper functions `is_workspace_idle(repo_root)` and `wait_until_idle(repo_root, timeout=60)` enabling background routines (e.g. draft promotions) to wait safely for an idle window.
- REQ-6 (ASCII Typography and Testing): Ensure 100% ASCII typography cleanliness and verify heartbeat writing, staleness timeouts, and idle transitions via hermetic unit tests.

## Acceptance Criteria

- [ ] `.along/.session/activity.json` schema and atomic writer implemented in `alongkit.session`.
- [ ] Session start, step updates, and test runs refresh the activity heartbeat.
- [ ] `along session activity` outputs human-readable and `--json` representations.
- [ ] Stale sessions (> 5 minutes without heartbeat) automatically decay to `idle`.
- [ ] `is_workspace_idle` and `wait_until_idle` helper functions tested and functional.
- [ ] Hermetic tests verify activity transitions and edge cases.
- [ ] Passes `python scripts/sanitize_typography.py --check` with 0 banned characters.
