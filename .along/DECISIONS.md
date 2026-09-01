# Decisions (ADR - append-only)

_One dated entry per architectural decision. Never edit past entries; mark a replaced one "Superseded by #N"._

<!-- Template:
## ADR-YYYY-MM-DD--<slug> - <Title>
- Date: YYYY-MM-DD
- Status: accepted            (or: superseded by ADR-YYYY-MM-DD--<slug>)
- Context: <why this came up>
- Decision: <what was decided>
- Consequences: <trade-offs / follow-ups>
-->

## ADR-2026-08-15--single-file-append-only-decisions - Single-file append-only DECISIONS.md over multi-file MADR/Nygard
- Date: 2026-08-15
- Status: accepted
- Context: In software engineering, Architectural Decision Records (ADRs) are often kept as separate files per decision (e.g. Michael Nygard / MADR format `doc/adr/0001-*.md`). We evaluated whether `.along/` should store decisions in separate files (like `.along/ISSUES/`) or in a single file.
- Decision: Keep all architectural decisions in a single append-only `.along/DECISIONS.md` file rather than individual files.
- Consequences:
  - **Single-shot context load**: Agents read all active constraints on session start in one tool call (< 300 tokens) without traversing or indexing multiple files.
  - **No lifecycle overhead**: Unlike Issues (`open` -> `in-progress` -> `done/`), decisions are immutable and only appended or marked `superseded by #NNN`.

## ADR-2026-08-26--protocol-v120-knowledge-base-architecture - Protocol v1.2.0 & Knowledge Base (KB) Architecture Standard
- Date: 2026-08-26
- Status: accepted
- Context: Projects require a structured, persistent Knowledge Base that provides deep architecture, domain model, and workflow guidance without bloating `AGENTS.md` context window.
- Decision: Adopt Knowledge Base (KB) terminology and structure in `.along/KB/` (`INDEX.md`, `01-architecture.md`, `02-domain-model.md`, `03-setup-and-workflow.md`). `AGENTS.md` remains a compact executive entry point linking to KB articles (`[[.along/KB/INDEX.md]]`). Human `docs/` and `README.md` are scanned as read-only inputs during `/along-init-kb` and `/along-sync-kb`.
- Consequences: `AGENTS.md` stays lean (< 80 lines) while agents and humans have structured access to deep documentation.

## ADR-2026-08-26--code-graph-mcp-and-hybrid-kb-search - Code Graph & Hybrid Knowledge Base Search MCP Integration
- Date: 2026-08-26
- Status: accepted
- Context: Agents need lightweight tools to inspect call hierarchies and search project documentation without loading massive raw files.
- Decision: Integrate `code-review-graph` for AST call graph analysis and impact radius, and `wiki-llm` / native hybrid search (`/along-search-kb`, `/along-sync-kb`) for document querying. Provide `/along-check-graph` and `/along-search-kb` debugging slash commands across all agent tools (Antigravity, Claude Code, Codex, OpenCode).
- Consequences: Agents prioritize MCP graph and hybrid search calls during research and refactoring, saving token overhead.

## ADR-2026-08-27--protocol-v150-automated-entities-and-intent-heuristics - Protocol v1.5.0: Automated Entity Ecosystem & Zero-Friction Intent Recognition
- Date: 2026-08-27
- Status: accepted
- Context: Turning agent tracking into a complete project tracking and dashboard-ready analytics system requires tracking milestones, risks, spikes, checklists, and completed issue timestamps without forcing the human developer to manually manage project files.
- Decision: Expand entity ecosystem with `MILESTONES/`, `RISKS/`, `SPIKES/`, `CHECKLISTS/`, and standardized YAML front-matter (`completed: YYYY-MM-DD`, `agent`, `tags`). Enforce strict automatic intent recognition heuristics in `AGENTS.md` and mandatory stage wrap-up verification checklists in `along-wrap-session`. Provide retroactive auto-migration tooling (`migrate_protocol.py`) across all installation targets.
- Consequences: Full project visibility and analytics ready for `/along-dash` while maintaining zero human friction during everyday coding.

## ADR-2026-08-27--entity-relationships-unidirectional-graph-and-canonical-slugs - Entity Relationships, Unidirectional Graph Storage & Canonical Slug Invariance
- Date: 2026-08-27
- Status: accepted
- Context: Representing dependencies and associations between issues, risks, and spikes is required for dependency modeling and DAG/timeline visualizations. Using relative file paths breaks references when completed issues move into `done/`. Dual-syncing reciprocal fields (`blocks` vs `blocked_by`, `parent` vs `children`) causes drift by LLM agents.
- Decision:
  1. Store dependencies unidirectionally in YAML front-matter (`blocked_by: []`, `related: []`, `parent: <slug>`). Reverse relationships (`blocks`, `children`) and full DAGs are computed dynamically by graph parsers and dashboard builders.
  2. Reference entities strictly by canonical key (`<type>--<slug>` or `<slug>`), never by physical filesystem path, ensuring links remain valid across moves to `done/`.
  3. Validate DAGs for cyclic dependencies and dangling references in `migrate_protocol.py` and provide a `/along-update` one-liner skill for automated global and project upgrades.
- Consequences: Eliminates link drift, guarantees graph invariance across entity lifecycles, and enables automated dashboard dependency graphs.

## ADR-2026-08-27--autonomous-multi-mode-dashboard-and-analytics-engine - Autonomous Multi-Mode Repository Dashboard & Analytics Engine
- Date: 2026-08-27
- Status: accepted
- Context: Developers and agents require instant visibility into entity lifecycles, milestone completion rates, active blockers, and dependency DAGs without manual data compilation or heavy infrastructure.
- Decision:
  1. Implement an autonomous Python script (`scripts/along_dash.py`) using PEP 723 inline dependencies (`# /// script ...`) executable directly via `uv run scripts/along_dash.py`.
  2. Provide 4 decoupled operational modes in a single codebase: CLI Mode, Interactive Web Mode, Static HTML Export, and Markdown Dashboard Report (`.along/DASHBOARD.md`).
  3. Expose the `/along-dash` skill across Claude Code, Codex, OpenCode, and Antigravity.
