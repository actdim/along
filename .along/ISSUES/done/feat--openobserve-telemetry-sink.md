---
protocol: along
protocol_version: "4.8.1"
slug: openobserve-telemetry-sink
type: feat
status: done
completed: 2026-11-14
priority: high
created: 2026-11-14
updated: 2026-11-14
agent: antigravity
tags: [telemetry, otlp, openobserve, orchestrator]
milestone: v5.0.0-agent-run-protocol-and-observability
blocked_by: []
related: []
parent: feat--agent-run-protocol-and-observability
plan_status: approved
---

# OpenObserve Telemetry Sink and Orchestrator Tracing

## Goal
Enable direct OpenTelemetry trace and log streaming from Along orchestrator runs into OpenObserve, and instrument CrossRuntimeOrchestrator with end-to-end phase spans across all supported agent runtimes (Antigravity, Claude Code, OpenAI Codex, OpenCode).

## Problem Statement
While Along has a low-level OTLP export engine in `alongkit.telemetry`, it is currently decoupled from `CrossRuntimeOrchestrator` and lacks native configuration handling for OpenObserve authentication and endpoints (such as `Authorization: Basic ...` headers and custom stream paths). As a result, cross-runtime execution across heterogeneous agent CLI tools operates without real-time observability, making failure diagnosis and performance profiling difficult.

## Requirements
- REQ-1: `OTLPExporter` MUST support reading `OTEL_EXPORTER_OTLP_ENDPOINT` and `OTEL_EXPORTER_OTLP_HEADERS` from environment variables, with fallback to repository configuration in `along.yaml` or `.along/config.yaml`.
- REQ-2: `OTLPExporter` MUST support HTTP Basic authentication (`Authorization: Basic <base64>`) and custom headers required for OpenObserve ingestion.
- REQ-3: `CrossRuntimeOrchestrator` MUST instantiate and manage a `Tracer` instance, emitting a root agent run span and nested child spans for scout, architect, step implementation, and reviewer phases.
- REQ-4: Runner execution results, exit codes, gate denials, and step retries MUST be attached as span attributes and Span Events.
- REQ-5: Telemetry export errors (such as network timeouts or unreachable OpenObserve instances) MUST fail-open to the local disk spooler without halting or crashing orchestrator execution.
- REQ-6: End-to-end automated unit and integration tests MUST cover OTLP header parsing, OpenObserve payload formatting, orchestrator span emission, and disk spool fail-open behavior.

## Acceptance Criteria
- [x] `OTLPExporter` reads endpoint and headers from both environment variables and repository config.
- [x] OpenObserve Basic Auth headers and endpoint configuration are validated and tested.
- [x] `CrossRuntimeOrchestrator` emits root and phase spans with runtime metadata (runtime, role, step, exit code).
- [x] Telemetry transmission failures spool to disk without crashing the orchestrator.
- [x] Comprehensive automated tests in `tests/test_telemetry_otlp.py` and `tests/test_orchestrator_telemetry.py` pass.
