---
protocol: along
protocol_version: "4.0.1"
slug: agent-run-protocol-core
type: feat
status: open
priority: high
created: 2026-09-23
updated: 2026-09-23
agent: antigravity
tags: [aep, arp, opentelemetry, openinference, genai, otlp, openobserve, clickhouse, core]
milestone: v5.0.0-agent-run-protocol-and-observability
blocked_by: []
related: []
parent: feat--agent-run-protocol-and-observability
---

# Agent Run Protocol (AEP/ARP) Specification & OpenTelemetry Engine

## Goal
Specify and implement the core Agent Run Protocol (AEP/ARP) using standard OpenTelemetry (OTel) primitives, enabling append-only, high-performance streaming telemetry of agent execution to pluggable analytical backends.

## Problem Statement
Autonomous AI agents currently operate as black boxes or output human-oriented terminal streams. Existing tools either attempt to parse fragile PTY outputs or build proprietary, incompatible database schemas. A standard, schema-validated protocol based on industry-standard OpenTelemetry semantic conventions is required to observe what an agent actually executes.

## Technical Specifications

### 1. Unified Event & Span Mapping
All agent execution events map to OpenTelemetry Spans and Span Events using standard namespaces:
- **Root Span (Agent Run)**:
  - `openinference.span.kind = "AGENT"`
  - `along.run.id = "<uuid>"`
  - `along.repo.root = "/path/to/repo"`
  - `along.repo.name = "my-project"`
  - `along.issue.slug = "feat--token-refresh"`
- **Turn Spans (Step / Chain)**:
  - `openinference.span.kind = "CHAIN"`
  - `along.turn.seq = <int>`
- **Inference Spans (Model Calls)**:
  - `openinference.span.kind = "LLM"`
  - `gen_ai.system = "anthropic" | "openai" | "ollama"`
  - `gen_ai.request.model = "claude-3-7-sonnet" | "gpt-4o"`
  - `gen_ai.usage.input_tokens = <int>`
  - `gen_ai.usage.output_tokens = <int>`
- **Tool Spans (Tool Invocations)**:
  - `openinference.span.kind = "TOOL"`
  - `tool.name = "bash" | "filesystem.write"`
  - `tool.parameters = <json>`
  - `process.command_line = "dotnet test -v q"`
  - `process.pid = <int>`
  - `process.exit.code = <int>`

### 2. High-Performance Append-Only Architecture
- Pure append-only telemetry stream: zero in-place `UPDATE` operations in backend stores.
- Client-side buffering and batch export via OTLP/gRPC (port 4317) or OTLP/HTTP (port 4318).
- Local spooling ring-buffer: if the telemetry collector is unreachable, events buffer locally in memory/WAL without stalling the agent.

### 3. Payload Offloading & Secret Sanitization
- Heavy blobs (diffs > 50 lines, raw compiler dumps > 10 KB) are saved as file artifacts, with spans storing `artifact_ref` and SHA256 checksums.
- Automatic secret masking: command arguments and environment variables are sanitized to redact tokens, authorization headers, and private keys prior to export.

### 4. Pluggable Backend Support
- Verified compatibility with:
  - **OpenObserve**: Lightweight Rust-based search and trace store (Parquet on local disk/S3).
  - **ClickHouse / SigNoz**: High-throughput analytical backend for large team clusters.
  - **Seq / .NET Aspire Dashboard**: Zero-configuration developer dashboards for local debugging.

## Acceptance Criteria
- [ ] Universal AEP/ARP schema defined and documented with OpenInference and OTel GenAI mappings.
- [ ] OTLP exporter module implemented supporting buffered batch transmission.
- [ ] Automated secret redaction pipeline tested against common token patterns (`Bearer`, `ghp_`, API keys).
- [ ] Heavy artifact offloader storing large stdout/diff blobs outside span attributes.
- [ ] End-to-end trace emission verified against OpenObserve and Aspire Dashboard.