- Consequences: Zero setup cost, instant offline/online dashboard visualization across all execution environments.

## ADR-2026-08-27--along-v200-rebranding-and-namespace-isolation - Along v2.0.0: Rebranding, Isolated .along/ Directory, along-* Skill Prefixes, and protocol: along Metadata
- Date: 2026-08-27
- Status: accepted
- Context: The generic `.along/` folder was prone to collision with third-party tools, and generic un-namespaced skills (like `dashboard`, `bump-version`, `sync-context`) collided in global agent environments (`~/.claude/skills/`, `~/.gemini/config/skills/`).
- Decision:
  1. Transition the product and protocol to **Along (`actdim-along`)** and **`ALONG-PROTOCOL v2.0.0`**.
  2. Store all project tracking and memory in an isolated **`.along/`** directory in target repositories.
  3. Require **`protocol: along`** in the YAML front-matter of all entity markdown files.
  4. Prefix all skills and slash commands with **`along-*`** (`along-init`, `along-update`, `along-dash`, `along-wrap-session`, etc.) and purge legacy un-namespaced skills during installation and update.
  5. Upgrade migration engine (`scripts/migrate_protocol.py`) to seamlessly detect legacy `.along/`, inject `protocol: along`, relocate files to `.along/`, and clean up empty `.along/` directories without touching foreign files.
- Consequences: Total isolation from third-party tools, zero namespace collision in global skill registries, backward-compatible automated migration path for existing projects.

## ADR-2026-08-27--mandatory-code-review-and-blast-radius-impact-gate - Mandatory Agentic Code Review & Blast Radius Impact Assessment Gate
- Date: 2026-08-27
- Status: accepted
- Context: Unchecked AI code modifications often introduce regression risks, silent broken callers, edge-case crashes, or unhandled nulls that accumulate unnoticed until runtime.
- Decision:
  1. Formalize a mandatory **Code Review & Blast Radius Assessment** gate in the ALONG-PROTOCOL and session wrap-up checklist.
  2. Mandate agents to inspect their own git diffs and trace blast radius across dependent modules using `code-review-graph` MCP tools (`build_or_update_graph_tool`, `get_impact_radius_tool`, `get_affected_flows_tool`) or AST analysis.
  3. Require verification of ADR conformance in `.along/DECISIONS.md`, null-safety, and edge-case handling.
  4. Document the code review findings and impact summary in the session log (`.along/SESSIONS/`).
- Consequences: Significantly reduced regression rate, improved long-term architectural health, and explicit accountability for multi-module impact.

## ADR-2026-08-27--universal-version-bumping-and-scripts-ecosystem - Universal Project Version Bumping & Repository Scripts Ecosystem (.along/scripts/)
- Date: 2026-08-27
- Status: accepted
- Context: `along-bump-version` was initially hardcoded for `actdim/along` internal development, failing when executed in external consumer repositories (Node, Python, Rust, .NET).
- Decision:
  1. Transform `/along-bump-version` (`along_bump_version.py`) into a universal release engine.
  2. Establish `.along/scripts/` convention in project memory directories for repo-tailored automation scripts.
  3. Support execution of custom `.along/scripts/bump_version.py` hooks with fallback to automatic stack detection (Node `package.json`, Python `pyproject.toml`, Rust `Cargo.toml`, .NET `*.csproj`, Along dev).
  4. Auto-synthesize `.along/scripts/bump_version.py` on first run for detected stacks, with diagnostic templates for custom environments.
- Consequences: Every project adopting Along gains automated, stack-agnostic version bumping and release orchestration out-of-the-box.

## ADR-2026-08-27--unified-along-wrap-commit-and-lifecycle-runners - Unified /along-wrap, Smart /along-commit, and Lifecycle Execution Suite (/along-build, /along-test, /along-dev)
- Date: 2026-08-27
- Status: accepted
- Context: Separate `along-wrap-session` and `along-wrap-stage` skills created redundant duplication and prompt bloat. Developers also needed safe pre-commit ASCII checks, automated Conventional Commit formatting, and project lifecycle runners (`build`, `test`, `dev`).
- Decision:
  1. Consolidate `along-wrap-session` and `along-wrap-stage` into a single canonical skill: **`/along-wrap`**.
  2. Implement **`/along-commit`** (`scripts/along_commit.py`) to enforce pre-commit typography checks, auto-link active `.along/` issues, and format Conventional Commits.
  3. Deploy non-destructive lifecycle suite (**`/along-build`**, **`/along-test`**, **`/along-dev`** via `scripts/along_exec.py`), utilizing `.along/scripts/` with `# Status: verified` vs `# Status: unconfigured` markers.
  4. Refine `along-bump-version` to update files on disk by default, committing only when `--commit` is explicitly passed.
- Consequences: Reduced skill token footprint, unified wrap mental model, and robust development lifecycle automation.

