---
protocol: along
protocol_version: "4.2.0"
slug: along-core-extras-split
type: debt
status: open
priority: low
created: 2026-09-27
updated: 2026-09-27
agent: cowork
tags: [architecture, scope, packaging, versioning]
blocked_by: []
related: [debt--session-start-context-budget, docs--vision-md-refresh]
milestone: v4.5.0-structured-state-and-blackboard-engine
---

# Split Along into a minimal core and optional extras

## Problem

In 54 days the project grew to about 42k lines of Python, 21 skills, 16 gates, 7 entity types, a custom-framework dashboard, OTLP telemetry, a circuit breaker, worktree isolation and a planned Telegram gateway, with four major versions (v1 to v4). The backlog adds Kubernetes operators, GPU pools, enterprise compliance and chat adapters. Breadth outpaces verification (see the review bugs scheduled in v4.3.0), every major version costs adopters a migration, and the always-on protocol grows with every feature.

## Requirements

- REQ-1: Define "Along Core" in an ADR: memory layout, issue/ADR entities, projections, `kb-search`, test/commit contract, and a small set of gates with git/CI enforcement.
- REQ-2: Move dashboard, telemetry/OTLP, circuit breaker, `along-team`, worktree, dep-scan, graph skills and chat gateways into optional extras (`actdim-along[dash]`, `[team]`, `[telemetry]`, ...) with their own protocol sections loaded only when enabled.
- REQ-3: Versioning policy ADR: protocol version changes only on format changes; breaking changes batched into rare majors with migration notes; feature releases are minors.
- REQ-4: Backlog triage: re-scope or park items that do not serve Core until Core has external adopters.
- REQ-5: Validate Core on 2-3 external repositories and record feedback as issues before adding new extras.

## Acceptance Criteria

- [ ] Core ADR accepted and reflected in VISION.md and README
- [ ] `pip install actdim-along` installs only Core dependencies
- [ ] Automated tests passing
