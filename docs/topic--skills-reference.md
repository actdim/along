---
protocol: along
protocol_version: "2.2.6"
slug: topic--skills-reference
title: Skills & Slash Commands Technical Reference
type: topic
created: 2026-08-30
updated: 2026-09-01
tags: [skills, commands, reference, runners, lifecycle, automation, multi-agent]
---

# Skills & Slash Commands Technical Reference

Along provides an integrated suite of **18 singular automation skills** operating across Claude Code, OpenAI Codex, OpenCode, and Google Antigravity.

Each skill is built on a domain-first naming pattern (`along-<entity>-<action>`), guarantees clean ASCII output, operates on strongly typed repository entities, and can be invoked either explicitly via slash commands/CLI or automatically via semantic intent recognition.

---

## Skills Ecosystem & Workflow Phases

```mermaid
flowchart TD
    subgraph Phase1["1. Bootstrap & Protocol"]
        INIT["along-init"]
        UPDATE["along-update"]
        BUMP["along-version-bump"]
    end

    subgraph Phase2["2. Planning & Multi-Agent"]
        TEAM["along-team"]
        ISSUE_SYNC["along-issue-sync"]
        DEC_SYNC["along-decision-sync"]
    end

    subgraph Phase3["3. Lifecycle Runners"]
        BUILD["along-build"]
        TEST["along-test"]
        DEV["along-dev"]
    end

    subgraph Phase4["4. Quality & Code Graph"]
        COMMIT["along-commit"]
        GRAPH["along-graph-check"]
        DEP["along-dep-scan"]
    end

    subgraph Phase5["5. LLM-Wiki Intelligence"]
        KB_SYNC["along-kb-sync"]
        KB_SEARCH["along-kb-search"]
    end

    subgraph Phase6["6. Analytics & Wrap"]
        DASH["along-dash"]
        HIST_SYNC["along-history-sync"]
        FEEDBACK["along-feedback"]
        WRAP["along-wrap"]
    end

    INIT --> TEAM
    TEAM --> BUILD & TEST & DEV
    TEST --> GRAPH & COMMIT
    COMMIT --> KB_SYNC & KB_SEARCH
    KB_SYNC --> DASH & WRAP
```

---

## 1. Bootstrap & Repository Protocol Management

### `along-init`
- **What it is**: The foundation bootstrapping engine for Along in any repository. Scaffolds or refreshes root `AGENTS.md` (carrying the managed protocol block), `CLAUDE.md`, `.gitattributes` (with `merge=union`), and the `.along/` directory skeleton (`ISSUES/`, `DECISIONS.md`, `MILESTONES/`, `RISKS/`, `SPIKES/`, `CHECKLISTS/`, `SESSIONS/`, `docs/`).
- **Architectural Rationale**:
  - *Idempotent Managed Block*: Never overwrites custom human developer instructions in `AGENTS.md`; only refreshes the block between `<!-- BEGIN ALONG-PROTOCOL ... -->` and `<!-- END ALONG-PROTOCOL -->`.
  - *Non-Destructive Initialization*: Creates directories and template files only if missing, preserving existing project history.
- **Invocation Triggers**:
  - *Explicit*: `/along-init`, `install.ps1`, `install.sh`.
  - *Semantic / Automatic*: Triggered when an agent detects an uninitialized repository, missing `AGENTS.md`, or a user prompt like *"Set up Along in this repo"*, *"Initialize agent instructions"*.
- **Entities Operated On**: `AGENTS.md`, `CLAUDE.md`, `.gitattributes`, `.along/ISSUES/`, `.along/DECISIONS.md`, `docs/`.
- **Ecosystem Chaining**: Followed immediately by `/along-kb-sync` (to ingest `README.md`) and `/along-dep-scan`.

---

### `along-update`
- **What it is**: Automated protocol and skill synchronizer. Checks and pulls latest Along skills, migrations, and protocol definitions across user home directories (`~/.claude`, `~/.codex`, `~/.gemini`) and local repositories.
- **Architectural Rationale**:
  - Eliminates skill drift across multiple developer machines.
  - Automatically executes retroactive migration scripts (`scripts/migrate_protocol.py`) to upgrade legacy front-matter schemas and directory layouts without data loss.
- **Invocation Triggers**:
  - *Explicit*: `/along-update`, `python scripts/along_update.py`.
  - *Semantic / Automatic*: Triggered on protocol version mismatch, outdated skills warnings, or prompts like *"Upgrade Along protocol"*, *"Update agents"*.
