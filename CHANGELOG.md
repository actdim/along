# Changelog

All notable changes to this project, newest first.

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
- release: v2.2.8 - bump version and release reconciliation
- release(v2.2.7): bump version to v2.2.7, knowledge base overhaul, and requirement traceability gates (refs #automated-ui-screenshots-and-visual-verification)
- feat(protocol): integrate documentation blast radius and llm-wiki synchronization (refs #automated-ui-screenshots-and-visual-verification)
- release(v2.2.6): bump release to v2.2.6 with Step 8 retroactive migration (refs #automated-ui-screenshots-and-visual-verification)
- fix(migrate): add Step 8 for explicit v2.2.3/v2.2.4 to v2.2.5 link rewriting (refs #automated-ui-screenshots-and-visual-verification)
- fix(update): add retroactive link rewriting, ~/.along/bin script discovery, and interactive prompts (refs #automated-ui-screenshots-and-visual-verification)
- feat(kb): add inbound link rewriting, link integrity gate, header dedup, and bump v2.2.5 (refs #automated-ui-screenshots-and-visual-verification)
- release: v2.2.4 - bump version and release reconciliation
- feat: automated KB migration to docs/ and .archive/, recursive monorepo context updates, and release v2.2.3 (refs #automated-ui-screenshots-and-visual-verification)
- feat(dashboard): integrate knowledge base and ADR decisions into graph visualization v2.2.2 (refs #automated-ui-screenshots-and-visual-verification)
- feat(protocol): bump to v2.2.1, concurrency projections, decentralized ADRs, and remove CONTEXT.md [feat--concurrency-projections-and-context-deprecation]
- release: v2.1.8 - bump version and release reconciliation
- feat(bumper): auto-sync global installation on local machine during release bump
- release: v2.1.7 - bump version and release reconciliation
- release: v2.1.6 - bump version and release reconciliation
- feat: multi-agent-blackboard-and-architectural-rationale feat(cli): add native entity and scratchpad subcommands to along_exec to prevent shell escaping errors (refs #external-issue-trackers-sync-and-import)
- release: v2.1.5 - bump version and release reconciliation
- feat: centralize scripts suite, clean skills declarative purity, unify router, and bump v2.1.4 (refs #external-issue-trackers-sync-and-import)
- release: v2.1.3 - bump version and release reconciliation
- docs: compile session log, refresh context snapshot and history for v2.1.2 release
- release: v2.1.2 - bump version and release reconciliation
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
- release: v2.1.1 - LLM-Wiki Knowledge Base architecture, docs migration and singular domain-first skills refactoring
- docs(llms): add llms.txt standard files, highlight dynamic dashboard and KB search, bump release v2.0.11
- fix(dashboard): resolve header KB search modal opening and reactive state binding
- docs(kb): sync Knowledge Base articles and index cross-links
- feat(deps): add along-scan-deps skill and fix dashboard drawer scroll theme and search modal (v2.0.10)
- release: v2.0.9 - upgrade ActDim packages to v1.5.9, NSwag client integration, dynamic MsgMesh adapters, and Decision #011
- docs(dash): update dashboard statistics for v2.0.8 (refs #external-issue-trackers-sync-and-import)
- release: v2.0.8 - bump version, fix bumper variable re.sub bug, and release reconciliation (refs #external-issue-trackers-sync-and-import)
- docs(dash): configure automatic background web server startup with 1-click live link (refs #external-issue-trackers-sync-and-import)
- docs(dash): refresh executive dashboard metrics and reports (refs #external-issue-trackers-sync-and-import)
- chore(session): wrap session, log unit test gates, and sync protocol v2.0.7 state (refs #external-issue-trackers-sync-and-import)
- feat(tests): add comprehensive unit test suite and enforce pre-commit testing gate (refs #external-issue-trackers-sync-and-import)
- feat: -m fix(release): restore clean migrate_protocol and along_update scripts for v2.0.7 release -p (refs #external-issue-trackers-sync-and-import)
- release: v2.0.7 - bump version and release reconciliation
- feat: -m fix(dash): bundle along_dash.py inside skills/along-dash and clarify server controls -p (refs #external-issue-trackers-sync-and-import)
- feat: -m fix(scripts): restore complete along_update.py engine across scripts and skills -p (refs #external-issue-trackers-sync-and-import)
- fix(scripts): ensure clean 707-line migrate_protocol.py across scripts and skills/along-init -p (refs #external-issue-trackers-sync-and-import)
- release: v2.0.6 - bump version and release reconciliation
- docs(dash): standardize agent workflow for /along-dash in SKILL.md -p (refs #external-issue-trackers-sync-and-import)
- fix(dash): ensure defensive Cytoscape graph edge validation and add v2.0.0 milestone -p (refs #external-issue-trackers-sync-and-import)
- fix(dash): auto-refresh reports on launch and recommend uv run with fastapi/uvicorn -p (refs #external-issue-trackers-sync-and-import)
- fix(scripts): ensure full 707-line migrate_protocol.py with v2.0.5 sync -p (refs #external-issue-trackers-sync-and-import)
- release: v2.0.5 - bump version and release reconciliation
- fix(protocol): bump CURRENT_PROTOCOL_VERSION to 2.0.4 in migrate_protocol.py -p (refs #external-issue-trackers-sync-and-import)
- fix(scripts): clean encoding for migrate_protocol and along_update -p (refs #external-issue-trackers-sync-and-import)
- release: v2.0.4 - bump version and release reconciliation
- docs(readme): document CI/CD deployment best practices and rationale (refs #external-issue-trackers-sync-and-import)
- feat(commit): support -p and --push flags in along_commit.py (refs #external-issue-trackers-sync-and-import)
- feat(bump-version): add short flags -c, -p, -cp for commit and push (refs #external-issue-trackers-sync-and-import)
- feat(skills): unify along-wrap, add along-commit, and deploy lifecycle suite (refs #external-issue-trackers-sync-and-import)
- fix(scripts): ensure clean migrate_protocol.py and universal bump version engine
- release: v2.0.3 - bump version and release reconciliation
- release: v2.0.2 - bump version and deploy global skills
- feat(issues): add external issue trackers integration and importer issue
- feat(issues): add OpenClaw and Hermes Agent integration issue
- feat(protocol): implement mandatory agentic code review and blast radius assessment gate
- feat(issues): add automated UI screenshots and agentic code review issues
- release: v2.0.1 - bump version and deploy global skills
- docs: note former actdim-agents name in README subtitle
- release: along v2.0.0 rebranding, isolated .along/ directory, along-* skills, and migration engine
- bump(version): v1.5.7 - repository dashboard and executive analytics engine
- bump(version): v1.5.6 - Recursive in-place update-agents and multi-context migration engine
- feat(update-agents): recursive in-place discovery and update of existing agent contexts
- bump(version): v1.5.5 - Platform Rule Packs, Central Package Management and Monorepo standards
- bump(version): v1.5.4 - entity relationships, dependency graph, and update-agents skill
- bump(version): v1.5.3 - Add bump-version skill and sanitize_typography helper
- feat(skills): add bump-version skill and auto-increment support to bump-version.py
- feat(typography): add sanitize_typography.py, expand forbidden non-ASCII character ban, and sanitize codebase
- fix(scripts): escape emdash unicode character in sanitize_emdash.py
- bump(version): v1.5.2 - Git history reconciliation, typography sanitization, and protocol sync
- fix(skills): populate sync-history SKILL.md and analyze_git_history.py
- feat(release): v1.5.1 - Protocol upgrade, migration engine, Language Rule Packs, and sync-history skill
- bump(version): v1.3.3 release with explicit MCP tool calls across all skills
- feat(skills): explicitly reference wiki-llm MCP tools (search_wiki_tool, sync_wiki_tool) in search-kb and sync-kb
- bump(version): v1.3.2 release
- fix(i18n): replace remaining Russian header text in search-kb SKILL.md with English
- feat(tools): add scripts/bump-version.py helper script for safe 2-step version updates
- feat(skills): restore and verify full SKILL.md contents for version v1.3.1
- fix(docs): ensure clean v1.3.1 versioning audit across all docs and protocol
- bump(version): v1.3.1 release
- feat(installer): add Windows Junction fallback for seamless non-admin Symlink creation
- feat(skills): add interactive re-initialization prompts for Code Graph and Knowledge Base
- feat(graph): add automatic .code-review-graph-ignore scaffolding and exclusion rules
- feat(protocol): add strict anti-hallucination & fact-grounding rules to protocol and init-kb v1.3.0
- feat(deps): add .mise.toml, uv dependency check, and -InstallDeps flag to installers
- docs(readme): add Git clone and One-Liner install instructions to README and KB
- docs(session): update commit hash in session log
- feat(v1.2.0): Knowledge Base (KB) architecture, /init-kb, /search-kb, /check-graph skills and ADR #002/#003
- added stage definition, readme updated, plans updated
- Self-applied, planned new features
- update (tasks->issues) + antigravity support
- Readme updated
- added sync-decisions skill, removed general instructions
- Initial Commit

