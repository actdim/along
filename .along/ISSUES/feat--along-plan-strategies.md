---
protocol: along
protocol_version: "4.4.1"
slug: along-plan-strategies
type: feat
status: open
priority: medium
created: 2026-09-29
updated: 2026-09-29
agent: claude
tags: [planning, priorities, milestones, cli]
milestone: v5.5.0-priority-aware-planning
blocked_by: [feat--planning-fields-and-ordering-gates]
related: [feat--per-model-rework-metrics, docs--tiered-model-workflow-guide]
---

# along plan: strategy-driven milestone sequencing

## Problem

Agents cannot know a human's planning preferences (customer demand vs. building the core first vs. quick wins), so they either guess or ask on every issue. The better contract: ask once per milestone, record the strategy, then apply it mechanically and explain the result.

## Requirements

- REQ-1: Built-in strategies, each a deterministic sort key over the fields from `feat--planning-fields-and-ordering-gates` and the `blocked_by` graph (topological order is always respected first):
  - `value-first`: `requested_by` customer > internal > tech, then `value`.
  - `foundation-first`: number of transitively enabled issues (descending).
  - `risk-first`: `risk` high first; open spikes before the issues they inform.
  - `quick-wins`: `value` descending, `effort` ascending.
  - `deadline-driven`: nearest `due` date first.
  - `cost-of-delay`: simplified WSJF, `value` / `effort` on coarse scales.
- REQ-2: `along plan <milestone> [--strategy <name>] [--json]` prints the proposed order with a one-line reason per issue, and flags issues that the strategy suggests moving to another milestone. Read-only by default.
- REQ-3: `along plan <milestone> --apply` writes the approved order (e.g. `rank:` field) and milestone moves, recording `deferred_reason` for moves; runs through `FileTransaction`.
- REQ-4: Skill guidance (`along-issue-sync`, milestone creation flow): when a milestone is created without a strategy, the agent asks the human once which strategy to use and records it; it does not ask per issue.
- REQ-5: Custom strategies via a small config (ordered list of sort keys) without code changes.

## Acceptance Criteria

- [ ] Each strategy produces a deterministic, explained order on a fixture repo
- [ ] `--apply` is transactional and preserves topological order
- [ ] Documented in `docs/topic--cli-reference.md` and `docs/topic--domain-model.md`
- [ ] Automated tests passing