- **Entities Operated On**: Global skill folders (`~/.gemini/config/skills/along-*`), target repository `AGENTS.md`, `scripts/`.
- **Ecosystem Chaining**: Runs `migrate_protocol.py` and triggers `/along-kb-sync --strict` to validate repository link integrity after updates.

---

### `along-version-bump`
- **What it is**: Universal multi-stack semantic version bumper and release orchestrator. Updates project versions across Node (`package.json`), Python (`pyproject.toml`), Rust (`Cargo.toml`), .NET (`*.csproj`), or Along protocol files.
- **Architectural Rationale**:
  - *Stack-Agnostic Hook Architecture*: Executes repository-specific hooks in `.along/scripts/bump_version.py` with automatic fallback to stack auto-detection.
  - *Pre-Release Quality Gate*: Runs automated test suites and ASCII cleanliness checks before allowing a version bump.
- **Invocation Triggers**:
  - *Explicit*: `/along-version-bump [patch|minor|major|<version>] [-c|--commit] [-p|--push]`, `python scripts/along_version_bump.py`.
  - *Semantic / Automatic*: Triggered when preparing a release, completing a milestone sprint, or prompted with *"Release version 2.3.0"*, *"Bump patch version"*.
- **Entities Operated On**: `package.json`, `pyproject.toml`, `Cargo.toml`, `*.csproj`, `AGENTS.md`, `.along/HISTORY.md`.
- **Ecosystem Chaining**: Chains with `/along-test` for pre-release validation and `/along-commit` for release tag commits.

---

## 2. Orchestration, Planning & Multi-Agent Teams

### `along-team`
- **What it is**: Sequential multi-agent development engine and living plan orchestrator. Replaces chaotic chat rooms with a deterministic state machine: `Supervisor -> Scout (Research) -> Architect (Living Plan) -> Step Loop [Implementer -> Reviewer/Tester -> Reassess] -> Wrap`.
- **Architectural Rationale**:
  - *Context Pruning Gatekeeping*: The Supervisor strips raw tool outputs from the Scout, injecting only distilled facts into the Implementer to prevent prompt saturation.
  - *Independent Gatekeeper Review*: Reviewer evaluates code in an isolated subagent context against the strict 5-point verification rubric (Zero-byte check, unit tests, diff scope, AST blast radius, clean ASCII).
  - *Adaptive Complexity Routing*: Fast-paths S-size tasks (1-2 files) without subagents; uses full state machine only for M/L/XL tasks.
- **Invocation Triggers**:
  - *Explicit*: `/along-team <slug>`, `/goal <task>`.
  - *Semantic / Automatic*: Triggered automatically for multi-file feature requests, complex refactorings, or prompts like *"Implement this feature with the agent team"*.
- **Entities Operated On**: `.along/ISSUES/<type>--<slug>.md`, `.along/.session/<slug>/` (ephemeral blackboard: `plan.md`, `scout_findings.json`, `step_reviews/`), `docs/`.
- **Ecosystem Chaining**: Uses `along-build`, `along-test`, `along-graph-check` during step loops, and finishes via `along-wrap`.

---

### `along-issue-sync`
- **What it is**: Idempotent synchronization engine that reconciles atomic issue files (`.along/ISSUES/*.md`, `.along/ISSUES/done/*.md`) into the compact active issue board projection (`.along/ISSUES.md`).
- **Architectural Rationale**:
  - *Zero-Manual-Merge Principle*: Because `ISSUES.md` is a compiled projection, git merge conflicts are resolved automatically by running `along-issue-sync` rather than manually resolving diffs.
- **Invocation Triggers**:
  - *Explicit*: `/along-issue-sync`, `python scripts/along_exec.py issue sync`.
  - *Semantic / Automatic*: Triggered during `/along-wrap`, when an issue changes status, or during post-git-merge reconciliation.
- **Entities Operated On**: `.along/ISSUES/*.md`, `.along/ISSUES/done/*.md`, `.along/ISSUES.md`.
- **Ecosystem Chaining**: Feeds data into `along-dash` and `along-wrap`.

---

