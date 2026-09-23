---
protocol: along
protocol_version: "4.0.1"
slug: agent-runtime-runner-antigravity
type: feat
status: open
priority: high
created: 2026-09-23
updated: 2026-09-23
agent: antigravity
tags: [runtime, runner, antigravity, hooks, process-supervisor, repo-containment]
milestone: v5.0.0-agent-run-protocol-and-observability
blocked_by: [feat--agent-run-protocol-core]
related: []
parent: feat--agent-run-protocol-and-observability
---

# Antigravity Runtime Launcher & Observability Adapter

## Goal
Implement a process supervisor and telemetry adapter for launching and observing the Antigravity agent runtime, utilizing native hooks as the primary observation source and buffered process output as a secondary fallback.

## Problem Statement
When running autonomous agent tasks, developers need a reliable mechanism to spawn Antigravity in headless or interactive modes, enforce workspace directory boundaries, and capture execution telemetry in real time without relying on fragile terminal scraping.

## Technical Specifications

### 1. Process Supervisor & Workspace Isolation
- Implement `along run antigravity [options]` command capable of launching Antigravity sessions.
- Enforce strict workspace containment: the agent process is bounded to the project root directory.
- Pass environment parameters indicating active Along context (`ALONG_RUN_ID`, `ALONG_ISSUE_SLUG`, `ALONG_OTEL_ENDPOINT`).

### 2. Dual-Channel Observability
- **Primary Source (Native Hooks)**:
  - Configure Antigravity lifecycle hooks: `SessionStart`, `PreToolUse`, `PostToolUse`, `SessionEnd`.
  - Hook dispatcher converts hook payloads directly into normalized AEP/OTel spans.
  - Spans record tool names, input arguments, durations, and exit statuses.
- **Secondary Source (Process Output Fallback)**:
  - Capture child process stdout and stderr in buffered chunks (coarse-grained chunks every 200 ms or 64 KB).
  - Stream chunks are attached to the active run span or saved as execution log artifacts, preventing high-frequency DB write saturation.

### 3. Subproject Boundary & Repo-Local Containment
- In accordance with Along rules (`AGENTS.md` subproject boundary), all generated session logs, artifacts, and issue linkages must resolve to the nearest `<repo>/.along/` directory.
- Execution history is tied to active issues in `.along/ISSUES/` and summarized in `.along/SESSIONS/`.

### 4. Observability Confidence Levels
- Each run declares its observability confidence in root span attributes:
  - `along.observability.level = "complete" | "partial" | "unknown"`
  - `along.observability.sources = ["antigravity_hook", "stdout_stream"]`

## Acceptance Criteria
- [ ] Process supervisor spawns Antigravity with configured workspace boundaries.
- [ ] Native hooks (`PreToolUse`, `PostToolUse`) emit corresponding OpenInference tool spans.
- [ ] Output stream buffer correctly chunks high-volume stdout without performance drops.
- [ ] State, artifacts, and issue bindings reside strictly in the target repository `.along/`.
- [ ] Unit and hermetic tests verify runner lifecycle handling and clean exit codes.
