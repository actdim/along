---
protocol: along
slug: drivers-bound-per-clone-merge-protection-committed
type: decision
title: "Merge drivers are bound per clone; committed .gitattributes carries only built-in -merge protection"
date: 2026-11-15
status: accepted
tags: [adr, architecture, decision]
---

# ADR-2026-11-15--drivers-bound-per-clone-merge-protection-committed - Merge drivers are bound per clone; committed .gitattributes carries only built-in -merge protection

- Date: 2026-11-15
- Status: accepted
- Context: feat--git-automerge-protection-and-semantic-merge: Along markdown (.along/, docs/, AGENTS.md, CLAUDE.md) was line-merged silently on concurrent non-overlapping edits. The previous managed .gitattributes block bound merge=along-projection / merge=along-frontmatter in the tracked file, but git falls back to its built-in TEXT merge for a driver name not defined in .git/config, so every clone without along git setup line-merged entities and projections. A -merge baseline line before the driver lines does not help: git applies the last matching line per attribute.
- Decision: The tracked .gitattributes managed block holds only built-in attributes: -merge for **/.along/**/*.md, **/docs/**/*.md, AGENTS.md, CLAUDE.md, then merge=union for **/.along/HISTORY.md (and a monolithic DECISIONS.md). along git setup binds the custom drivers in GIT_COMMON_DIR/info/attributes (highest precedence, never tracked), always together with their .git/config registration. Marker-less -merge conflicts are resolved from index stages :1:/:2:/:3: by along resolve and along git sync.
- Consequences: Any clone, configured or not, stops on concurrent edits of Along markdown instead of corrupting it; configured clones keep the automatic driver merge. Unconfigured clones see more conflicts, resolved by along git sync. along update / along init / along git setup rewrite old managed blocks; along doctor probes the effective attribute with git check-attr. Refines ADR projection-merge-driver-defers-recompile (driver behaviour unchanged, only where it is bound).
