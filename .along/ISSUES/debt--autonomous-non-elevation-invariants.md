---
protocol: along
protocol_version: "4.5.4"
slug: autonomous-non-elevation-invariants
type: debt
status: open
priority: high
created: 2026-10-30
updated: 2026-10-30
agent: antigravity
tags: [security, invariants, autonomous, constraints]
milestone: v5.1.0-language-ecosystem-expansion
blocked_by: []
related: []
---

# Enforce non-elevation invariants for autonomous agent loops and runtime tools

Establish and enforce a strict architectural security invariant: autonomous agent routines, background runners, and self-learning engines cannot elevate their own operational privileges.

## Context and Problem Statement
With the introduction of background daemons, remote runners, and autonomous multi-agent loops in Along v5.0.0, the risk of privilege escalation by autonomous agents increases. If an agent encounters a restrictive gate, missing tool, or failing credential check, a self-improving loop might attempt to edit gate definitions, register unsanctioned CLI tools, probe host credential stores, or grant itself release privileges.

A strict non-elevation invariant ensures that autonomous systems remain sandboxed within their designated operational boundaries, requiring explicit human or supervisor authorization for privilege expansion.

## Requirements
- REQ-1: Architectural Invariant: Autonomous agent loops, reflection engines, and background runners MUST NEVER elevate their own privileges, expand their allowed tool list, access credential stores, or trigger version release pipelines.
- REQ-2: Gate Enforcement: Runtime gates in `scripts/alongkit/gates.py` MUST intercept and block any automated attempt to modify security policies, `.along/rules/`, hook configurations, or release tags originating from an unattended agent turn.
- REQ-3: Proposal-Only Pattern: Any autonomous learning or optimization engine MAY produce optimization candidates or suggested rules, but MUST output them as reviewable artifacts requiring explicit human approval rather than self-applying them.
- REQ-4: Codification: The non-elevation invariant MUST be recorded as an ADR in `.along/DECISIONS/` and projected into `.along/CONSTRAINTS.md`.

## Acceptance Criteria
- [ ] Non-elevation invariant ADR created and synced to `.along/CONSTRAINTS.md`
- [ ] Gate check in `scripts/alongkit/gates.py` preventing self-elevation and rule-tampering by background runners
- [ ] Runner daemon and supervisor scripts verified to run under restricted capability envelopes
- [ ] Automated tests in `tests/test_alongkit.py` verifying rejection of unauthorized privilege escalation attempts