### `along-decision-sync`
- **What it is**: Architectural Decision Record (ADR) recorder. Appends structured architectural decisions with decentralized slug headers (`## ADR-YYYY-MM-DD--<slug>`) into `.along/DECISIONS.md`.
- **Architectural Rationale**:
  - *Decentralized Slug Headers*: Prevents merge collisions across concurrent branches compared to sequential integer numbering (`#012`).
  - *Append-Only Invariance*: Old decisions are never deleted or rewritten; when superseded, they are marked `superseded by ADR-YYYY-MM-DD--<slug>`.
- **Invocation Triggers**:
  - *Explicit*: `/along-decision-sync`, `python scripts/along_exec.py decision append`.
  - *Semantic / Automatic*: Triggered whenever a non-trivial architectural choice, library selection, or database schema design is confirmed during a session or spike.
- **Entities Operated On**: `.along/DECISIONS.md`.
- **Ecosystem Chaining**: Governs Reviewer checks in `along-team` and informs documentation updates in `along-kb-sync`.

---

## 3. Development & Lifecycle Execution Runners

### `along-build`
- **What it is**: Universal build runner. Executes repository build lifecycle via `.along/scripts/build.py` or auto-detected package runners (`npm run build`, `cargo build`, `dotnet build`, `python -m build`).
- **Architectural Rationale**:
  - *Non-Destructive Standardized Interface*: AI agents execute a single unified command (`along-build`) across any programming language or technology stack without needing custom per-repo prompt tuning.
- **Invocation Triggers**:
  - *Explicit*: `/along-build`, `python scripts/along_exec.py build`.
  - *Semantic / Automatic*: Triggered after code edits, before pre-commit checks, or when the user prompts *"Build the project"*.
- **Entities Operated On**: `.along/scripts/build.py`, build output targets (`dist/`, `build/`, `bin/`).
- **Ecosystem Chaining**: Prerequisite for `along-test` and `along-dash` UI builds.

---

### `along-test`
- **What it is**: Universal automated test runner with quiet flags (`pytest -q`, `npm test`, `cargo test -q`, `dotnet test -v q`).
- **Architectural Rationale**:
  - *Token Hygiene via Quiet Flags*: Suppresses massive verbose test logs in agent prompts, emitting clean summary counts (pass/fail) to conserve context budget.
- **Invocation Triggers**:
  - *Explicit*: `/along-test`, `python scripts/along_exec.py test`.
  - *Semantic / Automatic*: Triggered during every Reviewer step in `along-team`, before pre-commit in `along-commit`, and during `/along-wrap`.
- **Entities Operated On**: `.along/scripts/test.py`, test suites (`tests/`, `src/**/*.test.ts`).
- **Ecosystem Chaining**: Core quality gate for `along-team`, `along-commit`, and `along-version-bump`.

---

### `along-dev`
- **What it is**: Development server runner. Launches local dev servers or debug runners (`npm run dev`, `cargo run`, `dotnet run`, `python main.py`).
- **Architectural Rationale**:
  - Provides a single standardized hook (`.along/scripts/dev.py`) for background daemon execution.
- **Invocation Triggers**:
  - *Explicit*: `/along-dev`, `python scripts/along_exec.py dev`.
  - *Semantic / Automatic*: Triggered when the user requests *"Start local dev server"*, *"Run application locally"*.
- **Entities Operated On**: `.along/scripts/dev.py`.
- **Ecosystem Chaining**: Pairs with `along-dash` for local interactive debugging.

---

## 4. Quality Gates, Code Graph & Commit Integrity

### `along-commit`
- **What it is**: Smart, ASCII-clean Conventional Committer. Validates typography, binds commit messages to active `.along/` issues, and creates clean Git commits.
- **Architectural Rationale**:
  - *Typography & Non-ASCII Gate*: Scans staged files and commit messages to block forbidden typographic characters (em-dash, smart curly quotes, non-breaking spaces) that corrupt Windows shell execution or AST parsers.
  - *Issue Traceability*: Enforces issue slug references (`(refs #<slug>)` or `[<slug>]`) for 100% auditability.
- **Invocation Triggers**:
  - *Explicit*: `/along-commit -i <slug> -m "<message>"`, `python scripts/along_commit.py`.
  - *Semantic / Automatic*: Triggered when completing a task or when prompted with *"Commit changes"*.
- **Entities Operated On**: Git staging index, `.along/ISSUES/`, active commit logs.
- **Ecosystem Chaining**: Precedes `/along-wrap`.

---

