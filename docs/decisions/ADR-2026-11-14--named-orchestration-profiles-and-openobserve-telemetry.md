---
protocol: along
slug: named-orchestration-profiles-and-openobserve-telemetry
type: decision
title: "Named Orchestration Profiles and OpenObserve OTLP Telemetry"
date: 2026-11-14
status: accepted
tags: [adr, architecture, decision]
---

# ADR-2026-11-14--named-orchestration-profiles-and-openobserve-telemetry - Named Orchestration Profiles and OpenObserve OTLP Telemetry

- Date: 2026-11-14
- Status: accepted
- Context: Managing heterogeneous agent harnesses requires flexible task allocation without hardcoded CLI configs, alongside real-time trace observability.
- Decision: Adopt declarative named orchestration profiles in .along/orchestration/*.yaml and stream OTel spans over OTLP to OpenObserve with fail-open disk spooling.
- Consequences: Separates process runners from governance protocol, eliminates hardcoded model strings in Python, and enables transparent cross-CLI performance tracking.
