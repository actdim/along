---
protocol: along
protocol_version: "4.0.1"
slug: system-invariants-and-health-probes
type: feat
status: open
priority: high
created: 2026-09-23
updated: 2026-09-23
completed: null
agent: antigravity
tags: [operations, verification, probes, health-checks, gates, invariants]
milestone: v5.0.0-agent-run-protocol-and-observability
blocked_by: [feat--operational-assets-and-playbooks]
related: [feat--agent-execution-gate-telegram]
parent: feat--agent-run-protocol-and-observability
superseded_by: null
duplicate_of: null
---

# System Invariants, Health Probes & Operational Verification Gates

## Goal

Decouple Along verification gates from code-only test runners (`along test`, `pytest`, `npm test`), introducing generic health probes, system invariant assertions, and operational quality gates for non-SE workflows.

## Problem Statement

Along's lifecycle enforcement relies on `gate: test_before_stop` and `along test`. In operational, cloud, and business process automation, there are often no repository unit tests to execute. Instead, agents must verify external system health, metric thresholds, and business invariants before marking a task or playbook run as `done`.

## Technical Specifications

### 1. Invariant Probes & Verification Contracts
- Define structured verification probe types in Along lifecycle configuration (`.along/rules/` or playbook definitions):
  - `http_probe`: URL, expected status code, latency threshold, response body assertions.
  - `command_probe`: CLI execution, expected exit code, stdout/stderr regex matching.
  - `metric_probe`: Query against monitoring systems or telemetry endpoints with threshold operators (`<`, `<=`, `==`, `>=`, `>`).
  - `sql_probe`: Read-only database query with assertion on row count or column values.

### 2. Operational Verification Engine
- Implement `along probe` CLI and Python engine (`alongkit.probes`):
  - Execution of configured probes against target assets (`.along/ASSETS/`).
  - Strict timeout enforcement and retry backoff.
  - Structured output integrated into AEP/ARP telemetry spans (`openinference.span.kind = "TOOL"`).

### 3. Generalized Stage Completion Gate
- Enhance `along wrap` and stage completion gates:
  - If the active issue is an SE type (`feat`, `bug`, `debt`), require standard test runner.
  - If the active issue is operational (`incident`, `change`, `audit`), require successful evaluation of all declared probes and invariant assertions.
  - Prevent issue closure if any probe fails or returns degraded status.

## Acceptance Criteria

- [ ] Probe specification implemented supporting HTTP, command, and metric checks.
- [ ] `along probe` CLI command implemented and integrated into Along command dispatcher.
- [ ] Verification gate updated to enforce probe assertions on operational issues and playbooks.
- [ ] Full unit and hermetic test coverage for probe execution, timeouts, and failure handling.
