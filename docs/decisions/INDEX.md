---
protocol: along
slug: decisions-index
title: Architectural Decision Records
type: index
tags: [adr, architecture, decisions, index]
---

# Architectural Decision Records (ADRs)

This directory contains the project's Architectural Decision Records.
Decisions are authored and maintained in `.along/DECISIONS/` and published here as first-class documentation.

## Active Decisions (35)

- **[code-graph-mcp-and-hybrid-kb-search](./ADR-2026-08-26--code-graph-mcp-and-hybrid-kb-search.md)** - Code Graph & Hybrid Knowledge Base Search MCP Integration
- **[protocol-v120-knowledge-base-architecture](./ADR-2026-08-26--protocol-v120-knowledge-base-architecture.md)** - Protocol v1.2.0 & Knowledge Base (KB) Architecture Standard
- **[along-v200-rebranding-and-namespace-isolation](./ADR-2026-08-27--along-v200-rebranding-and-namespace-isolation.md)** - Along v2.0.0: Rebranding, Isolated .along/ Directory, along-* Skill Prefixes, and protocol: along Metadata
- **[autonomous-multi-mode-dashboard-and-analytics-engine](./ADR-2026-08-27--autonomous-multi-mode-dashboard-and-analytics-engine.md)** - Autonomous Multi-Mode Repository Dashboard & Analytics Engine
- **[entity-relationships-unidirectional-graph-and-canonical-slugs](./ADR-2026-08-27--entity-relationships-unidirectional-graph-and-canonical-slugs.md)** - Entity Relationships, Unidirectional Graph Storage & Canonical Slug Invariance
- **[mandatory-code-review-and-blast-radius-impact-gate](./ADR-2026-08-27--mandatory-code-review-and-blast-radius-impact-gate.md)** - Mandatory Agentic Code Review & Blast Radius Impact Assessment Gate
- **[protocol-v150-automated-entities-and-intent-heuristics](./ADR-2026-08-27--protocol-v150-automated-entities-and-intent-heuristics.md)** - Protocol v1.5.0: Automated Entity Ecosystem & Zero-Friction Intent Recognition
- **[unified-along-wrap-commit-and-lifecycle-runners](./ADR-2026-08-27--unified-along-wrap-commit-and-lifecycle-runners.md)** - Unified /along-wrap, Smart /along-commit, and Lifecycle Execution Suite (/along-build, /along-test, /along-dev)
- **[universal-version-bumping-and-scripts-ecosystem](./ADR-2026-08-27--universal-version-bumping-and-scripts-ecosystem.md)** - Universal Project Version Bumping & Repository Scripts Ecosystem (.along/scripts/)
- **[frontend-dynstruct-architecture-and-msgmesh-adapters](./ADR-2026-08-28--frontend-dynstruct-architecture-and-msgmesh-adapters.md)** - Frontend Architecture: Dynstruct Component Architecture, MessageMesh Integration, and NSwag Adapters
- **[llm-wiki-docs-architecture-and-singular-skills-refactoring](./ADR-2026-08-30--llm-wiki-docs-architecture-and-singular-skills-refactoring.md)** - LLM-Wiki Knowledge Base Architecture in docs/, .archive/ Isolation & Singular Domain-First Skills Refactoring
- **[multi-agent-protocol-along-team-and-goal-integration](./ADR-2026-08-30--multi-agent-protocol-along-team-and-goal-integration.md)** - Multi-Agent Development Protocol (along-team), Sequential State Machine, Living Plan, and /goal Integration
- **[concurrency-projections-and-context-deprecation](./ADR-2026-08-31--concurrency-projections-and-context-deprecation.md)** - Multi-Branch Concurrency, Derived Projections, Context Deprecation, and Mandatory Issue Anchoring
- **[global-self-diagnostics-and-feedback-subsystem](./ADR-2026-08-31--global-self-diagnostics-and-feedback-subsystem.md)** - Global Self-Diagnostics, PII Redaction, and Multi-Transport Feedback Engine
- **[session-scoped-blackboard-memory-and-role-contracts](./ADR-2026-08-31--session-scoped-blackboard-memory-and-role-contracts.md)** - Session-Scoped Blackboard Memory, Strict Multi-Agent Role Contracts, and Mandatory Architectural Rationale Standards
- **[frontmatter-on-ruamel-yaml](./ADR-2026-09-01--frontmatter-on-ruamel-yaml.md)** - Front-matter on ruamel.yaml, with uv for Dependency Delivery
- **[installers-never-delete-what-they-did-not-write](./ADR-2026-09-01--installers-never-delete-what-they-did-not-write.md)** - The Installers Copy, an Engine Decides, and a Manifest Remembers
- **[migration-never-deletes-a-destination](./ADR-2026-09-01--migration-never-deletes-a-destination.md)** - A Migration Merges, Backs Up, and Defaults to a Dry Run
- **[release-gates-before-mutations](./ADR-2026-09-01--release-gates-before-mutations.md)** - Gates Precede Mutations, and a Release Is Transactional
- **[requirement-traceability-and-public-surface-gate](./ADR-2026-09-01--requirement-traceability-and-public-surface-gate.md)** - Requirement Traceability Matrix, Public Surface Discovery & Reviewer Coverage Gate
- **[shared-engine-package](./ADR-2026-09-01--shared-engine-package.md)** - Shared Implementation Package for the Engines (scripts/alongkit/)
- **[typography-rule-scope](./ADR-2026-09-01--typography-rule-scope.md)** - Scope and Enforcement Mode of the ASCII Typography Rule
- **[engineering-provenance-and-dual-track-artifact-loop](./ADR-2026-09-06--engineering-provenance-and-dual-track-artifact-loop.md)** - Engineering Provenance, Dual-Track UI Projections, and Loop Trace Disambiguation
- **[provider-agnostic-subagent-abstraction](./ADR-2026-09-06--provider-agnostic-subagent-abstraction.md)** - Provider-Agnostic Subagent Primitives and Single-Agent Degradation in along-team
- **[authored-vs-compiled-documentation-boundaries](./ADR-2026-09-07--authored-vs-compiled-documentation-boundaries.md)** - Authored vs Compiled Documentation Boundaries and Automated Consistency Gates
- **[ban-file-uri-scheme-in-markdown-links](./ADR-2026-09-07--ban-file-uri-scheme-in-markdown-links.md)** - Ban file:// Scheme in Markdown Links in Favor of Standard Relative Links
- **[bounded-context-budget-and-active-projections](./ADR-2026-09-07--bounded-context-budget-and-active-projections.md)** - Bounded Context Budget, Active Constraints Projection, and Sliding Window Issues
- **[durable-session-blackboard-and-canonical-cli](./ADR-2026-09-07--durable-session-blackboard-and-canonical-cli.md)** - Durable Multi-Agent Session Blackboard and Canonical CLI Skill Execution
- **[revert-git-stat-cache-workarounds](./ADR-2026-09-07--revert-git-stat-cache-workarounds.md)** - Revert GIT_OPTIONAL_LOCKS and diff.autoRefreshIndex to Preserve Git Stat-Cache Integrity
- **[subproject-git-path-resolution-under-intent-gate](./ADR-2026-09-07--subproject-git-path-resolution-under-intent-gate.md)** - Relative Path Prefixing for Subproject Git Revisions under Intent Gate
- **[error-handling-and-failure-visibility](./ADR-2026-09-09--error-handling-and-failure-visibility.md)** - Explicit Error Handling, Failure Visibility, and Centralized Diagnostics
- **[kb-search-in-memory-ranking-vs-sqlite-fts5](./ADR-2026-09-09--kb-search-in-memory-ranking-vs-sqlite-fts5.md)** - In-Memory Word-Boundary Token Indexing and Ranking over SQLite FTS5
- **[untracked-dashboard-artifacts-and-projection-policy](./ADR-2026-09-09--untracked-dashboard-artifacts-and-projection-policy.md)** - Untracked Dashboard Artifacts and Derived Projection Boundary
- **[version-ssot-consolidation-and-dynamic-packaging](./ADR-2026-09-09--version-ssot-consolidation-and-dynamic-packaging.md)** - Single Source of Truth Versioning, PEP 621 Dynamic Hatchling Packaging, and Skill Manifest Decoupling
- **[declarative-gate-engine-and-traceability](./ADR-2026-09-13--declarative-gate-engine-and-traceability.md)** - Declarative Gate Engine and Protocol Traceability Matrix

## Superseded & Retired Decisions (2)

- **[single-file-append-only-decisions](./ADR-2026-08-15--single-file-append-only-decisions.md)** - Single-file append-only DECISIONS.md over multi-file MADR/Nygard *(superseded by bounded-context-budget-and-active-projections)*
- **[windows-git-concurrency-and-index-lock-mitigation](./ADR-2026-09-06--windows-git-concurrency-and-index-lock-mitigation.md)** - Windows Git Concurrency Hardening: Disabling Optional Locks and Preload Races *(superseded by revert-git-stat-cache-workarounds)*
