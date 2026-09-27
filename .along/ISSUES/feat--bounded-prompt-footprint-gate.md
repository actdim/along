---
protocol: along
protocol_version: "4.1.0"
slug: bounded-prompt-footprint-gate
type: feat
status: open
priority: medium
created: 2026-09-27
updated: 2026-09-27
agent: antigravity
tags: [gates, context-budget, tokens, prompt-size, skill-state]
milestone: v4.5.0-structured-state-and-blackboard-engine
blocked_by: [feat--structured-blackboard-state-machine]
related: [feat--progressive-disclosure-and-context-scaling, feat--clean-turn-context-isolation-in-along-team]
---

# Mechanical Bounded Step Prompt Gate and Attention Leak Detection

## Problem

Along enforces static file size budgets for session startup context (`test_context_budget.py`: `AGENTS.md` <= 16 KB, `ISSUES.md` <= 4 KB, `CONSTRAINTS.md` <= 6 KB). However, during dynamic multi-step execution (`along-team`), prompts constructed for subagents (Worker, Reviewer) can grow unbounded if unparsed tool outputs, full-file contents, or historical conversational traces are injected.

As proven in SKILL.state (arXiv:2608.26263, Complexity Analysis), scaling procedural skills over long horizons requires maintaining a strictly bounded O(1) prompt footprint per step to prevent quadratic token inflation and attention drag.

## Requirements

### 1. Declarative Gate Specification (`BoundedPromptGate`)
- Add a new runtime gate in `scripts/alongkit/hooks/default_gates.yaml`:
  - `name`: `BoundedPromptGate`
  - `phase`: `PreToolUse` (when invoking subagent primitives) or internal orchestrator check before spawning workers.
  - `rule`: Inspects synthesized subagent input payloads.
  - Hard limit: Emits an immediate error if a worker prompt payload exceeds 32 KB (~8,000 tokens) without an explicit override flag.
  - Soft warning: Emits advisory warning if payload exceeds 16 KB (~4,000 tokens).

### 2. Attention Leak Detector
- Detect common context bloat anti-patterns in synthesized prompts:
  - Inclusion of entire unparsed log outputs (> 50 lines).
  - Repetition of previous passed step reviews.
  - Embedding raw file dumps that could instead be referenced by path and line anchors.

### 3. CLI Verification and Diagnostics
- Add `along budget check-prompt <file|payload>` to inspect token/character distribution.
- Record prompt budget metrics in `.along/diagnostics/activity_trace.json` under the Agent Run Protocol.

## Acceptance Criteria

- [ ] `BoundedPromptGate` implemented in declarative gate engine and covered by `along hook verify`.
- [ ] Subagent prompt synthesis in `along-team` validates against the bounded prompt budget.
- [ ] Hermetic tests verify that oversized prompts trigger gate failures while compliant prompts pass.
- [ ] Clean ASCII formatting with zero forbidden typography characters.
