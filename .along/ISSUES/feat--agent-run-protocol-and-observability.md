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
Establish Along as an execution control plane and observability layer for autonomous AI agents, independent of underlying agent runtimes. This epic delivers the core protocol specification, an OpenTelemetry-based append-only telemetry engine, Antigravity runtime integration, a bidirectional Telegram remote operational gateway for semi-autonomous task dispatch and project routing, and in-place Live Status Cards with interactive execution gates.

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

### 3. Bidirectional Remote Control Plane: Semi-Autonomous Mode vs Interactive IDE Mode
- **Semi-Autonomous Operational Remote Gateway (Telegram)**:
  - Initiates agent runs and anchors tasks into `.along/ISSUES/` remotely.
  - Multi-project routing maps Telegram groups and Forum Topics to specific workspace repositories.
  - Context and issue browsing provided via Telegram Mini App (TMA) and native interactive cards.
  - Rejects conversational "ping-pong" chatting: operates as a structured command and milestone tracking console.
  - Single in-place editable message per run (`editMessageText`) with progress checklists and synchronous approval hooks (`[Approve]`, `[Reject]`, `[View Trace]`).
- **Interactive Development Mode (Direct IDE Workspace)**:
  - Line-by-line coding, deep debugging, and conversational exploration remain in full IDE workspaces (e.g. Antigravity remote access via QR code / web terminal), deliberately separated from the chat gateway.

### 4. Repo-Local Containment
- While runner daemons and global hooks are installed globally (`~/.along/`), all runs, session links, diffs, and execution history are anchored strictly inside the target repository `.along/` boundary.

## Child Issues
- `[feat--agent-run-protocol-core]`: Protocol specification, OpenTelemetry engine, and pluggable OTLP sinks.
- `[feat--agent-runtime-runner-antigravity]`: Process supervisor, Antigravity runtime adapter, and hook-based observation.
- `[feat--agent-execution-gate-telegram]`: Bidirectional Telegram remote operational gateway, task dispatch, project room routing, issue explorer (Mini App/Cards), and in-place Live Status Card execution gates.
- `[feat--operational-assets-and-playbooks]`: Operational assets, dependency topology, and executable playbooks.
- `[feat--system-invariants-and-health-probes]`: System invariant assertions, health probes, and generalized verification gates.
- `[docs--operations-and-autonomous-systems-paradigm]`: Documentation paradigm shift to dual-mode software engineering and autonomous operations.

## Acceptance Criteria
- [ ] Universal AEP/ARP event schema formalized and validated.
- [ ] OpenTelemetry telemetry pipeline exporting spans to OTLP endpoints (gRPC/HTTP).
- [ ] Antigravity runtime launched and observed via native hooks with output stream fallback.
- [ ] Telegram remote gateway operational: task dispatch, issue anchoring, and project room routing verified.
- [ ] Telegram Bot Live Card updating in-place with working approval/rejection callbacks.
- [ ] Subproject containment verified: runs and artifacts remain inside target `.along/`.
