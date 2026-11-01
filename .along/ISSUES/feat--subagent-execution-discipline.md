---
protocol: along
protocol_version: "4.5.4"
slug: subagent-execution-discipline
type: feat
status: open
priority: medium
created: 2026-10-30
updated: 2026-10-30
agent: antigravity
tags: [subagent, quality-gate, verification, acceptance-criteria, execution-discipline, light-models]
milestone: v5.1.0-language-ecosystem-expansion
blocked_by: []
related: [feat--autonomous-gate-profile, feat--system-invariants-and-health-probes, feat--clean-turn-context-isolation-in-along-team]
---

# Subagent Execution Discipline, Anti-Stub Guardrails, and Acceptance Matrix

## Goal

Strengthen execution discipline and deterministic verification across Along agent runs, subagents (`along-team`, `invoke_subagent`), and lightweight models (e.g. Gemini Flash / Haiku). Ensure that task completion is strictly bound to measurable acceptance criteria with tool-verified PASS/FAIL evidence, completely eliminating silent code truncation, placeholder stubs (`// TODO`), and premature victory declarations.

## Problem Statement

When tasks or subtasks are delegated to fast, cost-effective models (such as Gemini Flash or lightweight subagent workers), several systematic failure modes emerge:

1. **Stub and Placeholder Proliferation**: Fast models frequently insert `// TODO: implement later`, empty function bodies, or truncated snippets (`... rest of implementation ...`) under context or time pressure, reporting success without finishing the contract.
2. **"File Creation != Task Completion" Fallacy**: Agents often treat the mere creation of a file or existence of code as proof of completion, bypassing syntax validation, test execution, or build checks.
3. **Absence of a Structured Acceptance Matrix**: Tasks often end with descriptive natural-language summaries rather than a verifiable checklist showing each requirement mapped to actual command execution evidence (exit code 0, test output, linter pass).
4. **Context Drift in Multi-Turn Sessions**: In longer agent sessions, early requirements degrade into vague approximations unless an explicit acceptance checklist is continuously referenced and validated against.

## Requirements

### 1. Anti-Stub and Truncation Guardrail Contract (REQ-1)
- The system MUST provide an explicit subagent execution rule profile (for `along-team` worker roles and subagent templates) that strictly prohibits:
  - Unimplemented placeholders (`TODO`, `FIXME`, `TBD`, placeholder stubs).
  - Silent truncation of existing files or omitted blocks (`// ... existing code ...`).
  - Replacing complete deliverables with draft summaries without explicit instructions.

### 2. Execution-Before-Completion Invariant (REQ-2)
- An issue or subtask MUST NOT be marked complete or ready for review unless:
  - Target files are syntactically validated.
  - Required tests, linters, or deterministic verification scripts have been executed in the active session.
  - The verification output confirms zero failures on touched files.

### 3. Structured Acceptance Verification Matrix (REQ-3)
- Introduce a standardized Acceptance Verification Matrix format into `along-team` Step Reviewer outputs and session wrap summaries (`along wrap`):
  - Each item MUST list: `[Requirement ID / Item]`, `[Status: PASS|FAIL]`, `[Verification Method / Command]`, `[Output Evidence]`.
  - Any `FAIL` status blocks transition to `done` unless an explicit waiver or issue split is authorized.

### 4. Lightweight Runtime Profile Integration (REQ-4)
- Configure specialized system prompt profiles for subagents invoked with `flash` or `flash_lite` models to enforce proactive file inspection, reasonable low-risk autonomy without routine operator micromanagement, and persistent requirements tracking.

## Acceptance Criteria

- [ ] Subagent execution profile documentation and prompt guidelines registered in `.along/rules/` or `alongkit`.
- [ ] Pre-completion lint/gate detects stub markers (`// TODO`, `/* TODO */`, `pass  # todo`) introduced in modified regions.
- [ ] `along-team` reviewer step requires and validates a structured Acceptance Matrix before transitioning to final completion.
- [ ] Session wrap documentation references acceptance verification evidence.
- [ ] Structural issue lint passes cleanly (`along issue lint --strict`).