## ADR-2026-08-28--frontend-dynstruct-architecture-and-msgmesh-adapters - Frontend Architecture: Dynstruct Component Architecture, MessageMesh Integration, and NSwag Adapters
- Date: 2026-08-28
- Status: accepted
- Context: The web dashboard UI for Along required clear architectural guidelines for frontend components, state management, and backend communication. Ad-hoc React hooks, manual fetch calls, unstructured global variables, and loose `any` typing create boilerplate, high maintenance overhead, and obscure component communication.
- Decision:
  1. **Strict Dynstruct Component Architecture**: All UI components must use `@actdim/dynstruct` (`ComponentStruct`, `ComponentDef`, `useComponent`, MobX reactivity) and `@actdim/dynstruct-mui`. Avoid ad-hoc React hooks (`useState`, `useEffect`, `useMemo`), manual callback plumbing, or global `window` state storage.
  2. **Implicit Contextual Bus Integration**: The Message Mesh bus (`msgBus`) is created once and injected at the root via React context (`ComponentContextProvider`). Components access the bus implicitly via `c.msgBus` proxy, which provides built-in Dynstruct error handling, lifecycle management, and scoped messaging (`msgScope`, `msgBroker`).
  3. **Zero Manual API Channels & Fetch Handlers**: Do not manually write `MsgStruct` channel maps or manual `fetch` calls in `provide()`. All backend REST API clients are generated automatically from OpenAPI schemas via NSwag (`pnpm run generate:api`).
  4. **Dynamic Adapter Wiring via `@actdim/msgmesh/adapters`**:
     - Compute the channel prefix from the client literal type via `ToMsgChannelPrefix<'DashboardApiClient', 'API'>` (`API.DASHBOARD.`).
     - Dynamically map all client methods to typed message channels at compile-time via `ToMsgStruct<DashboardApiClient, DashboardChannelPrefix>`.
     - Register the client instance on the bus automatically at runtime using `getMsgChannelSelector(services)` and `registerAdapters(msgBus, adapters)`.
  5. **100% Strict Type Safety**: No `any` casting, no type assertions (`as ...`), and strict channel typing. All interaction points, emitted events, and subscriptions must be fully visible and traceable through component structs (`ComponentStruct<AppMsgStruct, ...>`).
- Consequences: Zero boilerplate, clean separation between UI components and backend transport, fully automated API client maintenance via NSwag, and transparent, declarative message routing with compile-time type safety.

## ADR-2026-08-30--llm-wiki-docs-architecture-and-singular-skills-refactoring - LLM-Wiki Knowledge Base Architecture in docs/, .archive/ Isolation & Singular Domain-First Skills Refactoring
- Date: 2026-08-30
- Status: Accepted
- Context:
  1. Previously, structured documentation was placed in `.along/KB/` and raw source notes often polluted documentation directories.
  2. Multi-part skill names like `along-sync-issues`, `along-sync-decisions`, and `along-bump-version` lacked uniform domain hierarchy and plural/singular consistency.
  3. LLM agents needed a token-efficient retrieval engine based on `nvk/llm-wiki` principles to query documentation snippets before reading full documents into context.
- Decision:
  1. **Top-Level `docs/` Knowledge Base**: Move all active project documentation and Wiki articles into top-level `docs/` with standard relative Markdown links (`[Title](./target.md)`).
  2. **Raw Source Isolation (`.archive/`)**: Move raw, unmanaged notes and source documents into a hidden `.archive/` directory so developers can inspect and safely delete them later without polluting active KB searches.
  3. **Singular Domain-First Skill Hierarchy**: Standardize all 3-part skill names to `along-<singular_entity>-<action>`:
     - `along-kb-sync` (single idempotent compiler/linter)
     - `along-kb-search` (token-efficient snippet retrieval)
     - `along-issue-sync`
     - `along-context-sync`
     - `along-decision-sync`
     - `along-history-sync`
     - `along-graph-check`
     - `along-dep-scan`
     - `along-version-bump`
  4. **Targeted Agent Fast Retrieval**: Protocol requires agents to query `along-kb-search` or `wiki_query` before reading full documentation files into context.
  5. **Strict Nearest Subproject & Submodule Localization**: When working in submodules, nested packages, or symlinked component libraries, all entity creation and updates (`ISSUES`, `SESSIONS`, `CONTEXT`, `DECISIONS`, `HISTORY`) MUST strictly occur in the **nearest `.along/`** corresponding to the modified files, preventing workspace root pollution.
- Consequences: Cleaner repository layout, universal Markdown rendering on GitHub/npm, reduced agent token usage via targeted retrieval, a consistent domain-first skill naming convention across all providers, and strict project boundary isolation for submodules and multi-package workspaces.

## ADR-2026-08-30--multi-agent-protocol-along-team-and-goal-integration - Multi-Agent Development Protocol (along-team), Sequential State Machine, Living Plan, and /goal Integration
- Date: 2026-08-30
- Status: accepted
- Context:
  1. Traditional multi-agent swarms (uncontrolled parallel agents or chat-room style agents) suffer from high token overhead, race conditions in workspace files, lost context across steps, and lack of deterministic verification.
  2. Developers need an autonomous, sequential multi-agent execution pipeline that decomposes complex engineering tasks into verifiable steps without requiring constant human micromanagement.
  3. Integration is needed with autonomous environment commands (such as Antigravity `/goal`) and skill-driven team execution (`/along-team`).
- Decision:
  1. **Adopt Sequential State Machine Protocol**: Base multi-agent development on a sequential, living-plan architecture: `Supervisor -> Research (Scout) -> Architect (Living Plan) -> Step Loop [Implementer -> Reviewer/Tester -> Reassess] -> Wrap`.
  2. **Role Primitives**:
     - `Supervisor`: Orchestration, acceptance criteria verification, routing.
     - `Researcher`: Read-only discovery via `invoke_subagent` (`TypeName: "research"`, `enable_write_tools: false`).
     - `Architect`: Dynamic Living Plan formulation (2 to 5 verifiable steps).
     - `Implementer`: Code execution in isolated workspace branch via `invoke_subagent` (`TypeName: "self"`).
     - `Reviewer`: Unified verification (tests runner, diff audit, blast radius, ADR compliance) via `invoke_subagent` (`TypeName: "self"`).
  3. **Adaptive Complexity Routing**:
     - `S-Size` (1-2 files, clear scope): Fast-path single-agent execution without spawning subagents.
     - `M-Size` (isolated feature): Fast loop (Scout -> Worker -> Reviewer).
     - `L / XL-Size` (complex architecture): Full Step-by-Step Living Plan protocol with Reassess cycles.
  4. **Targeted Feedback Loops & Bounded Retries**: Reviewer rejects are routed back to the minimal relevant stage (Implementer or Architect) with a strict cap of 2 retries per step before human escalation.
  5. **Deploy `/along-team` Skill**: Provide canonical `/along-team` skill across all agent runtimes and wire it with `/goal` semantics.
