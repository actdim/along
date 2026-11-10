---
protocol: along
slug: children-allowed-for-cross-context-links-only
type: decision
title: "Children allowed for cross-context links only"
date: 2026-11-10
status: accepted
tags: [adr, architecture, decision]
---

# ADR-2026-11-10--children-allowed-for-cross-context-links-only - Children allowed for cross-context links only

- Date: 2026-11-10
- Status: accepted (supersedes ADR-2026-08-27--entity-relationships-unidirectional-graph-and-canonical-slugs)
- Context: Representing dependencies and associations between issues, risks, and spikes is required for dependency modeling and DAG/timeline visualizations. Dual-syncing reciprocal fields (such as storing both parent and children) causes drift by LLM agents. ADR-2026-08-27 established unidirectional storage (parent: only). However, Git submodule isolation and portability requires that subprojects avoid hard parent references pointing upwards to superprojects that may not exist in standalone checkouts.
- Decision:
  1. Store dependencies unidirectionally in YAML front-matter (`blocked_by: []`, `related: []`, `parent: <slug>`).
  2. A parent/child relationship is stored in exactly one direction. By default, store `parent:` on the child issue.
  3. The `children:` list field is permitted on umbrella issues only when using a path-qualified entry (`<subproject-path>:<key>`) where the child context does not declare its parent. Never store both `parent:` and `children:` for the same pair.
  4. References qualified with `root:` produce a non-blocking diagnostic warning in standalone checkouts without enclosing contexts.
  5. Reference entities strictly by canonical key (`<type>--<slug>` or `<slug>`), never by physical filesystem path, ensuring links remain valid across moves to `done/`.
- Consequences: Preserves submodule decoupling and portability while allowing top-down umbrella issue authorization across superprojects and submodules. Unqualified children entries or dual-direction declarations trigger validation warnings. In standalone clones, root-qualified references warn rather than blocking validation.
