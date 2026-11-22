---
protocol: along
protocol_version: "4.9.1"
slug: local-llm-micro-orchestrator
type: feat
status: open
priority: medium
created: 2026-11-22
updated: 2026-11-22
agent: antigravity
tags: [orchestrator, local-llm, autonomous, multi-agent, micro-harness]
blocked_by: [feat--local-llm-substrate-env-config]
related: [feat--runtime-integration-tests-local-llm, feat--webdev-nl-local-runner]
parent: feat--local-llm-runtime-harness
---

# Local LLM Micro-Orchestrator: Autonomous Local Dispatcher

## Problem

Along includes an autonomous cross-runtime orchestrator (`along orchestrate` and `along-team`) that executes sequential multi-agent loops across heterogeneous CLIs (scout -> architect -> implementer -> reviewer). 

Currently, this orchestration supervisor faces two limitations:
1. **Cloud Dependency**: Supervisor decisions (such as synthesizing briefs from review notes, evaluating retries, and diagnosing gate denials) require cloud LLM calls (Anthropic or OpenAI API). When working offline or in air-gapped environments, the orchestrator cannot function autonomously.
2. **Rigid State Transitions**: The fallback state machine relies on static heuristics and regex parsing of review files. It lacks a reasoning layer capable of analyzing handoff notes, distilling complex errors, and reformulating agent briefs to unblock stuck loops.

## Requirements

### 1. Local Micro-Supervisor Interface (REQ-1)
- Along MUST introduce `LocalMicroSupervisor` in `alongkit.orchestrator` that communicates with the local OpenAI-compatible endpoint (`http://127.0.0.1:8080/v1` via `qwen2.5-coder:7b`).
- The supervisor MUST operate without requiring external network connectivity or paid API keys.

### 2. Autonomous Task & Loop Management (REQ-2)
- **Brief Synthesis**:
  - Given issue description, previous step diff, and handoff note, the micro-supervisor generates a concise, focused prompt for the next role (implementer or reviewer).
- **Review Evaluation**:
  - The micro-supervisor parses `reviews/step-N.md` front-matter and prose, classifying defects into:
    - `pass`: Advance step in `state.json`.
    - `retry`: Generate targeted remediation brief highlighting exact defects.
    - `fatal`: Halt loop and formulate operator escalation note.
- **Gate Denial Remediation**:
  - When an agent command is denied by Along hooks (e.g. attempting to modify an unapproved file or violating workspace containment), the micro-supervisor diagnoses the denial and instructs the agent to respect the protocol boundary.

### 3. Micro-Harness Architecture & Fallback Discipline (REQ-3)
- To prevent reinventing a complex agent runtime, the micro-orchestrator MUST utilize structured JSON schemas for all LLM interactions.
- If the local LLM output fails schema validation, the supervisor MUST fallback deterministically to rule-based state machine logic without deadlocking or looping infinitely.
- Maximum retry limits (default: 3) MUST be strictly enforced.

## Implementation Plan

1. **Architectural Evaluation & Schema Design**:
   - Design JSON schemas for: `BriefRequest`, `ReviewEvaluation`, and `DenialRemediation`.
   - Record architectural decision in `.along/DECISIONS/` as an ADR.
2. **Local Supervisor Core**:
   - Implement `LocalMicroSupervisor` in `scripts/alongkit/orchestrator_local.py`.
   - Integrate with `LocalInferenceClient` from `alongkit.local_llm`.
3. **CLI Integration**:
   - Add `--local` flag to `along orchestrate <slug>` (e.g. `along orchestrate <slug> --local`).
4. **Testing & Verification**:
   - Unit tests with mock JSON responses in `tests/test_local_micro_orchestrator.py`.
   - Real smoke test with `qwen2.5-coder:7b` on `127.0.0.1:8080`.

## Acceptance Criteria

- [ ] `along orchestrate <slug> --local` runs the multi-agent loop using local LLM inference for supervisor decisions.
- [ ] Review evaluations correctly categorize pass/retry/fatal outcomes.
- [ ] Schema validation errors fallback cleanly to rule-based defaults without crashing.
- [ ] Automated unit and smoke tests passing.