- Consequences: Eliminates parallel file race conditions, cuts token waste on simple tasks through adaptive routing, guarantees rigorous automated verification per step, and enables true autonomous goal execution.

## ADR-2026-08-31--session-scoped-blackboard-memory-and-role-contracts - Session-Scoped Blackboard Memory, Strict Multi-Agent Role Contracts, and Mandatory Architectural Rationale Standards
- Date: 2026-08-31
- Status: accepted
- Context:
  1. Decision #013 introduced multi-agent roles (`Supervisor`, `Scout`, `Architect`, `Implementer`, `Reviewer`), but lacked an explicit ephemeral memory storage model, causing in-flight data (AST findings, living plans, reviewer verdicts) to either clutter conversation context or leak across sessions.
  2. Relying on default LLM role naming without explicit boundary contracts, input/output schemas, and verification rubrics led to prompt drift, out-of-scope code changes, and sycophantic reviews.
  3. Repository documentation and skill definitions frequently documented *how* features work while omitting *why* specific patterns were chosen, what trade-offs were made, and what concrete benefits they provide.
- Decision:
  1. **Session-Scoped Blackboard Architecture**:
     - Store in-flight multi-agent coordination data in an isolated, task-bound ephemeral directory: `.along/.session/<issue-slug>/` (auto-ignored in `.gitignore`).
     - Standardize in-flight artifacts: `plan.md` (Living Plan), `scout_findings.json` (target symbols and constraints), `step_reviews/` (Reviewer verdicts per step), `blackboard.json` (shared in-session state and mocks).
     - **Lifecycle & Automated GC**: Allocate on session start -> Update during step loops -> Distill into `.along/SESSIONS/<YYYY>/<YYYY-MM-DD>--<slug>.md` -> Purge `.along/.session/<slug>/` completely during `/along-wrap`.
  2. **Context Pruning & Typed Handoff Gatekeeping**:
     - The Supervisor strictly strips raw search logs and tool output from the Scout, injecting only distilled facts (target files, constraints, AST symbols) into the Implementer prompt.
     - The Implementer passes only touched files, diff summary, and local test results to the Reviewer.
     - Point-to-point correction loops (`send_message`) must contain concrete failure details and actionable fixes, capped at 2 retries per step.
  3. **Strict Multi-Agent Role Contracts**:
     - Formulate explicit System Prompt Templates, Boundary Contracts (prohibited actions), Input Payloads, and Output Schemas for Scout, Implementer, and Reviewer in `skills/along-team/SKILL.md`.
     - Standardize a mandatory 5-point verification rubric for Reviewer (Automated Tests, Diff Scope, ADR Compliance, Error Handling, ASCII cleanliness).
  4. **Mandatory Architectural Rationale Standard ("Why & Value Proposition")**:
     - Institutionalize a core protocol rule across `AGENTS.md` and `docs/`: every architectural topic, skill, and feature documentation must explicitly explain *why* this architecture was selected, why naive alternatives fail, trade-offs made, and the concrete value proposition to developers.
- Consequences:
  - Eliminates state leakage and context token bloat across multi-agent runs.
  - Guarantees deterministic, reproducible subagent execution with zero out-of-scope edits.
  - Ensures clean repository hygiene with automatic temp file garbage collection upon stage wrap-up.
  - Elevates documentation quality to provide clear engineering rationale and user value across the entire codebase.


## ADR-2026-08-31--global-self-diagnostics-and-feedback-subsystem - Global Self-Diagnostics, PII Redaction, and Multi-Transport Feedback Engine
- Date: 2026-08-31
- Status: accepted
- Context: When Along tools or agent scripts encounter unexpected runtime errors or platform incompatibilities in user repositories, developers lack a centralized telemetry and diagnostic mechanism to capture and report these incidents without risking credential or PII leaks.
- Decision: 1. Implement global diagnostics store in user home directory (~/.along/diagnostics/) with structured incident JSON files and an auto-compiled REPORT.md. 2. Enforce strict automatic regex redaction for user home paths and authentication credentials. 3. Support three pluggable feedback transports: File export, Telegram Bot API, and REST Webhook. 4. Deploy /along-feedback skill and along_feedback.py CLI tool.
- Consequences: Enables reliable debugging and continuous protocol improvement while guaranteeing zero silent transmissions and preventing secret/PII leakage.

## ADR-2026-08-31--concurrency-projections-and-context-deprecation - Multi-Branch Concurrency, Derived Projections, Context Deprecation, and Mandatory Issue Anchoring
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

## ADR-2026-09-01--requirement-traceability-and-public-surface-gate - Requirement Traceability Matrix, Public Surface Discovery & Reviewer Coverage Gate
- Date: 2026-09-01
- Status: accepted
- Context: In multi-agent decomposition, when the Supervisor or Architect deconstructs complex user prompts into living plans, sub-requirements (e.g. updating mirrored tables in README.md as well as docs/) were occasionally de-scoped or lost, leading to documentation drift between public surfaces and internal knowledge bases.
- Decision:
  1. **Phase 0 Requirement Traceability Matrix**: Supervisor explicitly decomposes user prompts into atomic requirements (`REQ-1`, `REQ-2`, `REQ-3`).
  2. **Phase 2 Public Surface Discovery**: Architect greps for all mirrored occurrences of modified entities across public entry points (`README.md`, `AGENTS.md`, `docs/`, manifests) and maps each `REQ-N` to target files across all surfaces.
  3. **6-Point Reviewer Rubric**: Formalize an explicit **Requirement Coverage Gate** and **Public Surface Parity Gate** in the mandatory Reviewer rubric, failing any step that satisfies internal docs but omits mirrored public surfaces.
