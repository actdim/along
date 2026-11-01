---
protocol: along
protocol_version: "4.5.4"
slug: team-typed-handoff-mailbox
type: feat
status: open
priority: medium
created: 2026-10-30
updated: 2026-10-30
agent: antigravity
tags: [team, blackboard, messaging, handoff]
milestone: v5.1.0-language-ecosystem-expansion
blocked_by: []
related: []
---

# Typed role-handoff mailbox and structured inter-agent messages

Implement schema-validated, typed handoff payloads between along-team roles to minimize token waste and eliminate context degradation across agent transitions.

## Context and Problem Statement
When multi-agent teams hand off work between roles (Research -> Architect -> Implementer -> Reviewer), passing entire conversational transcripts or raw prompt dumps causes severe context bloat and degrades LLM reasoning. Important edge cases, constraints, and blast-radius warnings get lost in narrative prose.

Establishing a typed blackboard mailbox with strict data schemas ensures that each role receives exactly the structured facts it needs to execute without context pollution.

## Requirements
- REQ-1: Schema-Validated Payloads: Define formal data contracts for role handoffs:
  - `ResearchHandoff`: Structured findings, relevant file paths, identified constraints, and unresolved risks.
  - `ArchitectHandoff`: Explicit target files, component interfaces, forbidden patterns, and verification plan.
  - `ImplementHandoff`: Changed files, exported symbols, test execution receipts, and deferred items.
  - `ReviewHandoff`: Approval verdict, blocking defects, compliance checklist, and residual risks.
- REQ-2: Blackboard Mailbox: Persist typed handoffs in `.along/scratch/<slug>/state.json` under an atomic `handoffs` dictionary keyed by step identifier.
- REQ-3: Deterministic Role Briefing: `along brief <slug> --role <role>` MUST consume the preceding role's validated handoff payload and format a concise role brief without ingesting raw conversation history.
- REQ-4: Step Gate Validation: A role step cannot be marked complete if its required handoff payload fails schema validation.

## Acceptance Criteria
- [ ] Pydantic/dataclass schemas defined for all core role handoffs in `scripts/alongkit/`
- [ ] Atomic mailbox storage implemented in blackboard state engine
- [ ] `along brief` updated to render typed handoffs concisely
- [ ] Step exit gate rejects malformed or incomplete handoff payloads
- [ ] Unit tests covering handoff schema validation, serialization, and retrieval
