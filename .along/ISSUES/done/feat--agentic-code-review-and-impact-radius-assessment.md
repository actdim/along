---
protocol: along
slug: agentic-code-review-and-impact-radius-assessment
type: feat
status: done
priority: high
created: 2026-08-27
updated: 2026-08-27
completed: 2026-08-27
agent: antigravity
tags: [code-review, impact-analysis, quality-gate, mcp]
milestone: v2.0.0-along-transition
blocked_by: []
related: [feat--along-webdev-runner, feat--agentic-goals-and-mandatory-checklists]
---

# Agentic Code Review & Blast Radius Impact Assessment Protocol

## Goal
Establish a mandatory, automated **Agentic Code Review & Impact Radius Assessment** protocol within the system, requiring agents to critically analyze their own code changes before completing non-trivial tasks, assessing blast radius across dependent modules, architecture compliance, and safety.

## Accomplishments
1. **Protocol Integration**:
   - Added mandatory Code Review & Blast Radius assessment guidelines under `## While working` in `AGENTS.md` and `protocol.md`.
   - Updated the **Mandatory Stage & Session Completion Checklist** with item #2:
     - Inspect git diff for unintended side effects, unhandled nulls/errors, and edge cases.
     - Evaluate systemic impact radius on callers/dependents using `code-review-graph` or AST analysis.
     - Verify compliance with architectural decisions in `.along/DECISIONS.md`.
2. **Skill Suite Enforcement**:
   - Updated `skills/along-wrap-session/SKILL.md` and `skills/along-wrap-stage/SKILL.md` to enforce Code Review as a mandatory step in the wrap-up pipeline.
3. **ADR #008 Logged**:
   - Logged architectural decision in `.along/DECISIONS.md`.

## Acceptance Criteria
- [x] Code Review & Blast Radius assessment guidelines added to `AGENTS.md` and `protocol.md`.
- [x] Completion checklist carries the code review item (diff inspection, impact radius, ADR compliance).
- [x] Wrap-up skills enforce code review as a mandatory step.
- [x] Architectural decision recorded in `.along/DECISIONS.md`.

