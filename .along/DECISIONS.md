<!-- Generated projection from .along/DECISIONS/*.md. Do not edit by hand. Run: along decision sync -->
# Decisions (ADR Projection Board)

## Active Decisions (47, newest 30 shown)

- [Gate Denials Are Ledger Events; Closing Requires Resolution or User-Verified Disclosure](DECISIONS/ADR-2026-10-23--gate-denials-are-ledger-events.md)
- [Entity model slimmed: spike is an issue type, risks and checklists retired](DECISIONS/ADR-2026-10-19--entity-model-slimmed.md)
- [Gates judge results, not commands](DECISIONS/ADR-2026-10-17--gates-judge-results-not-commands.md)
- [Autonomous mode isolation: one Docker container per environment now, gVisor runtime later](DECISIONS/ADR-2026-10-17--docker-isolation-now-gvisor-later.md)
- [Gate friction fixes of 2026-10-11](DECISIONS/ADR-2026-10-11--gate-friction-fixes.md)
- [An Along installation is Along state, never an AGENTS.md](DECISIONS/ADR-2026-10-07--along-installation-is-state-not-agents-md.md)
- [Subproject boundary is a nested .git or an explicit along init](DECISIONS/ADR-2026-10-06--subproject-boundary-is-git-or-explicit-init.md)
- [Session Event Ledger Is the Source of Truth; Telemetry Is a Projection](DECISIONS/ADR-2026-10-05--session-event-ledger-feeds-telemetry.md)
- [One VISION per context: mechanical reconcile, agent restructure; git-bounded REF blocks](DECISIONS/ADR-2026-10-04--single-vision-hybrid-reconcile.md)
- [Agent-Session Issue Bindings and Plan Approval](DECISIONS/ADR-2026-10-01--agent-session-bindings.md)
- [Projection merge driver keeps ours and defers recompilation](DECISIONS/ADR-2026-09-29--projection-merge-driver-defers-recompile.md)
- [Opt-in git hooks and CI supersede the Zero Git Hooks invariant](DECISIONS/ADR-2026-09-29--opt-in-git-hooks-supersede-zero-git-hooks.md)
- [Decouple code-review-graph from MCP to Direct CLI Execution](DECISIONS/ADR-2026-09-27--decouple-code-review-graph-from-mcp-to-direct-cli.md)
- [Telegram Remote Operational Gateway & Semi-Autonomous Mode vs Interactive IDE](DECISIONS/ADR-2026-09-23--telegram-remote-operational-gateway-and-semi-autonomous-mode.md)
- [One-Liner Self-Bootstrapping Installer and Update Harmonization Over Binary Distribution](DECISIONS/ADR-2026-09-21--oneliner-installer-bootstrap-over-binary-dist.md)
- [Runtime-Native Git Worktree Workspace Isolation and Environment Readiness](DECISIONS/ADR-2026-09-13--runtime-worktree-isolation-and-readiness.md)
- [Declarative Gate Engine and Protocol Traceability Matrix](DECISIONS/ADR-2026-09-13--declarative-gate-engine-and-traceability.md)
- [Single Source of Truth Versioning, PEP 621 Dynamic Hatchling Packaging, and Skill Manifest Decoupling](DECISIONS/ADR-2026-09-09--version-ssot-consolidation-and-dynamic-packaging.md)
- [Untracked Dashboard Artifacts and Derived Projection Boundary](DECISIONS/ADR-2026-09-09--untracked-dashboard-artifacts-and-projection-policy.md)
- [In-Memory Word-Boundary Token Indexing and Ranking over SQLite FTS5](DECISIONS/ADR-2026-09-09--kb-search-in-memory-ranking-vs-sqlite-fts5.md)
- [Explicit Error Handling, Failure Visibility, and Centralized Diagnostics](DECISIONS/ADR-2026-09-09--error-handling-and-failure-visibility.md)
- [Relative Path Prefixing for Subproject Git Revisions under Intent Gate](DECISIONS/ADR-2026-09-07--subproject-git-path-resolution-under-intent-gate.md)
- [Revert GIT_OPTIONAL_LOCKS and diff.autoRefreshIndex to Preserve Git Stat-Cache Integrity](DECISIONS/ADR-2026-09-07--revert-git-stat-cache-workarounds.md)
- [Durable Multi-Agent Session Blackboard and Canonical CLI Skill Execution](DECISIONS/ADR-2026-09-07--durable-session-blackboard-and-canonical-cli.md)
- [Bounded Context Budget, Active Constraints Projection, and Sliding Window Issues](DECISIONS/ADR-2026-09-07--bounded-context-budget-and-active-projections.md)
- [Ban file:// Scheme in Markdown Links in Favor of Standard Relative Links](DECISIONS/ADR-2026-09-07--ban-file-uri-scheme-in-markdown-links.md)
- [Authored vs Compiled Documentation Boundaries and Automated Consistency Gates](DECISIONS/ADR-2026-09-07--authored-vs-compiled-documentation-boundaries.md)
- [Provider-Agnostic Subagent Primitives and Single-Agent Degradation in along-team](DECISIONS/ADR-2026-09-06--provider-agnostic-subagent-abstraction.md)
- [Engineering Provenance, Dual-Track UI Projections, and Loop Trace Disambiguation](DECISIONS/ADR-2026-09-06--engineering-provenance-and-dual-track-artifact-loop.md)
- [Scope and Enforcement Mode of the ASCII Typography Rule](DECISIONS/ADR-2026-09-01--typography-rule-scope.md)

Older decisions (17): docs/decisions/INDEX.md

## Superseded & Retired Decisions (6)

- single-file-append-only-decisions -> bounded-context-budget-and-active-projections
- code-graph-mcp-and-hybrid-kb-search -> decouple-code-review-graph-from-mcp-to-direct-cli
- protocol-v120-knowledge-base-architecture -> llm-wiki-docs-architecture-and-singular-skills-refactoring
- protocol-v150-automated-entities-and-intent-heuristics -> entity-relationships-unidirectional-graph-and-canonical-slugs
- universal-version-bumping-and-scripts-ecosystem -> version-ssot-consolidation-and-dynamic-packaging
- windows-git-concurrency-and-index-lock-mitigation -> revert-git-stat-cache-workarounds