### `along-graph-check`
- **What it is**: AST call graph and blast radius inspection engine. Uses `code-review-graph` MCP tools to map impacted functions, downstream callers, and interface breaks.
- **Architectural Rationale**:
  - *Deterministic Blast Radius*: Prevents silent regression bugs by identifying all dependent callers across the codebase before code is merged.
  - *Graph-Ignore Filtering*: Enforces `.code-review-graph-ignore` to exclude `node_modules` and vendor directories, preventing graph database ballooning.
- **Invocation Triggers**:
  - *Explicit*: `/along-graph-check`, `python scripts/along_graph_check.py`.
  - *Semantic / Automatic*: Triggered during Phase 4 (Reviewer) in `along-team` and before session wrap-up for non-trivial refactorings.
- **Entities Operated On**: `.code-review-graph-ignore`, AST symbol database.
- **Ecosystem Chaining**: Maps identified AST symbols directly into `along-kb-search` for Knowledge Base synchronization.

---

### `along-dep-scan`
- **What it is**: Hierarchical multi-project and submodule dependency scanner. Scans package manifests (`package.json`, `pyproject.toml`, `Cargo.toml`, `*.csproj`), submodules, and symlinks for declared AI instructions and vendor rules.
- **Architectural Rationale**:
  - Extracts subproject constraints and vendor AI rules into `docs/topic--dependencies.md`, giving agents unified visibility into third-party constraints without manual file hunting.
- **Invocation Triggers**:
  - *Explicit*: `/along-dep-scan`, `python scripts/along_dep_scan.py`.
  - *Semantic / Automatic*: Triggered during `/along-init`, after dependency updates, or when adding a new Git submodule.
- **Entities Operated On**: `package.json`, `pyproject.toml`, `Cargo.toml`, `*.csproj`, `docs/topic--dependencies.md`.
- **Ecosystem Chaining**: Feeds architectural constraints into `docs/topic--dependencies.md` and `along-kb-sync`.

---

## 5. Knowledge Base & LLM-Wiki Intelligence

### `along-kb-sync`
- **What it is**: Idempotent LLM-Wiki compiler, inbound link rewriter, and link integrity gate for `docs/`.
- **Architectural Rationale**:
  - *LLM-Wiki Paradigm*: Implements Andrej Karpathy's LLM-Wiki architecture in Python with a single runtime dependency (`ruamel.yaml`, for front-matter), resolved automatically by `uv`.
  - *Inbound Link Rewriter*: Recursively scans all Markdown files in the monorepo and rewrites legacy internal paths (`.along/KB/...`) to standard relative `docs/` paths.
  - *Link Integrity Gate*: In `--strict` mode, validates that every relative Markdown link physically resolves to an existing file on disk.
  - *Raw Source Archival*: Automatically relocates ingested raw notes, chat dumps, and scratch files to `.archive/`, excluding them from active search indices.
- **Invocation Triggers**:
  - *Explicit*: `/along-kb-sync [--strict]`, `python scripts/along_kb_sync.py`.
  - *Semantic / Automatic*: Triggered during `/along-wrap`, after modifying documentation in `docs/`, or during protocol migration.
- **Entities Operated On**: `docs/*.md`, `docs/INDEX.md`, `.archive/`, all repository Markdown files.
- **Ecosystem Chaining**: Compiles the Knowledge Base queried by `along-kb-search` and visualized by `along-dash`.

---

### `along-kb-search`
- **What it is**: Ultra-fast, token-efficient multi-scope search engine across Knowledge Base (`docs/`) and living project memory (`ISSUES/`, `DECISIONS.md`, `MILESTONES/`, `RISKS/`, `SESSIONS/`).
- **Architectural Rationale**:
  - *95-98% Token Reduction*: Instead of reading whole multi-kilobyte documents into prompt context, retrieves concise ~200-character snippet windows in under 100 tokens.
  - *Multi-Tier Relevance Scoring*: Ranks results using weighted heuristics (`Title: +10`, `Tags: +5`, `Body: +1`) for instant pinpoint accuracy.
- **Invocation Triggers**:
  - *Explicit*: `/along-kb-search "<query>" [--category <cat>]`, `python scripts/along_kb_search.py`.
  - *Semantic / Automatic*: Mandatory first step for agents when researching domain architecture, investigating existing decisions, or mapping blast radius.
- **Entities Operated On**: `docs/`, `.along/ISSUES/`, `.along/DECISIONS.md`, `.along/MILESTONES/`, `.along/RISKS/`, `.along/SPIKES/`, `.along/SESSIONS/`.
- **Ecosystem Chaining**: Used by Scout and Supervisor in `along-team` during Phase 1 (Research).

