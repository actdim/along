# Changelog

All notable changes to this project, newest first.

## v3.0.1 - 2026-09-10

- fix(updater): resolve sync_constraints path, along_update help flag, and AGENTS.md spacing (refs #updater-regressions-and-sync-constraints)
- fix: resolve MkDocs root 404 and sync home with README v3.0.0 (refs #mkdocs-root-index-404-and-version-drift)

## v3.0.0 - 2026-09-10

- chore(entities): reconcile v3.0 milestone, register v3.1 modular decisions and clean session log

## v2.6.1 - 2026-09-10

- fix(risks): resolve antigravity git index truncation following upstream v1.3.0 fix (refs #antigravity-extension-git-index-truncation)

## v2.6.0 - 2026-09-10

- No commits recorded since the previous release tag.

## v2.5.0 - 2026-09-10

- feat: implement executable along wrap CLI engine (refs #executable-along-wrap-engine)

## v2.4.0 - 2026-09-10

- refactor: prune AGENTS.md context budget and reconcile v3 DoD (refs #agents-md-context-budget-pruning)

## v2.3.0 - 2026-09-09

- fix(release): resolve broken relative links in session log and sync along-init skill on version bump (refs #runtime-enforcement-of-prose-rules)
- chore(milestone): move circuit breaker to milestone 4.0 and bind dependency on runtime enforcement (refs #systemic-anomaly-circuit-breaker)
- feat(kb): deterministic topic dictionary, auto-crosslinking, and ast grounding (refs #deterministic-kb-pipeline-and-ast-grounding)
- feat: programmatic integrity gates, AST patcher, and git guard (refs #programmatic-integrity-gates-and-git-guard)
- chore(audit): wrap session, record session log, and close quality audit remediation epic (refs #protocol-quality-audit-remediation)
- feat(kb-search): token-based IDF ranking, exact phrases, snippet extraction, and close debt--kb-search-ranking-and-snippet-quality (refs #kb-search-ranking-and-snippet-quality)
- chore(git): renormalize line endings, add regression test, and close debt--line-ending-churn-vs-gitattributes (refs #line-ending-churn-vs-gitattributes)
- fix(line-endings): enforce declared newlines across generator writers and add newline_for_path (refs #line-ending-churn-vs-gitattributes)
- chore: close debt--unpinned-mcp-and-ghost-wiki-query-tool (6/6 criteria met) (refs #unpinned-mcp-and-ghost-wiki-query-tool)
- docs(lifecycle): pluggable lifecycle hooks showcase and docs sync (refs #pluggable-lifecycle-hooks-showcase)

## v2.2.27 - 2026-09-09

- chore(protocol): untrack dashboard artifacts, formalize projection policy, and extend taxonomy (refs #generated-dashboard-artifact-committed)
- feat: auto-generate CONSTRAINTS.md on along-update and migration

## v2.2.26 - 2026-09-07

- refactor: optimize context budget, cap issues board, and compile active constraints (refs #always-on-context-budget-exceeds-claims)
- fix: record ADR for subproject Git path resolution under intent gate and ignore session blackboards (refs #kb-sync-subproject-intent-gate)
- docs(drift): resolve protocol documentation drift and update readme [debt--protocol-documentation-drift]

## v2.2.25 - 2026-09-07

- docs: clean illustrative links in session and decisions, include pyproject.toml in version bump
- fix(protocol): ban file:// URI scheme, update link gates, and migrate legacy references [generated-docs-emit-file-uri-links]

## v2.2.24 - 2026-09-07

- docs: record commit hash in session log (refs #remove-git-locking-workarounds)
- fix: revert broken git locking workarounds and restore stat cache (refs #remove-git-locking-workarounds)

## v2.2.23 - 2026-09-07

- feat: standardize skill commands, add durable session blackboard, and clean changelog (refs #skill-commands-reference-missing-script-paths)

## v2.2.22 - 2026-09-07

- feat: fix git index lock resilience, kb sync atomic writes, and issue milestones (refs #programmatic-integrity-gates-and-git-guard)
- fix: git index self-healing, committer selective staging, and kb-sync idempotency (refs #programmatic-integrity-gates-and-git-guard)
- docs(issues): translate worktree isolation issue to English and eliminate Cyrillic across all issues (refs #runtime-worktree-isolation)
- docs(issues): document semantic intent routing and false positive guards for worktree isolation (refs #runtime-worktree-isolation)
- feat: add issue for deterministic kb pipeline and ast grounding (refs #deterministic-kb-pipeline-and-ast-grounding)

## v2.2.21 - 2026-09-06

- feat(orchestration): provider-agnostic team, engineering provenance, and runtime worktree isolation (refs #runtime-worktree-isolation)

## v2.2.20 - 2026-09-04

- feat(migration): migration resilience and link reconciliation (refs #migration-resilience-and-link-reconciliation)

## v2.2.19 - 2026-09-04

- fix(alongkit): clean up syntax and deduplicate rules.py logic (refs #recent-features-defects-and-guard-messages)
- fix: resolve quality defects in rules engine and execution guards (refs #recent-features-defects-and-guard-messages, #kb-source-provenance-and-reconstruction, #well-known-llms-and-context-discovery)

## v2.2.18 - 2026-09-02

- docs: update dependency registry with actdim 1.5.13 (refs #runtime-enforcement-of-prose-rules)
- refactor(dashboard-ui): upgrade actdim packages to 1.5.13 and refactor EntityDrawer to Dynstruct (refs #runtime-enforcement-of-prose-rules)

## v2.2.17 - 2026-09-02

- feat: implement programmatic rule pack attachment and pruning (refs #runtime-enforcement-of-prose-rules)

## v2.2.16 - 2026-09-02

- No commits recorded since the previous release tag.

## v2.2.15 - 2026-09-02

- fix(alongkit): add library execution guards and ensure_deps to engine scripts Completed debt--library-modules-runnable-as-scripts and updated AGENTS.md rules (refs #kb-source-provenance-and-reconstruction)

## v2.2.14 - 2026-09-02

- No commits recorded since the previous release tag.

## v2.2.13 - 2026-09-02

- No commits recorded since the previous release tag.

## v2.2.12 - 2026-09-01

- test: properly skip bash installer tests if WSL is broken on Windows
- feat(installers): install manifest, MCP honesty, installer parity without deletion
- fix(migration): extend Step 5 typography scope to docs/ and AGENTS.md/README.md

## v2.2.11 - 2026-09-01

- fix(migration): merge instead of overwriting, back up first, dry run by default

## v2.2.10 - 2026-09-01

- fix(release): gate before mutating, roll back on failure, stop reinstalling globals
- fix(migration): stop rewriting prose in an already-current AGENTS.md
- docs(issues): record the managed-block drift finding and the closed REQ-5 in protocol-documentation-drift
- docs(protocol): ban file content in command lines, resync the managed block, gate both
- refactor(engines): extract scripts/alongkit/ as the single implementation, front-matter on ruamel.yaml
- fix: reframe BOM handling around the real invariant, report normalization, clean typography
- fix: repair ADR retrieval and entity lifecycle corruption, record v3.0.0 quality plan

## v2.2.7 - 2026-09-01

- bump version to v2.2.7, knowledge base overhaul, and requirement traceability gates (refs #automated-ui-screenshots-and-visual-verification)
- feat(protocol): integrate documentation blast radius and llm-wiki synchronization (refs #automated-ui-screenshots-and-visual-verification)

## v2.2.6 - 2026-09-01

- bump release to v2.2.6 with Step 8 retroactive migration (refs #automated-ui-screenshots-and-visual-verification)
- fix(migrate): add Step 8 for explicit v2.2.3/v2.2.4 to v2.2.5 link rewriting (refs #automated-ui-screenshots-and-visual-verification)
- fix(update): add retroactive link rewriting, ~/.along/bin script discovery, and interactive prompts (refs #automated-ui-screenshots-and-visual-verification)

## v2.2.5 - 2026-08-31

- feat(kb): add inbound link rewriting, link integrity gate, header dedup, and bump v2.2.5 (refs #automated-ui-screenshots-and-visual-verification)

## v2.2.3 - 2026-08-31

- feat: automated KB migration to docs/ and .archive/, recursive monorepo context updates, and release v2.2.3 (refs #automated-ui-screenshots-and-visual-verification)
- feat(dashboard): integrate knowledge base and ADR decisions into graph visualization v2.2.2 (refs #automated-ui-screenshots-and-visual-verification)
- feat(protocol): bump to v2.2.1, concurrency projections, decentralized ADRs, and remove CONTEXT.md [feat--concurrency-projections-and-context-deprecation]

## v2.1.8 - 2026-08-31

- feat(bumper): auto-sync global installation on local machine during release bump

## v2.1.6 - 2026-08-31

- feat: multi-agent-blackboard-and-architectural-rationale feat(cli): add native entity and scratchpad subcommands to along_exec to prevent shell escaping errors (refs #external-issue-trackers-sync-and-import)

## v2.1.4 - 2026-08-31

- feat: centralize scripts suite, clean skills declarative purity, unify router, and bump v2.1.4 (refs #external-issue-trackers-sync-and-import)

## v2.1.3 - 2026-08-30

- docs: compile session log, refresh context snapshot and history for v2.1.2 release

## v2.1.2 - 2026-08-30

- feat: enable live Mermaid diagram rendering in Dashboard Drawer
- fix: implement transparent uv self-bootstrapping for along_dash runner
- feat: implement dual visual graph architecture with auto-generated Mermaid in INDEX.md and interactive Cytoscape in Dashboard
- refactor: rename along_bump_version to along_version_bump and purge all redundant skill aliases
- feat: implement unified multi-scope knowledge retrieval engine across docs/ and .along/ artifacts
- feat: treat README.md as primary KB source, streamline README into executive entry point, and enforce universal package registry rendering
- docs: add topic--llm-wiki-architecture.md and remove third-party repo references in favor of native paradigm
- feat: enforce strict source scanning (docs, wiki, kb, .along/KB) and front-matter discrimination in along-kb-sync
- fix: enforce deterministic migration pipeline in Step 7 and purge all legacy KB references
- docs: standardize all knowledge base articles to topic-- naming and scaffold .archive/ isolation folder
- docs: populate comprehensive architecture, domain-model and setup articles in docs/
- docs: document adaptive parallel research ingestion heuristic in along-kb-sync
- docs: compile full LLM-Wiki knowledge base and topic index in docs/
- feat: enforce nearest subproject localization and domain-first skill command aliases

## v2.1.1 - 2026-08-30

- v2.1.1 - LLM-Wiki Knowledge Base architecture, docs migration and singular domain-first skills refactoring

## v2.0.11 - 2026-08-28

- docs(llms): add llms.txt standard files, highlight dynamic dashboard and KB search, bump release v2.0.11
- fix(dashboard): resolve header KB search modal opening and reactive state binding
- docs(kb): sync Knowledge Base articles and index cross-links

## v2.0.10 - 2026-08-28

- feat(deps): add along-scan-deps skill and fix dashboard drawer scroll theme and search modal (v2.0.10)

## v2.0.9 - 2026-08-28

- v2.0.9 - upgrade ActDim packages to v1.5.9, NSwag client integration, dynamic MsgMesh adapters, and Decision #011
- docs(dash): update dashboard statistics for v2.0.8 (refs #external-issue-trackers-sync-and-import)

## v2.0.8 - 2026-08-27

- v2.0.8 - bump version, fix bumper variable re.sub bug, and release reconciliation (refs #external-issue-trackers-sync-and-import)
- docs(dash): configure automatic background web server startup with 1-click live link (refs #external-issue-trackers-sync-and-import)
- docs(dash): refresh executive dashboard metrics and reports (refs #external-issue-trackers-sync-and-import)
- chore(session): wrap session, log unit test gates, and sync protocol v2.0.7 state (refs #external-issue-trackers-sync-and-import)
- feat(tests): add comprehensive unit test suite and enforce pre-commit testing gate (refs #external-issue-trackers-sync-and-import)
- feat: -m fix(release): restore clean migrate_protocol and along_update scripts for v2.0.7 release -p (refs #external-issue-trackers-sync-and-import)

## v2.0.7 - 2026-08-27

- feat: -m fix(dash): bundle along_dash.py inside skills/along-dash and clarify server controls -p (refs #external-issue-trackers-sync-and-import)
- feat: -m fix(scripts): restore complete along_update.py engine across scripts and skills -p (refs #external-issue-trackers-sync-and-import)
- fix(scripts): ensure clean 707-line migrate_protocol.py across scripts and skills/along-init -p (refs #external-issue-trackers-sync-and-import)

## v2.0.6 - 2026-08-27

- docs(dash): standardize agent workflow for /along-dash in SKILL.md -p (refs #external-issue-trackers-sync-and-import)
- fix(dash): ensure defensive Cytoscape graph edge validation and add v2.0.0 milestone -p (refs #external-issue-trackers-sync-and-import)
- fix(dash): auto-refresh reports on launch and recommend uv run with fastapi/uvicorn -p (refs #external-issue-trackers-sync-and-import)
- fix(scripts): ensure full 707-line migrate_protocol.py with v2.0.5 sync -p (refs #external-issue-trackers-sync-and-import)

## v2.0.5 - 2026-08-27

- fix(protocol): bump CURRENT_PROTOCOL_VERSION to 2.0.4 in migrate_protocol.py -p (refs #external-issue-trackers-sync-and-import)
- fix(scripts): clean encoding for migrate_protocol and along_update -p (refs #external-issue-trackers-sync-and-import)

## v2.0.4 - 2026-08-27

- docs(readme): document CI/CD deployment best practices and rationale (refs #external-issue-trackers-sync-and-import)
- feat(commit): support -p and --push flags in along_commit.py (refs #external-issue-trackers-sync-and-import)
- feat(bump-version): add short flags -c, -p, -cp for commit and push (refs #external-issue-trackers-sync-and-import)
- feat(skills): unify along-wrap, add along-commit, and deploy lifecycle suite (refs #external-issue-trackers-sync-and-import)
- fix(scripts): ensure clean migrate_protocol.py and universal bump version engine

## v2.0.2 - 2026-08-27

- v2.0.2 - bump version and deploy global skills
- feat(issues): add external issue trackers integration and importer issue
- feat(issues): add OpenClaw and Hermes Agent integration issue
- feat(protocol): implement mandatory agentic code review and blast radius assessment gate
- feat(issues): add automated UI screenshots and agentic code review issues

## v2.0.1 - 2026-08-27

- v2.0.1 - bump version and deploy global skills
- docs: note former actdim-agents name in README subtitle

## v2.0.0 - 2026-08-27

- along v2.0.0 rebranding, isolated .along/ directory, along-* skills, and migration engine

## v1.5.7 - 2026-08-27

- v1.5.7 - repository dashboard and executive analytics engine

## v1.5.6 - 2026-08-27

- v1.5.6 - Recursive in-place update-agents and multi-context migration engine
- feat(update-agents): recursive in-place discovery and update of existing agent contexts

## v1.5.5 - 2026-08-27

- v1.5.5 - Platform Rule Packs, Central Package Management and Monorepo standards

## v1.5.4 - 2026-08-27

- v1.5.4 - entity relationships, dependency graph, and update-agents skill

## v1.5.3 - 2026-08-27

- v1.5.3 - Add bump-version skill and sanitize_typography helper
- feat(skills): add bump-version skill and auto-increment support to bump-version.py
- feat(typography): add sanitize_typography.py, expand forbidden non-ASCII character ban, and sanitize codebase
- fix(scripts): escape emdash unicode character in sanitize_emdash.py

## v1.5.2 - 2026-08-27

- v1.5.2 - Git history reconciliation, typography sanitization, and protocol sync
- fix(skills): populate sync-history SKILL.md and analyze_git_history.py

## v1.5.1 - 2026-08-27

- v1.5.1 - Protocol upgrade, migration engine, Language Rule Packs, and sync-history skill

## v1.3.3 - 2026-08-26

- v1.3.3 release with explicit MCP tool calls across all skills
- feat(skills): explicitly reference wiki-llm MCP tools (search_wiki_tool, sync_wiki_tool) in search-kb and sync-kb

## v1.3.2 - 2026-08-26

- fix(i18n): replace remaining Russian header text in search-kb SKILL.md with English
- feat(tools): add scripts/bump-version.py helper script for safe 2-step version updates
- feat(skills): restore and verify full SKILL.md contents for version v1.3.1
- fix(docs): ensure clean v1.3.1 versioning audit across all docs and protocol

## v1.3.1 - 2026-08-26

- feat(installer): add Windows Junction fallback for seamless non-admin Symlink creation
- feat(skills): add interactive re-initialization prompts for Code Graph and Knowledge Base
- feat(graph): add automatic .code-review-graph-ignore scaffolding and exclusion rules
- feat(protocol): add strict anti-hallucination & fact-grounding rules to protocol and init-kb v1.3.0
- feat(deps): add .mise.toml, uv dependency check, and -InstallDeps flag to installers
- docs(readme): add Git clone and One-Liner install instructions to README and KB
- docs(session): update commit hash in session log

## v1.2.0 - 2026-08-26

- feat(v1.2.0): Knowledge Base (KB) architecture, /init-kb, /search-kb, /check-graph skills and ADR #002/#003
- added stage definition, readme updated, plans updated
- Self-applied, planned new features
- update (tasks->issues) + antigravity support
- Readme updated
- added sync-decisions skill, removed general instructions
- Initial Commit
