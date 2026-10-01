---
protocol: along
protocol_version: "4.4.1"
slug: gate-strictness-profiles
type: feat
status: open
priority: high
created: 2026-09-29
updated: 2026-09-29
agent: claude
tags: [gates, profiles, model-tiers, context-budget]
milestone: v4.6.0-structured-state-and-blackboard-engine
blocked_by: []
related: [debt--prose-rules-to-deterministic-checks, debt--agents-md-core-slimming, feat--bounded-prompt-footprint-gate, docs--tiered-model-workflow-guide]
---

# Gate strictness profiles (strict / light) per model tier

## Problem

Along applies one fixed level of procedural control to every model. Strong models (Opus-class) pay a context and attention tax for step-by-step procedure they do not need, and are sometimes pushed into ritual work (forced `along-team` routing on > 3 files, long checklists). Cheap or weak models, on the other hand, benefit from exactly that procedure. The protocol needs to separate the **state layer** (issues, ADRs, history, sessions - always on, portable) from the **control layer** (procedural rules and gates - tunable per model tier).

## Requirements

- REQ-1: Define named profiles in a tracked config (e.g. `.along/config.yaml` `profile: strict | standard | light`), with `standard` as the default that preserves current behavior.
- REQ-2: Each gate in `scripts/alongkit/hooks/default_gates.yaml` declares which profiles enable it and at what severity (`block` / `warn` / `off`). The state layer (issue anchoring, projection protection, typography, test_before_stop) MUST stay on in every profile.
- REQ-3: The profile controls procedural rules too: `along-team` escalation threshold, checklist verbosity, plan requirement for direct execution.
- REQ-4: Profile can be overridden per session (`ALONG_PROFILE` env var or `along start --profile`) so one repo can run a strong planner and a cheap executor with different profiles.
- REQ-5: `along doctor` and `along hook verify` print the active profile and the resulting gate matrix.
- REQ-6: Managed `AGENTS.md` block renders only the rules relevant to the active profile (coordinate with `debt--agents-md-core-slimming`).

## Acceptance Criteria

- [ ] Profiles defined, documented in `docs/topic--runtime-hooks-and-gates.md`, default is behavior-preserving
- [ ] Hermetic tests: same violation blocks in `strict`, warns in `light` for procedural gates; state-layer gates block in all profiles
- [ ] Session-level override verified
- [ ] Automated tests passing
