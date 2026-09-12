---
protocol: along
slug: entity-relationships-unidirectional-graph-and-canonical-slugs
title: "Entity Relationships, Unidirectional Graph Storage & Canonical Slug Invariance"
date: 2026-08-27
status: accepted
tags: [adr, architecture, decision]
---

# ADR-2026-08-27--entity-relationships-unidirectional-graph-and-canonical-slugs - Entity Relationships, Unidirectional Graph Storage & Canonical Slug Invariance

- Date: 2026-08-27
- Status: accepted
- Context: Representing dependencies and associations between issues, risks, and spikes is required for dependency modeling and DAG/timeline visualizations. Using relative file paths breaks references when completed issues move into `done/`. Dual-syncing reciprocal fields (`blocks` vs `blocked_by`, `parent` vs `children`) causes drift by LLM agents.
- Decision:
  1. Store dependencies unidirectionally in YAML front-matter (`blocked_by: []`, `related: []`, `parent: <slug>`). Reverse relationships (`blocks`, `children`) and full DAGs are computed dynamically by graph parsers and dashboard builders.
  2. Reference entities strictly by canonical key (`<type>--<slug>` or `<slug>`), never by physical filesystem path, ensuring links remain valid across moves to `done/`.
  3. Validate DAGs for cyclic dependencies and dangling references in `migrate_protocol.py` and provide a `/along-update` one-liner skill for automated global and project upgrades.
- Consequences: Eliminates link drift, guarantees graph invariance across entity lifecycles, and enables automated dashboard dependency graphs.
