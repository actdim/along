---
protocol: along
slug: single-vision-hybrid-reconcile
type: decision
title: "One VISION per context: mechanical reconcile, agent restructure; git-bounded REF blocks"
date: 2026-10-04
status: accepted
tags: [adr, architecture, decision]
---

# ADR-2026-10-04--single-vision-hybrid-reconcile - One VISION per context: mechanical reconcile, agent restructure; git-bounded REF blocks

- Date: 2026-10-04
- Status: accepted
- Context: along-init lost the v1 rule that moved a folder's root VISION.md into the state dir, so repos ended with two VISION files. Restoring a blind move breaks README links (stable-entry-point forbids linking into .along/) and merging two non-empty visions needs judgment. The FULL/REF walk-up without bounds would give a git submodule a REF into its parent repo.
- Decision: The engine (alongkit.scaffold, used by along init, along update and migration Step 13) always removes the root copy: move, dedupe, or append under an along:imported-vision needs-restructure marker, repointing public links to docs/INDEX.md. The agent decomposes a marked section in the same run; along doctor reports leftovers. FULL/REF ancestor search stops at the git working-tree boundary.
- Consequences: Two VISION files never coexist, even after a terminal-only update. A merged section may stay unstructured until an agent session resolves it. Nested published packages still ship a REF AGENTS.md (known limit).
