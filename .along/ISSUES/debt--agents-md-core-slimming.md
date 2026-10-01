---
protocol: along
protocol_version: "4.4.1"
slug: agents-md-core-slimming
type: debt
status: open
priority: medium
created: 2026-09-29
updated: 2026-09-29
agent: claude
tags: [agents-md, context-budget, progressive-disclosure]
milestone: v4.6.0-structured-state-and-blackboard-engine
blocked_by: [debt--prose-rules-to-deterministic-checks]
related: [feat--gate-strictness-profiles, feat--progressive-disclosure-and-context-scaling, feat--bounded-prompt-footprint-gate]
---

# Slim AGENTS.md to a core of state locations and gates

## Problem

`AGENTS.md` is loaded into every session (currently ~12.5 KB, ceiling 14 KB set by the done issue `debt--agents-md-context-budget-pruning`). Much of it is procedure and explanation that is only needed in specific situations (release, migration, multi-agent routing, documentation routing tree). This is paid on every turn by every model, and it dilutes attention on the rules that matter.

## Requirements

- REQ-1: Reduce the managed block to a core: where state lives, how to anchor work to an issue, the list of gates (tag + one line each), and pointers to on-demand docs.
- REQ-2: Move situational procedure (completion checklist details, documentation routing tree, concurrency/merge rules, release rules, multi-agent routing) into `docs/topic--*.md` articles that agents pull via `/along-kb-search` when relevant.
- REQ-3: Lower the budget ceiling in `tests/test_context_budget.py` to the new size (target: <= 6 KB for the managed block).
- REQ-4: Profile-aware rendering hook for `feat--gate-strictness-profiles` (the renderer accepts a profile and omits rules disabled for it).
- REQ-5: `migrate_protocol.py` / `along-update` refresh existing repos without losing project-specific sections below the managed block.

## Acceptance Criteria

- [ ] Managed block <= 6 KB, enforced by test
- [ ] No rule is lost: every removed paragraph has a destination article or an enforcing gate (checked against the audit from `debt--prose-rules-to-deterministic-checks`)
- [ ] `along-update` on a fixture repo preserves `## Project specifics`
- [ ] Automated tests passing