---

## 6. Visual Analytics, History & Diagnostics

### `along-dash`
- **What it is**: Multi-mode executive dashboard and interactive Cytoscape DAG visualizer. Serves a FastAPI REST API and Server-Sent Events (SSE) stream with a modern reactive UI.
- **Architectural Rationale**:
  - *Autonomous Multi-Mode Architecture*: Runs in 4 decoupled modes via `scripts/along_dash.py`: CLI Mode, Interactive Web Mode (`http://127.0.0.1:8765`), Static HTML Export, and Markdown Dashboard Report (`.along/DASHBOARD.md`).
  - *Zero Setup Overhead*: Uses PEP 723 inline script metadata (`# /// script ...`) for instant zero-config execution.
- **Invocation Triggers**:
  - *Explicit*: `/along-dash [-w|--web] [-c|--cli] [-e|--export]`, `python scripts/along_dash.py`.
  - *Semantic / Automatic*: Triggered when the user asks for a project status overview, dependency visualization, or sprint progress report.
- **Entities Operated On**: `.along/`, `docs/`, `.along/DASHBOARD.md`.
- **Ecosystem Chaining**: Visualizes the entire entity DAG created by `along-team`, `along-issue-sync`, and `along-kb-sync`.

---

### `along-history-sync`
- **What it is**: Git history reconstruction engine. Reconciles `.along/` entities, closed issues, milestones, and session journals from historical Git commits, tags, and pull requests.
- **Architectural Rationale**:
  - Enables legacy repositories adopting Along to immediately gain full project memory and completed issue archives without manual retrospective data entry.
- **Invocation Triggers**:
  - *Explicit*: `/along-history-sync`, `python scripts/along_history_sync.py`.
  - *Semantic / Automatic*: Triggered during initial onboarding on existing git repositories or after major branch rebases.
- **Entities Operated On**: Git commit log, `.along/ISSUES/done/`, `.along/SESSIONS/`, `.along/HISTORY.md`.
- **Ecosystem Chaining**: Reconstructs historical data visualized in `along-dash`.

---

### `along-feedback`
- **What it is**: Self-diagnostics and incident reporting subsystem. Collects sanitized diagnostic logs, redacts PII and credentials, and dispatches feedback via Telegram, Webhook, or File export.
- **Architectural Rationale**:
  - *Zero-Leak Redaction*: Automatic regex-based redaction of user home paths, tokens, and credentials guarantees that sensitive data is never transmitted.
  - *Pluggable Transports*: Supports offline file export, direct Telegram bot notifications, or custom webhook endpoints.
- **Invocation Triggers**:
  - *Explicit*: `/along-feedback [--export|--send]`, `python scripts/along_feedback.py`.
  - *Semantic / Automatic*: Triggered when an Along internal script encounters unhandled exceptions or when prompted with *"Report bug in Along"*.
- **Entities Operated On**: `~/.along/diagnostics/incidents/`, `~/.along/diagnostics/REPORT.md`.
- **Ecosystem Chaining**: Provides operational telemetry and continuous improvement for the Along protocol.

---

### `along-wrap`
- **What it is**: Unified session and stage wrap-up orchestrator. Executes the mandatory completion checklist: runs tests, checks documentation blast radius, moves finished issues to `done/`, reconciles `ISSUES.md`, appends to `HISTORY.md`, and purges session blackboards.
- **Architectural Rationale**:
  - *Consolidated Lifecycle*: Eliminates fragmentation between session wrap-up and stage wrap-up, providing a single deterministic checklist.
  - *Automated Garbage Collection*: Completely cleans up ephemeral blackboard directories (`.along/.session/<slug>/`), ensuring zero leftover state files.
- **Invocation Triggers**:
  - *Explicit*: `/along-wrap`, `along-wrap`.
  - *Semantic / Automatic*: Triggered whenever a developer says *"I'm done for today"*, *"Wrap up session"*, or upon completing all steps in an issue.
- **Entities Operated On**: `.along/ISSUES/`, `.along/ISSUES/done/`, `.along/ISSUES.md`, `.along/SESSIONS/`, `.along/HISTORY.md`, `.along/.session/`.
- **Ecosystem Chaining**: Finalizes work executed by `along-team` and triggers `along-kb-sync` and `along-issue-sync`.
