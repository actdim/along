---
protocol: along
protocol_version: "4.4.1"
slug: per-model-rework-metrics
type: feat
status: open
priority: medium
created: 2026-09-29
updated: 2026-09-29
agent: claude
tags: [metrics, model-tiers, telemetry, cost]
milestone: v4.8.0-empirical-benchmarking-and-publications
blocked_by: []
related: [feat--empirical-benchmark-harness-and-metrics, feat--agent-run-protocol-and-observability, feat--gate-strictness-profiles, docs--tiered-model-workflow-guide]
---

# Per-model cost and rework metrics per closed issue

## Problem

Choosing a subscription, a model tier, or a strictness profile is currently done by feel ("this model seems smarter"). Along already records issues, sessions, commits, and gate events, so it can answer the practical question with data: for each model and profile, what does a closed issue cost and how much rework did it need? This complements the synthetic benchmark harness (`feat--empirical-benchmark-harness-and-metrics`) with metrics from real day-to-day work.

## Requirements

- REQ-1: Session logs and commits record `model`, `role` (planner / executor / reviewer), and active profile.
- REQ-2: Collect per issue: tokens / cost (when the runtime reports it), number of sessions, gate blocks by gate, test failures before green, review-requested fixes, reopen count, commits reverted.
- REQ-3: `along metrics` (CLI) aggregates per model x role x profile: cost per closed issue, rework rate, gate-block rate; `--json` output.
- REQ-4: Dashboard view in `along-dash` with the same aggregation.
- REQ-5: Metrics are stored repo-locally (no external service) and never include prompt contents or secrets.

## Acceptance Criteria

- [ ] Fields recorded by `along session create/wrap` and commit binding
- [ ] `along metrics` produces the aggregation on a fixture repo with mixed models
- [ ] Documented in `docs/topic--cli-reference.md`
- [ ] Automated tests passing
