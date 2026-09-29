---
protocol: along
protocol_version: "4.2.0"
slug: session-start-context-budget
type: debt
status: done
completed: 2026-09-27
priority: medium
created: 2026-09-27
updated: 2026-09-27
agent: cowork
tags: [context, tokens, agents-md]
milestone: v4.6.0-structured-state-and-blackboard-engine
blocked_by: []
related: [feat--progressive-disclosure-and-context-scaling, feat--bounded-prompt-footprint-gate, debt--constraints-superseded-adr-filtering, debt--along-core-extras-split]
---

# Reduce mandatory session-start context below 3k tokens

## Problem

The protocol requires every session to read `AGENTS.md`, `.along/ISSUES.md` and `.along/CONSTRAINTS.md` before the task file. On this repository that is about 7.5k tokens (AGENTS.md ~3.0k, ISSUES.md ~1.4k, CONSTRAINTS.md ~3.2k, estimated at 4 chars/token), for a product that sells token efficiency. The protocol block also carries rules with high friction for adopters (auto-creating entities without asking, single-agent execution forbidden above 3 files, 9-step wrap on every stage).

## Requirements

- REQ-1: Split the protocol block into a core profile (under 1.5k tokens: memory layout, issue anchoring, test/commit contract, typography) and on-demand sections referenced by path or kb-search.
- REQ-2: `ISSUES.md` session-start view shows only Active plus the top N backlog items by priority; the full backlog moves to `along issue list`.
- REQ-3: `CONSTRAINTS.md` lists one line per active ADR (title + key rule, no truncated paragraph), after `debt--constraints-superseded-adr-filtering`.
- REQ-4: `along context-budget --check` enforces a configurable ceiling for the mandatory reads and runs in CI.
- REQ-5: Make high-friction rules configurable per repo (`.along/config.yaml`: `auto_entities`, `team_escalation_threshold`, `wrap_profile: minimal|full`).

## Acceptance Criteria

- [ ] Mandatory session-start reads on this repo are under 3k tokens as reported by `along context-budget`
- [ ] Automated tests passing
