---
protocol: along
protocol_version: "4.4.1"
slug: tiered-model-workflow-guide
type: docs
status: open
priority: high
created: 2026-09-29
updated: 2026-09-29
agent: claude
tags: [docs, explanation, model-tiers, planning, gates]
milestone: v4.7.0-clean-turn-agent-loops-and-state-recovery
blocked_by: []
related: [feat--gate-strictness-profiles, debt--prose-rules-to-deterministic-checks, feat--per-model-rework-metrics, feat--clean-turn-context-isolation-in-along-team]
---

# Tiered-model workflow: strong-model planning, cheap-model execution, deterministic gates

## Problem

Along supports (and should explicitly enforce) a cost-efficient workflow that is not documented anywhere as a first-class pattern:

- a **strong, expensive model** does research, architecture, planning, and diff review;
- a **cheap model** executes plan steps against explicit, checkable done criteria;
- **deterministic steps and gates** sit between them and catch what the cheap model gets wrong.

Users do not see why this works or why planning deserves the expensive model. Without that understanding they either hand everything to one expensive subscription (cost, vendor lock-in) or hand everything to a cheap model (drift, errors).

## Requirements

Write `docs/topic--tiered-model-workflow.md` (`type: explanation`, `write_policy: manual`) covering:

- REQ-1: **Why planning and architecture dominate quality.** Implementation quality is bounded by the plan: a precise plan with REQ-N and done criteria turns execution into a constrained task a cheap model can do; a vague plan makes even a strong executor guess. Errors made at plan level multiply across every step; errors at step level stay local and are caught by gates.
- REQ-2: **Why deterministic steps and gates matter.** Prose rules are probabilistic, code checks are not. Gates work the same with any model, cost zero tokens, are portable across runtimes and vendors, and give an objective done signal. Explain what gates cannot do: they catch violations, they do not fix bad reasoning, which is why the plan and review stay with the strong model.
- REQ-3: **The workflow in Along terms.** Role mapping onto existing mechanisms: issue + REQ-N + acceptance criteria as the contract, `along-team` Living Plan and step loop, session blackboard, `/along-test` and gates as the checkpoint, strong-model diff review, ADRs for decisions. Show a concrete walkthrough of one issue end to end.
- REQ-4: **Configuring it.** Strictness profiles per role (`feat--gate-strictness-profiles`), per-session model/profile override, which gates are mandatory for executor sessions.
- REQ-5: **Vendor independence.** Because state and contracts live in the repo as plain files, the planner and executor can come from different vendors and subscriptions and be swapped without losing context.
- REQ-6: **Measuring it.** How to use `feat--per-model-rework-metrics` to verify the split actually saves money without raising rework.
- REQ-7: Link the article from `docs/INDEX.md` and a short paragraph in `README.md` (via `docs/`, not into `.along/`).

## Acceptance Criteria

- [ ] Article written from actual code and commands (no placeholders); commands verified to exist
- [ ] Linked from `docs/INDEX.md` and `README.md`; `/along-kb-sync` link check passes
- [ ] Clean ASCII typography (`along sanitize` passes)
