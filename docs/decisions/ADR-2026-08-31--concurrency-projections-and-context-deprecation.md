---
protocol: along
slug: concurrency-projections-and-context-deprecation
title: "Multi-Branch Concurrency, Derived Projections, Context Deprecation, and Mandatory Issue Anchoring"
date: 2026-08-31
status: accepted
tags: [adr, architecture, decision]
---

# ADR-2026-08-31--concurrency-projections-and-context-deprecation - Multi-Branch Concurrency, Derived Projections, Context Deprecation, and Mandatory Issue Anchoring

- Date: 2026-08-31
- Status: accepted
- Context:
  1. Multiple developers and parallel agent sessions working across branches encounter git merge conflicts on shared bottleneck files (CONTEXT.md, ISSUES.md, HISTORY.md, DECISIONS.md).
  2. CONTEXT.md became a degenerate global state entity, causing continuous merge conflicts while duplicating information already tracked in .along/SESSIONS/, active .along/ISSUES/, and session blackboard directories.
  3. Sequential integer numbering of ADRs (#012) led to collisions when two branches added decisions concurrently.
  4. Agents lacked a strict rule prohibiting unanchored code modifications.
- Decision:
  1. **SSOT vs Derived Projections**: Formally classify .along/ISSUES/*.md, .along/SESSIONS/*.md, and docs/topic--*.md as Single Source of Truth (SSOT). Classify ISSUES.md, docs/INDEX.md, and DASHBOARD.md as compiled projections. Enforce zero-manual-merge: merge conflicts in projections are resolved by automated re-sync via /along-issue-sync and /along-kb-sync.
  2. **Deprecate & Delete CONTEXT.md**: Remove CONTEXT.md entirely from protocol scaffolding, session start reading lists, and wrap checklists. Context is localized to feature issues (.along/ISSUES/) and ephemeral session blackboards (.along/.session/<slug>/).
  3. **Decentralized ADR Identifiers**: Transition DECISIONS.md from sequential integers (#NNN) to non-colliding date-slug headers (ADR-YYYY-MM-DD--<slug>).
  4. **Git Merge Union (.gitattributes)**: Configure merge=union for append-only linear files (HISTORY.md, DECISIONS.md).
  5. **Mandatory Issue Anchoring**: Require all non-micro source code modifications to be tied to an active issue in .along/ISSUES/ with status: in-progress.
- Consequences: Eliminates >95% of merge conflicts across parallel developer and agent branches, reduces cold-start token consumption by removing redundant context reads, and ensures full traceability from issue to code commit.
