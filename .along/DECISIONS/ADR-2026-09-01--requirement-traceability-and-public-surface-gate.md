---
protocol: along
slug: requirement-traceability-and-public-surface-gate
title: "Requirement Traceability Matrix, Public Surface Discovery & Reviewer Coverage Gate"
date: 2026-09-01
status: accepted
tags: [adr, architecture, decision]
---

# ADR-2026-09-01--requirement-traceability-and-public-surface-gate - Requirement Traceability Matrix, Public Surface Discovery & Reviewer Coverage Gate

- Date: 2026-09-01
- Status: accepted
- Context: In multi-agent decomposition, when the Supervisor or Architect deconstructs complex user prompts into living plans, sub-requirements (e.g. updating mirrored tables in README.md as well as docs/) were occasionally de-scoped or lost, leading to documentation drift between public surfaces and internal knowledge bases.
- Decision:
  1. **Phase 0 Requirement Traceability Matrix**: Supervisor explicitly decomposes user prompts into atomic requirements (`REQ-1`, `REQ-2`, `REQ-3`).
  2. **Phase 2 Public Surface Discovery**: Architect greps for all mirrored occurrences of modified entities across public entry points (`README.md`, `AGENTS.md`, `docs/`, manifests) and maps each `REQ-N` to target files across all surfaces.
  3. **6-Point Reviewer Rubric**: Formalize an explicit **Requirement Coverage Gate** and **Public Surface Parity Gate** in the mandatory Reviewer rubric, failing any step that satisfies internal docs but omits mirrored public surfaces.
- Consequences: Guarantees 100% requirement fidelity from user prompt to final commit; eliminates drift between internal documentation and public repositories.
