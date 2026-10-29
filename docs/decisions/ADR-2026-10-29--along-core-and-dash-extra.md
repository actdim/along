---
protocol: along
slug: along-core-and-dash-extra
type: decision
title: "Along Core and Dash Extra Architecture"
date: 2026-10-29
status: accepted
supersedes: [along-core-and-modular-extras]
tags: [adr, architecture, decision]
---

# ADR-2026-10-29--along-core-and-dash-extra - Along Core and Dash Extra Architecture

- Date: 2026-10-29
- Status: accepted
- Supersedes: `ADR-2026-10-23--along-core-and-modular-extras`
- Context: Review of package extras revealed that [telemetry] declared third-party OpenTelemetry SDK dependencies, whereas Along's telemetry engine is implemented entirely in stdlib Python without external imports. Installing actdim-along[telemetry] introduced unused third-party dependencies.
- Decision: 1. Along Core: Minimal in-repo context, memory, projections, lifecycle contracts, mechanical gates, and stdlib telemetry (tracer, redactor, WAL spool, OTLP/HTTP JSON exporter) with minimal runtime dependencies restricted strictly to ruamel.yaml>=0.18. 2. Modular Extras: The only optional package extra is [dash] (FastAPI, Uvicorn, Pydantic, Rich for the executive dashboard and OpenAPI server). [all] is maintained as a stable alias for [dash]. Peripheral capabilities like along-team, worktree sandboxing, and code review graphs operate as zero-dependency modules. 3. Versioning Policy: Protocol version (ALONG-PROTOCOL vX.Y.Z) increments ONLY on format or schema changes.
- Consequences: pip install actdim-along provides fully functional stdlib OTLP telemetry out of the box with zero third-party dependencies. The [telemetry] extra is removed. Telemetry documentation and installation guides accurately reflect stdlib Core implementation.
