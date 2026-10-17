---
protocol: along
protocol_version: "4.4.16"
slug: gate-config-layers
type: debt
status: open
priority: medium
created: 2026-10-17
updated: 2026-10-17
agent: claude-code
tags: [gates, hooks, simplification, debt]
parent: feat--autonomous-multi-runtime-mvp
blocked_by: []
related: [debt--gate-simplification]
---

# Gate mode resolution: five layers to three

Split out of debt--gate-simplification (its "Configuration" and "Gate budget" sections).

## Problem

`alongkit/hooks/config.py` `HooksConfig.get_gate_mode` resolves a gate's mode from five
layers: tier (`GATE_TIERS`), state layer (`STATE_LAYER_GATES`), profile
(`strict`/`standard`/`light` in `default_gates.yaml`), `DEFAULT_GATE_MODES`, and the
environment (`ALONG_HOOK_MODE`) plus `.along/config.json` `hooks.gates`. Nobody can predict a
gate's mode without reading the code.

After debt--gate-simplification about 18 runtime gates remain; the budget is about 12.

## Target

- Three layers: catalogue default, repository override (`.along/rules/gates.yaml`), profile
  `interactive` | `autonomous` (autonomous turns ASK into DENY).
- `along gates list` (or `along doctor`) prints each gate's effective mode and where it came from.
- Gate budget: merge or move to commit time until at most about 12 runtime gates remain.
  Candidates: commit_issue_binding and commit_no_conflict_markers (already commit-time in
  gitgates), doc_routing_compliance (commit-time), worktree_env_readiness, bounded_prompt_gate.

## Acceptance Criteria
- [ ] Mode resolution has three layers; tiers and state-layer special cases removed or folded into the catalogue.
- [ ] Effective mode and its source are visible from the CLI.
- [ ] At most about 12 runtime gates in default_gates.yaml.
- [ ] Automated tests passing.