- Consequences: Guarantees 100% requirement fidelity from user prompt to final commit; eliminates drift between internal documentation and public repositories.

## ADR-2026-09-01--shared-engine-package - Shared Implementation Package for the Engines (scripts/alongkit/)
- Date: 2026-09-01
- Status: accepted
- Context: The twelve engines in `scripts/` (about 250 KB) had no shared module. `find_repo_root` existed in five copies that disagreed on what constitutes a repository root, front-matter parsing in four, `parse_semver` in two, and the pre-commit test and sanitizer gates in two each. `subprocess.run` was called at 25+ sites with no shared convention, which is why a single encoding defect (`[bug--subprocess-encoding-breaks-on-non-utf8-locale]`) was present in every engine and in the test suite at once. The demonstrated cost is `[bug--adr-retrieval-blind-to-slug-headers]`: the ADR header format changed in v2.2.0, was updated in the writer and the validator, and was missed in the reader, so ADR search returned zero results in every released version. Fixing such defects one file at a time multiplies the work and guarantees future divergence.
- Decision:
  1. **Package location**: `scripts/alongkit/`, a subpackage next to the engines rather than a top-level directory. Python places the running script's own directory on `sys.path`, and both installers copy `alongkit/` next to the engines, so `from alongkit import ...` resolves in a source checkout, in a flat `~/.along/bin/` file copy, and in an installed wheel, with no `sys.path` manipulation beyond one line per engine and no mandatory install step.
  2. **Module boundary**: one module per shared concern - `repo` (roots, state directory, engine resolution, directory walking), `frontmatter`, `entities` (vocabulary, canonical keys, ADR records), `proc`, `textio`, `markdown`, `typography`, `gates`, `semver`, `version`, `bootstrap`, `cli`. Inside the package a short name may repeat across modules (`frontmatter.parse`, `semver.parse`); the module qualifies it.
  3. **Single-definition rule, enforced**: no name may be defined at module level in two engines, and no engine may redefine a name the package owns. Two AST tests in `tests/test_alongkit.py` fail with the offending file and line otherwise. An engine that needs a shared helper aliases it (`parse_frontmatter = frontmatter.parse_tolerant`).
  4. **Packaging**: `pyproject.toml` (hatchling) declares the package, the `ruamel.yaml` runtime dependency, the `dash` extra for the dashboard stack, and the `along` console entry point, which delegates to the existing `along_exec.py` router rather than duplicating its dispatch table. Engine files are force-included one by one, asserted complete by a test, so the wheel cannot silently ship without them.
  5. **Compatibility**: the documented `python scripts/<engine>.py` invocation keeps working and is not deprecated here; rewriting the eighteen `SKILL.md` files onto the console entry point is tracked as `[bug--skill-commands-reference-missing-script-paths]`.
- Consequences: One place to fix each shared defect, and a test that fails when a copy reappears. The protocol version constant, the forbidden-character table, the ADR header format, and the subprocess conventions each have exactly one definition. Cost: engines carry a one-line `sys.path` insert, and the toolchain is no longer pure standard library (see the front-matter ADR below). Net effect on this change alone: 12 engines converted, about 240 duplicated lines removed, 4 latent defects fixed in passing (a missing `json` import that silenced the npm test gate, a stale version string reported in every bug report, an unparseable-file crash in the dashboard graph builder, and the `httpx2` typo in the dashboard test fallback).

## ADR-2026-09-01--frontmatter-on-ruamel-yaml - Front-matter on ruamel.yaml, with uv for Dependency Delivery
- Date: 2026-09-01
- Status: accepted
- Context: Front-matter was parsed and written by hand in four independent copies. All shared two defects that lost user data: a line without a colon was skipped, so a block sequence (`tags:` followed by indented `- item` lines) parsed to an empty string and the following full rewrite deleted its items; and the writer emitted `f"{key}: {value}"` with no quoting, so an ordinary title containing a colon produced a block that is not valid YAML. Six such files existed in this repository when this decision was taken, unreadable by PyYAML, `gray-matter`, and GitHub alike, including four milestones and two session logs. A separate finding: `decisions: [012]` was read as the integer 10 by PyYAML (YAML 1.1 octal) and as the string "012" by the hand-rolled parser, so no two readers agreed on the repository's own data. Writing a bespoke subset parser was considered and rejected: YAML is a widely implemented format, the front-matter is read by tools that are not Along, and a hand-rolled parser must be kept correct by tests forever for no gain.
- Decision:
  1. **`ruamel.yaml` in round-trip mode**, chosen over `pyyaml` because it preserves comments, key order, and quoting style. Measured on this repository: a no-op read-and-write is byte-identical for 123 of 123 entity files.
  2. **Reads are strict, edits are surgical**. `frontmatter.parse` raises on a block it cannot understand; `frontmatter.update` names individual keys and leaves every other line untouched; `frontmatter.render` is only for new files and re-parses its own output before returning it. `frontmatter.parse_tolerant` exists for read-only scanners that must not abort on one bad file, and it reports rather than silently reinterpreting.
  3. **A refusal is the correct outcome** for metadata that cannot be parsed: engines skip and report the file and line instead of rewriting it from a partial parse.
  4. **Dependency delivery via uv**, not vendoring: `pyproject.toml` is authoritative, `alongkit.bootstrap` mirrors the list for direct invocation and re-executes an engine once under `uv run` when the import fails, and a test asserts the two lists stay identical. `pixi` was considered and rejected as unnecessary for a pure-Python project.
  5. **Two deliberate deviations from PyYAML defaults**, both to keep existing consumers working: an ISO date stays a `YYYY-MM-DD` string rather than becoming a `datetime.date`, and an unset key reads as the empty string rather than None, because front-matter is text metadata and every caller does `fields.get(key, "")`.
