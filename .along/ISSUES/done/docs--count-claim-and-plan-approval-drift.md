---
protocol: along
protocol_version: "4.9.1"
slug: count-claim-and-plan-approval-drift
title: "Documentation counts, phase and rubric claims, snippet unit and plan approval drift"
type: docs
status: done
completed: 2026-11-25
priority: medium
created: 2026-11-24
updated: 2026-11-25
agent: dsh
tags: [documentation, drift, counts, gates, skills, kb]
blocked_by: []
related: []
plan_status: approved
---

# Documentation counts, phase and rubric claims, snippet unit and plan approval drift

## Problem

Measured against the v4.9.1 tree, six statements in the knowledge base contradict the code:

1. **Gate count.** `docs/topic--runtime-hooks-and-gates.md:100` claims "33 canonical gates, 11
   of them git/CI-only commit-time checks". Measured: **35** gate ids in
   `scripts/alongkit/hooks/default_gates.yaml` and **12** entries declaring
   `enforcement: [git, ci]` (the list omits `provenance_drift`, which is the twelfth). The
   sentence also still names `require_plan_approval`, `destructive_command`,
   `worktree_env_readiness` and `workspace_containment` as runtime gates in the same breath as
   the commit-time set, which is now correct but reads as if they were git/CI-only.
2. **Skill count.** `docs/topic--architecture.md:148` says "The eighteen skills are thin".
   Measured: **22** directories under `skills/`, matching `README.md`, `docs/topic--skills-reference.md`
   and `.along/VISION.md`, and `along-webdev` is among them.
3. **Phase machine.** `docs/topic--architecture.md:377` announces a "5-Phase State Machine" and
   the diagram below it runs Phase 0 through Phase 5 and then jumps to "Phase 7: Wrap-up".
4. **Rubric size.** `docs/topic--architecture.md:428` announces a "6-Point Verification Rubric"
   and lists seven numbered points.
5. **Snippet unit.** `docs/topic--system-comparisons.md:96-97` and
   `docs/topic--skills-reference.md:309` say the retrieval window is under 150 **tokens**, while
   `README.md` and `.along/VISION.md` say 150 **words**; the code truncates 150 words, so the
   token phrasing understates the actual budget by roughly a third.
6. **Plan approval.** `docs/topic--setup-and-workflow.md:482` states that `along start` "Marks
   the plan as approved (phase: execution, plan_approved: true) and binds the active issue".
   The CLI requires the explicit `--approved` flag (`scripts/along_exec.py:124`), and
   `.along/PROTOCOL.md` states that source edits unlock only after the user approves the plan
   (`[gate: require-plan-approval]`).

Item 6 is the harmful one: it tells a reader that edits are unlocked by binding alone, which is
exactly the assumption `require_plan_approval` denies.

## Requirements

- REQ-1: Correct all six statements, or derive them from code so they cannot drift again.
- REQ-2: At least the gate and skill counts MUST be asserted by a test that reads
  `default_gates.yaml` and `skills/`, so the next gate cannot leave the prose behind.
- REQ-3: The snippet unit MUST be stated once, consistently, in words, matching
  `scripts/along_kb_search.py` behaviour.
- REQ-4: The `along start` description MUST state that plan approval requires the user's
  explicit yes and that binding alone does not unlock source edits.

## Acceptance Criteria

- [x] No document states a gate count other than the catalogue total, and a test enforces it.
- [x] No document states a skill count other than the `skills/` directory total.
- [x] The phase diagram numbers are contiguous and its prose matches the diagram.
- [x] The rubric heading matches the number of listed points.
- [x] Every snippet-window statement uses one unit consistent with the code.
- [x] The `along start` row states the explicit approval requirement.
- [x] `along kb-sync --check` and `along lint` pass.

## Evidence

- Counts: `scripts/alongkit/hooks/default_gates.yaml` (35 ids, 12 `[git, ci]`), `skills/*/SKILL.md`
  (22 files).
- Texts: `docs/topic--architecture.md:148`, `:377`, `:428`;
  `docs/topic--runtime-hooks-and-gates.md:100`; `docs/topic--system-comparisons.md:96-97`;
  `docs/topic--skills-reference.md:309`; `docs/topic--setup-and-workflow.md:482`.
- Approval flag: `scripts/along_exec.py:124`; protocol rule: `.along/PROTOCOL.md`
  `[gate: require-plan-approval]`.
