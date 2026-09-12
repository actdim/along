---
protocol: along
slug: protocol-v150-automated-entities-and-intent-heuristics
title: "Protocol v1.5.0: Automated Entity Ecosystem & Zero-Friction Intent Recognition"
date: 2026-08-27
status: accepted
tags: [adr, architecture, decision]
---

# ADR-2026-08-27--protocol-v150-automated-entities-and-intent-heuristics - Protocol v1.5.0: Automated Entity Ecosystem & Zero-Friction Intent Recognition

- Date: 2026-08-27
- Status: accepted
- Context: Turning agent tracking into a complete project tracking and dashboard-ready analytics system requires tracking milestones, risks, spikes, checklists, and completed issue timestamps without forcing the human developer to manually manage project files.
- Decision: Expand entity ecosystem with `MILESTONES/`, `RISKS/`, `SPIKES/`, `CHECKLISTS/`, and standardized YAML front-matter (`completed: YYYY-MM-DD`, `agent`, `tags`). Enforce strict automatic intent recognition heuristics in `AGENTS.md` and mandatory stage wrap-up verification checklists in `along-wrap-session`. Provide retroactive auto-migration tooling (`migrate_protocol.py`) across all installation targets.
- Consequences: Full project visibility and analytics ready for `/along-dash` while maintaining zero human friction during everyday coding.