- Consequences: The "zero external dependencies" claim for `along-kb-sync` is no longer true and has been corrected in `skills/along-kb-sync/SKILL.md` and `docs/topic--skills-reference.md`; the honest statement is one dependency, resolved automatically by uv. In exchange, the read-modify-write cycle over a user's files stops losing block sequences, comments, and key order, and a block that is not valid YAML is refused loudly instead of propagated. The six pre-existing invalid files were repaired as part of this change (one line each, net line count unchanged).

## ADR-2026-09-01--typography-rule-scope - Scope and Enforcement Mode of the ASCII Typography Rule
- Date: 2026-09-01
- Status: accepted
- Context: `scripts/sanitize_typography.py` performed a repository-wide read-modify-write over `**/*.md`, `*.py`, `*.sh`, `*.ps1`, `*.bat`, `*.json`, `*.yaml`, `*.yml`, `*.toml`, and ran unattended before every commit (`along_commit.py`) and every release (`along_version_bump.py`). It read each candidate with `errors="ignore"` and then overwrote the file with the decoded result, so any cp1251, latin-1, or UTF-16 file lost its undecodable bytes permanently, with no warning and no backup - a direct violation of the protocol's own "Zero Unintended Deletions" invariant, in the least supervised place in the toolchain. It wrote with `newline="\n"`, forcing LF onto the `.ps1` and `.bat` files that `.gitattributes` declares `eol=crlf`. It rewrote guillemets, typographic apostrophes, and NBSP inside arbitrary `.json` / `.yaml` / `.toml`, which corrupts a French or Russian resource bundle as a side effect of a commit. And its only caller-visible output was a printed count line that the commit engine detected change by grepping. The open question the fix had to settle was not how to write files safely but what the rule governs: banning non-ASCII typography in agent-authored prose is the point of the protocol, banning it in arbitrary user data is out of scope and harmful. See `[bug--typography-sanitizer-destroys-non-utf8-files]`.
- Decision:
  1. **Governed file classes**: the rule governs agent-authored prose and the source files whose comments, docstrings, and string literals agents write - `.md`, `.py`, `.sh`, `.ps1`, `.bat`. Structured data (`.json`, `.yaml`, `.yml`, `.toml`) is opt-in per run (`--include-data`), because those files carry product and user content as often as agent text. Localized resource directories (`locales/`, `locale/`, `i18n/`, `intl/`, `_locales/`, `lang/`, `translations/`) are never scanned in any mode: a guillemet in a translated string is content, not typography to repair.
  2. **Verify by default, rewrite only on request**: `check` is the default mode everywhere. The commit and release gates report what they found, name the file and line, and abort; they never rewrite. Rewriting an automated path is opted into per invocation with `--fix-typography`, and the standalone engine requires `--write`. An unattended tool that edits a user's files is the wrong default however careful its writes are.
  3. **Strict reads, faithful writes**: a file that is not valid UTF-8 is skipped, reported by path with the decode reason, and left byte-identical; `errors="ignore"` before a rewrite is banned outright. Existing line endings are preserved verbatim rather than normalized, which honors `.gitattributes` without parsing it. Writes go through `alongkit.textio` (atomic temp-and-replace).
  4. **Hidden directories are in scope**: the walk uses `repo.iter_files(include_hidden=True)` instead of `glob`, which never matches a leading dot. A byte order mark inside `.along/**` was previously invisible to the only tool meant to remove it. Every BOM strip is now reported by path; enforcement across hidden directories remains `[bug--quality-gates-skip-hidden-directories]`.
  5. **Structured results, not printed text**: `alongkit.sanitizer.Report` carries per-file replacement counts, line numbers, BOM removals, and skipped files, and serializes to JSON (`--json` on stdout, human output on stderr). No caller may parse the tool's printed output; a test fails if the old count line reappears in any engine.
  6. **Module boundary**: `alongkit.typography` keeps the character table and the pure string transformation; `alongkit.sanitizer` owns scope, file access, modes, and the report. Nothing that touches a file lives in the table module.
- Consequences: A commit in a repository containing a non-UTF8 file or a localized resource bundle can no longer corrupt it, and can no longer commit the corruption in the same command. The cost is that a repository with pre-existing banned characters now sees commits and releases fail until they are cleaned or `--fix-typography` is passed, which is the intended trade: a refusal the human sees beats a silent rewrite they do not. Exclusions are configurable per repository through `.alongsanitizeignore` or `--exclude`. `migrate_protocol.py` keeps rewriting, because a migration is an explicitly requested mutation, but now through the same strict-read implementation and over the whole character table rather than only two dash glyphs.

