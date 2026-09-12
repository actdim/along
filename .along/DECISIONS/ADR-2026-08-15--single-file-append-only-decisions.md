---
protocol: along
slug: single-file-append-only-decisions
title: "Single-file append-only DECISIONS.md over multi-file MADR/Nygard"
date: 2026-08-15
status: superseded
superseded_by: bounded-context-budget-and-active-projections
tags: [adr, architecture, decision]
---

# ADR-2026-08-15--single-file-append-only-decisions - Single-file append-only DECISIONS.md over multi-file MADR/Nygard

- Date: 2026-08-15
- Status: superseded by ADR-2026-09-07--bounded-context-budget-and-active-projections
- Context: In software engineering, Architectural Decision Records (ADRs) are often kept as separate files per decision (e.g. Michael Nygard / MADR format `doc/adr/0001-*.md`). We evaluated whether `.along/` should store decisions in separate files (like `.along/ISSUES/`) or in a single file.
- Decision: Keep all architectural decisions in a single append-only `.along/DECISIONS.md` file rather than individual files.
- Consequences:
  - **Single-shot context load**: Agents read all active constraints on session start in one tool call (< 300 tokens) without traversing or indexing multiple files.
  - **No lifecycle overhead**: Unlike Issues (`open` -> `in-progress` -> `done/`), decisions are immutable and only appended or marked `superseded by #NNN`.
