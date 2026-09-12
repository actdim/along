---
protocol: along
slug: declarative-gate-engine-and-traceability
type: decision
title: "Declarative Gate Engine and Protocol Traceability Matrix"
date: 2026-09-13
status: accepted
tags: [adr, architecture, decision]
---

# ADR-2026-09-13--declarative-gate-engine-and-traceability - Declarative Gate Engine and Protocol Traceability Matrix

- Date: 2026-09-13
- Status: accepted
- Context: Natural language guidelines in AGENTS.md and skills decay as LLM conversations expand. Hardcoded Python hook gates created tight coupling and opacity between written rules and runtime enforcement. Furthermore, over 10 critical protocol invariants (such as mandatory issue anchoring, git commit slug binding, anti-stub injection, and test execution before turn completion) were unenforced mechanically.
- Decision: Replace hardcoded gate implementations with a declarative YAML catalogue (default_gates.yaml) supporting regex rules, composite conditions, and stateful Python predicates. Establish bi-directional machine-checked traceability: embed [gate: <id>] prose badges across protocol specifications and skill manifests, verified against YAML gate declarations via along hook verify and automated CI tests.
- Consequences: Enforces 11 canonical protocol gates mechanically across agent runtimes (Antigravity, Claude Code, OpenAI Codex). Guarantees zero drift between documentation and runtime enforcement. Prevents unanchored code mutations, syntax/typography violations, and untested session terminations. Allows repositories to customize or extend gates via .along/rules/gates.yaml without modifying core engine code.