## ADR-2026-09-01--release-gates-before-mutations - Gates Precede Mutations, and a Release Is Transactional
- Date: 2026-09-01
- Status: accepted
- Context: `along_version_bump.py` bumped the version across every manifest, ran the sanitizer over the whole repository, flipped the matching milestone to `completed`, regenerated the dashboard, and only then ran the test suite - and only when `--commit` was passed, so `along_version_bump.py patch` shipped a version number no gate had ever inspected. A failing gate printed "Release aborted. Fix failing tests before releasing." and exited 1 over a tree that was already half-released, with no rollback of any kind. Three more defects sat in the same 60 lines: the run ended with `install.ps1 -Target all`, which deletes and recreates `~/.claude/rules` (destroying user-authored rules), recopies skill folders for four providers, and edits MCP configuration - captured, with the exit code ignored, so the success line printed even when the install failed; the milestone reconciliation used two unanchored `re.sub` calls and matched milestones by filename substring, so `status: open` in a target-issue table was rewritten and a bump to `1.5.0` claimed any file whose name contained those characters; and the release commit was staged with `git add -A`. The dashboard step invoked `--markdown`, a flag the dashboard has never accepted, and no return code was checked anywhere. See `[bug--release-engine-mutates-before-tests-and-reinstalls-globals]`.
- Decision:
  1. **Gates run on the untouched tree, unconditionally**: the repository's tests, the typography check (check mode), and the Markdown link check (`along_kb_sync.py --check --strict`, added as `gates.link_integrity_gate`) all run before the first byte is written, on every invocation regardless of `--commit`. `-n` / `--no-verify` is the single documented way past them, matching `along_commit.py`.
  2. **Mutations are transactional**: `alongkit.transaction.FileTransaction` snapshots a file's exact bytes, or its absence, before anything writes to it, and restores every one of them on failure, naming what it put back. Bytes rather than decoded text, so a rollback can restore a file the sanitizer would refuse to touch. The transaction closes at the git commit: past that point a rollback would discard committed work rather than repair anything. A mutation the engine cannot see - a project's own `.along/scripts/bump_version.py` writing its own paths - is recorded with `mark_unrestorable()` and named in the abort report, because a partial rollback the user is not told about is worse than none.
  3. **No global side effects from a version bump**: `sync_local_global_install` is deleted outright rather than gated behind a flag. Installing skills for the machine's providers is `/along-update` or the installer, invoked by a human who meant it. A test asserts the engine contains no installer literal and no reference to the user's home directory.
  4. **Entity edits go through the front-matter writer**: milestone reconciliation uses `frontmatter.update` and matches on the milestone's own `slug` field, requiring the version to appear as a whole hyphen-separated component (`v3.0.0-...`), so `v1.4.30` is not matched by a release of `1.4.3`. Same fix already applied to `issue done` in `[bug--issue-done-corrupts-status-and-drops-completed]`.
  5. **A release finishes what it claims**: it stages exactly the paths it wrote (never `git add -A`), commits, creates the annotated tag `v<version>`, and prepends a `## v<version>` section to `CHANGELOG.md` listing the commit subjects git recorded since the previous tag. A tag or push failure is an error and a non-zero exit, not a warning - the commit exists locally and the remote does not have it, which is not a successful release.
  6. **The dead dashboard regeneration is removed** rather than repaired: the flag it passed does not exist, and `.along/DASHBOARD.md` is a derived projection whose committed status is itself under review in `[debt--generated-dashboard-artifact-committed]`. Every remaining child process in the engine checks its return code.
- Consequences: A failed release leaves the working tree byte-identical, which is now asserted by regression tests (`tests/test_release_engine.py`), including the abort path and the rollback report. A version bump can no longer rewrite machine-global agent configuration, and can no longer sweep unrelated work into a release commit. The costs are real and accepted: the release path now depends on the Knowledge Base engine for its link gate (absent engine passes, so a consumer repository is unaffected), a repository with broken relative links cannot release until they are fixed or `--no-verify` is passed, and a project with a custom `bump_version.py` hook gets a reported-but-not-restored mutation instead of a silent assumption that the tree is clean.

## ADR-2026-09-01--migration-never-deletes-a-destination - A Migration Merges, Backs Up, and Defaults to a Dry Run
- Date: 2026-09-01
- Status: accepted
- Context: `migrate_protocol.py` moved legacy `.agents/` content into `.along/` with `os.remove(dst)` followed by `shutil.move(src, dst)`, and repeated the pattern per file when merging directories. A repository holding both a populated `.agents/` and a populated `.along/` - a partial migration, or two developers migrating on different branches - therefore lost the newer `DECISIONS.md`, `HISTORY.md`, and issue files in favour of the stale legacy copies. Both `DECISIONS.md` and `HISTORY.md` are append-only by protocol, and `.gitattributes` already declares `merge=union` for exactly the case the engine resolved by deletion, so the loss was irreversible. Four aggravating factors surrounded it: no `--dry-run`, so the plan could not be seen before it executed; no backup of any kind; `errors="ignore"` on the markdown reads that preceded a rewrite, which deleted every undecodable byte of a non-UTF8 file; and no migration state, so all eight steps re-ran on every invocation and idempotency held only by accident of each step's own guards. The engine was also invoked implicitly, by `install.ps1` / `install.sh` against `$PSScriptRoot` and by the test suite against `REPO_ROOT`, so installing or running tests could rewrite a working tree nobody had pointed at it. See `[bug--migration-deletes-destination-without-backup]`.
- Decision:
  1. **The destination is never deleted**: collisions are resolved by file class, and every outcome keeps both bodies on disk. Append-only files (`DECISIONS.md`, `HISTORY.md`) are union-merged, deduplicated, destination order first - section-wise for a file built from `## ` headings, line-wise otherwise. Derived projections (`ISSUES.md`, `INDEX.md`, `DASHBOARD.md`, `dashboard.html`) keep the destination and discard the legacy copy, because they carry nothing their sources do not; the report says to recompile them. Everything else keeps the destination and preserves the legacy copy beside it as `<name>.legacy.md`, reported as a resolved collision rather than applied silently.
  2. **A durable backup precedes the first modification**: `.along/` and `.agents/` are copied to `.along/.migration-backup/<timestamp>/` before anything existing is changed, and the path is printed. This is deliberately not `alongkit.transaction`, which the release engine uses: an in-memory snapshot dies with the process, and a migration is meant to be run, inspected, and re-run. The backup directory carries its own `.gitignore` containing `*`, so it stays out of history without editing the user's `.gitignore`.
  3. **Dry run is the default for any caller that is not a human at a terminal**: without `--apply`, a run with no TTY prints the full planned operation list and writes nothing. `--apply` is mandatory from a script, `--dry-run` forces the plan even interactively. The two paths that used to migrate unasked are closed at the source as well: `install.ps1` / `install.sh` migrate only with `-Migrate` / `--migrate` and otherwise print how to do it, and the tests pass `--apply` explicitly against throwaway fixtures.
  4. **Strict reads**: `errors="ignore"` is gone from the engine. A file that fails to decode is skipped, listed in the report with the decode reason, and left byte-identical - the same rule the sanitizer adopted in ADR-2026-09-01--typography-rule-scope.
  5. **Migration state is persisted**: `.along/.protocol-version` records the version the repository was last migrated to, written last so a run that died halfway is not recorded as complete. A second run reports "already at v<version>; nothing to do"; `--force` re-runs every step.
  6. **One implementation, no raw file operations in the engine**: the collision policy, the backup, the plan and every mutation live in `alongkit.migration`. `migrate_protocol.py` calls no `shutil.move`, `shutil.rmtree`, `os.remove` or `os.rename` of its own, and a test fails if one reappears. Both modes end with the same report: operations grouped by kind, collisions and their resolution, skipped files, and the backup path.
