---
protocol: along
protocol_version: "4.4.5"
slug: entity-gate-blocks-preexisting-problems
type: bug
status: done
completed: 2026-10-05
priority: high
created: 2026-10-05
updated: 2026-10-05
agent: claude-code
tags: [gates, entities, hooks]
blocked_by: []
related: [bug--entity-refs-ignore-nested-contexts, bug--migration-dangling-template-milestones]
---

# Entity reference gate blocks turns and issue sync on problems the agent did not introduce

## Problem
The Stop predicate `check_entity_reference_integrity` fires when `git status` shows any
changed entity file and then rejects the turn on every problem in the whole entity graph,
including problems committed long ago. One stale reference elsewhere blocks every turn of
every agent. `along issue sync` and the wrap gate (`gates.entity_integrity_gate`) behave the
same way. The commit-time check (`gitgates.check_entity_references`) already blocks only
problems absent at the base commit.

## Requirements
- REQ-1: The Stop predicate blocks only problems that are absent at `HEAD` (baseline
  validated on a `git archive` snapshot of every `.along/` context in `HEAD`). Without a
  `HEAD` (fresh repository) every problem is new, as before.
- REQ-2: `gates.entity_integrity_gate` (wrap, `along issue sync`) uses the same baseline:
  new problems fail in enforce mode; pre-existing ones are printed as a warning with the
  `along doctor --entities` hint and never fail. `along issue sync` keeps writing the
  projection first.
- REQ-3: Tests: a committed dangling reference plus an unrelated entity change does not
  block the Stop predicate nor `along issue sync`; deleting a referenced entity still
  blocks both.

## Acceptance Criteria
- [x] REQ-1, REQ-2 implemented
- [x] REQ-3 tests pass
- [x] Automated tests passing
