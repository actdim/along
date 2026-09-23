---
protocol: along
protocol_version: "4.0.1"
slug: agent-run-protocol-and-observability
type: feat
status: open
priority: high
created: 2026-09-23
updated: 2026-09-23
agent: antigravity
tags: [aep, arp, protocol, observability, runtime, opentelemetry, telegram, epic]
milestone: v5.0.0-agent-run-protocol-and-observability
blocked_by: []
related: []
parent: null
---

# Agent Run Protocol (AEP/ARP) & Observability Engine (Epic)

## Goal
Establish Along as an execution control plane and observability layer for autonomous AI agents, independent of underlying agent runtimes. This epic delivers the core protocol specification, an OpenTelemetry-based append-only telemetry engine, Antigravity runtime integration, interactive execution gates, and Telegram Live Status Cards.

## Core Architectural Pillars

### 1. Execution Facts vs Model Reasoning
- Telemetry strictly captures physical execution facts: tool invocations, shell commands, process lifecycles, exit codes, and filesystem mutations.
- The protocol explicitly excludes private model Chain-of-Thought (CoT) to eliminate prompt leakage, context clutter, and storage bloat.

### 2. Standardized Telemetry via OpenTelemetry & OpenInference
- Map agent execution directly into standard OpenTelemetry Spans and Attributes without conflicting namespaces:
  - `openinference.span.kind`: `AGENT`, `CHAIN`, `TOOL`, `LLM`.
  - OTel GenAI Semantic Conventions: `gen_ai.system`, `gen_ai.request.model`, `gen_ai.usage.*`.
  - OTel Process Conventions: `process.command_line`, `process.pid`, `process.exit.code`.
  - Along Protocol Attributes: `along.issue.slug`, `along.session.slug`, `along.git.diff_hash`, `along.permission.*`, `along.repo.*`.

### 3. Human-in-the-Loop via Live Status Cards
- Single in-place editable message per run (`editMessageText`) in Telegram.
- Progress visualization with completed milestones, active action, and inline callback buttons (`[Approve]`, `[Reject]`, `[View Trace]`).
- Fail-safe execution timeout preventing orphaned locks.

### 4. Repo-Local Containment
- While runner daemons and global hooks are installed globally (`~/.along/`), all runs, session links, diffs, and execution history are anchored strictly inside the target repository `.along/` boundary.

## Child Issues
- `[feat--agent-run-protocol-core]`: Protocol specification, OpenTelemetry engine, and pluggable OTLP sinks.
- `[feat--agent-runtime-runner-antigravity]`: Process supervisor, Antigravity runtime adapter, and hook-based observation.
- `[feat--agent-execution-gate-telegram]`: Blocking permission hook, Telegram Live Status Card, and inline approval callbacks.
- `[feat--operational-assets-and-playbooks]`: Operational assets, dependency topology, and executable playbooks.
- `[feat--system-invariants-and-health-probes]`: System invariant assertions, health probes, and generalized verification gates.
- `[docs--operations-and-autonomous-systems-paradigm]`: Documentation paradigm shift to dual-mode software engineering and autonomous operations.

## Acceptance Criteria
- [ ] Universal AEP/ARP event schema formalized and validated.
- [ ] OpenTelemetry telemetry pipeline exporting spans to OTLP endpoints (gRPC/HTTP).
- [ ] Antigravity runtime launched and observed via native hooks with output stream fallback.
- [ ] Telegram Bot Live Card updating in-place with working approval/rejection callbacks.
- [ ] Subproject containment verified: runs and artifacts remain inside target `.along/`.
