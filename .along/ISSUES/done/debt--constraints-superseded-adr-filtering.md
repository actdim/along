---
protocol: along
protocol_version: "4.2.0"
slug: constraints-superseded-adr-filtering
type: debt
status: done
completed: 2026-10-10
priority: medium
created: 2026-09-27
updated: 2026-10-10
agent: cowork
tags: [adr, projections, drift]
milestone: v4.5.0-multi-user-merge-automation
blocked_by: []
related: [docs--vision-md-refresh, debt--session-start-context-budget]
---

# CONSTRAINTS.md lists superseded ADRs as active constraints

## Problem

`.along/CONSTRAINTS.md` is a mandatory session-start read (about 3.2k tokens) and is titled "Active Architectural Constraints", but it includes decisions that later ADRs replaced. Example: `ADR-2026-08-26--protocol-v120-knowledge-base-architecture` (knowledge base in `.along/KB/`) is still `status: accepted` and listed, while `ADR-2026-08-30--llm-wiki-docs-architecture-and-singular-skills-refactoring` moved the KB to `docs/`. An agent reading the projection gets contradictory instructions. Only 4 of 41 ADRs mention supersession at all. In addition, `docs/decisions/` duplicates `.along/DECISIONS/` file by file.

## Requirements

- REQ-1: Audit all 41 ADRs; set `status: superseded` and `superseded_by: <adr-slug>` where a later ADR replaced the decision (at least the v1.2.0 KB, v1.5.0 intent heuristics, pre-v2 naming ADRs).
- REQ-2: `along decision sync` excludes `superseded`, `deprecated` and `rejected` ADRs from `CONSTRAINTS.md` and lists them only in the `DECISIONS.md` board.
- REQ-3: A gate in `along decision sync --check` flags two accepted ADRs that reference the same path or artefact with conflicting statements (heuristic: shared `tags` plus newer ADR mentions the older slug).
- REQ-4: Decide whether `docs/decisions/` is a generated mirror (then mark it generated and exclude from kb-search double counting) or remove it.

## Acceptance Criteria

- [ ] `CONSTRAINTS.md` contains no superseded decision and shrinks measurably
- [ ] Automated tests passing
