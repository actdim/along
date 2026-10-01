---
protocol: along
protocol_version: "4.4.1"
slug: planning-fields-and-ordering-gates
type: feat
status: open
priority: high
created: 2026-09-29
updated: 2026-09-29
agent: claude
tags: [planning, priorities, milestones, gates]
milestone: v5.5.0-priority-aware-planning
blocked_by: []
related: [feat--along-plan-strategies, feat--entity-reference-integrity-gate, debt--prose-rules-to-deterministic-checks]
---

# Planning fields and deterministic ordering gates

## Problem

Issue ordering today rests on three fields: `priority`, `milestone`, and `blocked_by`. `priority` conflates value (who wants it), sequencing (what is cheaper to build first), and risk/effort. Ordering correctness depends entirely on the judgment of whoever assigned milestones: nothing stops an issue from being scheduled in an earlier milestone than its blocker, and a customer request can be silently deferred release after release.

## Requirements

- REQ-1: Optional coarse planning fields in the issue schema (`docs/topic--domain-model.md`):
  - `requested_by: customer | internal | tech`
  - `value: high | medium | low`
  - `effort: S | M | L`
  - `risk: high | medium | low`
  - `deferred_reason: "<one line>"` - required when an issue moves to a later milestone.
  Keep scales coarse on purpose: fine-grained numeric scores create false precision.
- REQ-2: `planning_strategy` field on milestones, with a repo-level default in Along config. Allowed values are defined by `feat--along-plan-strategies`.
- REQ-3: The "enables" relation (inverse of `blocked_by`) is computed, never stored.
- REQ-4: Ordering gates, run by `along doctor --entities` and the CI gate subset:
  - ERROR: issue is in an earlier milestone than one of its `blocked_by` issues.
  - ERROR: cycle in `blocked_by`.
  - WARN: open milestone without `planning_strategy` (and no repo default).
  - WARN: open issue without `requested_by`.
  - WARN: `requested_by: customer` + `value: high` issue outside the nearest open milestone without `deferred_reason`.
- REQ-5: `along issue create/update` accept the new fields; `issue update --milestone` to a later milestone prompts for (or requires `--reason`) `deferred_reason`.
- REQ-6: Existing issues without the new fields remain valid (warnings only, no migration required).

## Acceptance Criteria

- [ ] Schema documented; CLI accepts the fields
- [ ] Hermetic fixtures cover each ERROR / WARN case and a clean graph
- [ ] Running the gates on this repository produces no errors
- [ ] Automated tests passing