- Consequences: The engine whose job is to protect the migration path can no longer destroy the memory it migrates, and `tests/test_migration.py` asserts it on a fixture holding both directories at once. The plan is inspectable before execution, and the pre-migration state remains on disk afterwards. The costs are accepted: a tool invoking the engine must now say `--apply` or get a plan (`along_update.py` passes the flag matching its own `--dry-run`), an installed repository is no longer migrated as a side effect and the user must run one command, a preserved `<name>.legacy.md` leaves a file the user has to reconcile by hand rather than a silent choice, and each applying run leaves a timestamped backup directory that nobody deletes automatically.

## ADR-2026-09-01--installers-never-delete-what-they-did-not-write - The Installers Copy, an Engine Decides, and a Manifest Remembers
- Date: 2026-09-01
- Status: accepted
- Context: The two installers were the protocol's own reference implementation and violated four of its rules at once. `install.ps1` opened its rule-pack step with `Remove-Item -Recurse -Force ~/.claude/rules`, so every install destroyed whatever the user had written under that directory - and the release engine ran an install unasked at the end of every version bump. The two scripts had drifted: `install.sh` did not install `rules/` at all, and the parity test did not notice because it compared skill folder NAMES rather than artifacts. Both carried a 24-line Python program inside a here-string passed to `python -c`, the exact pattern `AGENTS.md` forbids. MCP registration wrote `code-review-graph` into five files (`~/.claude.json`, plus a `mcp_config.json` in four provider homes) and printed a success line for each, though only the first is read by anything. The `mklink /J` fallback was double-quoted (`""C:\path""`), which works only while no path contains a space - the case the fallback exists to handle. And an install had no record of itself: no version, no file list, no way to uninstall. See `[bug--installer-parity-and-destructive-rules-overwrite]`.
- Decision:
  1. **The installers copy; every decision is an engine.** `alongkit.install` holds the installed layout, the manifest, and the per-provider MCP contracts. `scripts/configure_mcp.py` and `scripts/install_manifest.py` are the command lines over it, invoked with arguments. Zero inline `python -c` remains in either installer, and a test over their source (comments excluded, because the comments quote what was removed) fails if one comes back.
  2. **One description of the layout, both installers measured against it.** `install.planned_files(source, homes, providers)` derives every path an install writes. `tests/test_installers.py` runs each real installer against a throwaway checkout, into homes under `tempfile`, and asserts that what is on disk equals that plan exactly - in both directions. Parity is therefore a property of the artifacts, not of a probe list, and each installer is correct on its own rather than merely equal to the other.
  3. **A manifest replaces the delete.** `~/.along/install-manifest.json` records the version, the target homes, and every file the install wrote with a content hash. The next install removes, by name, only files the previous install wrote and this one no longer ships, scoped to the providers of this run - installing Claude alone must not uninstall Codex. Nothing else in a provider home is ever a candidate for removal, so a user's own rules survive. `-Uninstall` / `--uninstall` reads the same record and removes exactly it, leaving `~/.along/config.json`, user files, and provider configuration alone.
  4. **A link install is recorded as a link.** `os.path.islink` reports False for a Windows junction, which is what the symlink fallback creates (`mklink /J` needs no elevation). Recording the files behind it would make an uninstall delete the source checkout through the link, so `install.is_link` also tests the reparse-point attribute, the link itself is what the manifest stores, and removal uses `os.rmdir` rather than anything that follows the link.
  5. **MCP is registered only where the contract is verified, and a file that does not parse is left alone.** Claude Code's `mcpServers` map in `~/.claude.json` is written. Codex, OpenCode and Antigravity are reported with their real configuration path and the snippet to add, and are written only under `--include-unverified-mcp`. The four inert `mcp_config.json` writes are gone, as are the success lines that accompanied them. On a JSON parse failure the previous code started from `{}` and rewrote the file, which could have replaced a user's entire `~/.claude.json`; it now refuses and says why.
  6. **Every root is overridable** (`--along-home`, `--claude-home`, ...), which is what makes an end-to-end installer test possible without touching the developer's own home, and the junction fix is proven on a fixture path that contains a space.
- Consequences: An install is now inspectable (`install_manifest.py show`), reversible, and non-destructive, and the two installers cannot silently diverge again. The costs are accepted: a full install now depends on Python for the manifest and MCP steps (the file copying still works without it, with a printed note), three of the four providers get no MCP registration by default until their contract is confirmed - honest but less convenient than the previous false success - and an install that ran before this change has no manifest, so its first pruning pass has nothing to compare against and superseded files from earlier versions stay until the next install after this one.
