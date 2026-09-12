---
name: along-decision-sync
description: Record architectural/design decisions into the nearest .along/DECISIONS/ as modular ADR records with front-matter, compile projections (.along/DECISIONS.md and .along/CONSTRAINTS.md), and export to docs/decisions/ for MkDocs. Use when a non-trivial technical choice was made, or invokes /along-decision-sync.
---

# Along Decision Sync (`/along-decision-sync`)
Maintains modular Architectural Decision Records (ADRs) in the nearest `.along/DECISIONS/` directory, compiles compact projections (`.along/DECISIONS.md` board and `.along/CONSTRAINTS.md`), and exports ADR pages into `docs/decisions/` for documentation search and MkDocs publishing.

## Scope & Placement
- Always record ADRs in the **NEAREST** `.along/DECISIONS/` for the subproject, module, or submodule being architected.
- Root `.along/DECISIONS/` is reserved for system-wide or cross-package architectural decisions.
- Backward compatibility: single-file `.along/DECISIONS.md` remains supported as a legacy fallback.

## Modular ADR File Format (`.along/DECISIONS/ADR-YYYY-MM-DD--<slug>.md`)
```markdown
---
title: "Decision Title"
date: YYYY-MM-DD
status: accepted # or: superseded
superseded_by: <target-slug> # optional when superseded
type: decision
slug: <slug>
tags:
  - architecture
---

# ADR-YYYY-MM-DD--<slug> - Decision Title

- Date: YYYY-MM-DD
- Status: accepted
- Context: <why this came up>
- Decision: <what was decided>
- Consequences: <trade-offs / follow-ups>
```

## CLI Helper
```bash
# Create a new modular ADR and recompile projections
along decision create <slug> --title "Title" --context "Why" --decision "What" --consequences "Tradeoffs"

# Recompile .along/DECISIONS.md, .along/CONSTRAINTS.md, and docs/decisions/
along decision sync
```
*(Or fallback: `python ~/.along/bin/along_exec.py decision create ...`, `along decision sync`, or `/along-decision-sync`)*

