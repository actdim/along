---
protocol: along
slug: along-core-and-modular-extras
type: decision
title: "Along Core and Modular Extras Architecture"
date: 2026-10-23
status: accepted
tags: [adr, architecture, decision]
---

# ADR-2026-10-23--along-core-and-modular-extras - Along Core and Modular Extras Architecture

- Date: 2026-10-23
- Status: accepted
- Context: Along expanded across 21 skills, 16 gates, dashboard UI, OpenTelemetry telemetry, circuit breakers, and team orchestration. The always-on cognitive overhead, dependencies, and protocol complexity burdened basic agent operations. Feature releases bumped protocol versions, creating artificial migration churn.
- Decision: 1. Along Core: Strictly defines minimal in-repo agent context and memory. Core comprises: (a) Memory layout in .along/ with atomic entity files (issues, ADRs, milestones, sessions), projections (ISSUES.md, CONSTRAINTS.md, docs/INDEX.md), and .along/scripts/ lifecycle hooks; (b) Zero-vector bounded snippet retrieval via along-kb-search; (c) Standardized lifecycle contracts (build, test, dev, commit, wrap); (d) Essential mechanical gates (active issue requirement, plan approval, typography cleanliness, projection protection, commit issue binding) enforced via runtime hooks where supported, with git hooks and CI as portable baselines; (e) Minimal runtime dependencies restricted strictly to ruamel.yaml>=0.18. 2. Modular Extras: Moves optional peripheral capabilities into package extras: [dash] (FastAPI, Uvicorn, Pydantic, Rich for executive web dashboard and OpenAPI server), [telemetry] (OpenTelemetry and OpenInference tracer and exporter integrations), and [all] (combining dash and telemetry). Domain extensions like along-team, worktree sandboxing, code-review-graph, and dep-scan operate as modular skills without inflating Core runtime dependencies. 3. Versioning Policy: Protocol version (ALONG-PROTOCOL vX.Y.Z) increments ONLY on format or schema changes. Breaking protocol format changes are strictly batched into rare major releases with migration automation (along migrate). Tooling features are minor releases, and bug fixes/hardening are patch releases.
- Consequences: pip install actdim-along installs strictly Core dependencies (ruamel.yaml). Consumers not using dashboard or telemetry pay zero dependency or startup tax. Protocol stability is decoupled from tooling releases, eliminating unnecessary migration churn.
