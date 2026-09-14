---
protocol: along
protocol_version: "3.1.0"
slug: cli-reference
title: Along CLI Command Reference
type: topic
curated: true
created: 2026-09-14
updated: 2026-09-14
tags: [cli-reference]
---

---
title: Along CLI Command Reference
type: topic
tags: [cli, commands, router, lifecycle, tools, reference]
---

# Along CLI Command Reference

This document provides the canonical command-line interface reference for the `along` toolchain.

The Along CLI acts as the unified command router for human developers, terminal scripts, CI/CD pipelines, and autonomous AI agents. It guarantees identical execution semantics whether invoked as a globally installed console script, via Python directly in a repository checkout, or through a shared global installation.

---

## 1. Invocation Architecture & Paths

The CLI is routed through `scripts/along_exec.py` backed by the shared `alongkit` engine library. It automatically ensures runtime dependencies (such as `ruamel.yaml`) via `uv run` fallback if they are missing in the active interpreter.

```text
Invocation Paths:
  1. Canonical Console Script:   along <command> [subcommand] [options...]
  2. Local Repository Checkout: python scripts/along_exec.py <command> [subcommand] [options...]
  3. Global User Installation:   python ~/.along/bin/along_exec.py <command> [subcommand] [options...]
```

General help and command listing are accessible via:
```bash
along --help
along <command> --help
```

---

## 2. Project Lifecycle Hooks

Lifecycle commands provide a uniform execution contract across any programming language or build stack. They execute repository-specific hooks in `.along/scripts/` when present, or automatically detect the underlying project runner.

### `along build`
Executes the project build lifecycle hook.
- **Engine Script**: `.along/scripts/build.py`
- **Auto-Detection Fallback**: Detects `package.json` (`npm run build`), `Cargo.toml` (`cargo build`), `.csproj`/`.sln` (`dotnet build`), `pyproject.toml`/`setup.py` (`python -m build`).
- **Synthesis**: If no build script exists, automatically synthesizes a verified or unconfigured template in `.along/scripts/build.py`.
- **Usage**:
  ```bash
  along build [args...]
  ```

### `along test`
Executes automated test suites using quiet, token-efficient flags.
- **Engine Script**: `.along/scripts/test.py`
- **Auto-Detection Fallback**: Detects `pytest` (`pytest -q`), `npm` (`npm test -- --silent`), `dotnet` (`dotnet test -v q`), `cargo` (`cargo test -q`).
- **Usage**:
  ```bash
  along test [args...]
  ```

### `along dev`
Launches the local development server or watcher.
- **Engine Script**: `.along/scripts/dev.py`
- **Auto-Detection Fallback**: Detects `npm run dev`, `cargo run`, `dotnet run`, or `python main.py`.
- **Usage**:
  ```bash
  along dev [args...]
  ```

### `along debug`
Executes project debugging or diagnostics profile.
- **Engine Script**: `.along/scripts/debug.py`
- **Usage**:
  ```bash
  along debug [args...]
  ```

---

## 3. Entity & Repository Management

Entity commands manage the durable in-repo memory stored inside `.along/` (issues, decisions, sessions, scratchpads, and isolated worktrees).

### `along status`
Displays an instant terminal summary of repository health, active in-flight issues, and recent completed sessions.
- **Usage**:
  ```bash
  along status
  ```

### `along doctor`
Validates repository compliance with the Along protocol. Audits `.along/` directory layout, `.gitattributes` merge drivers, and ADR header formatting.
- **Options**:
  - `--entities`: Performs deep validation of the entity DAG graph, verifying parent/child relationships, `blocked_by` dependencies, and detecting circular references.
- **Usage**:
  ```bash
  along doctor
  along doctor --entities
  ```

### `along issue`
Manages atomic issue files in `.along/ISSUES/` and recompiles the active board projection (`.along/ISSUES.md`).
- **Subcommands**:
  - `along issue create <type> <slug> --title "Title" [options...]`: Creates a new issue file. Valid types: `feat`, `bug`, `debt`, `task`, `docs`.
    - Options: `--priority {high,medium,low}`, `--tags "t1,t2"`, `--agent <name>`, `--milestone <name>`.
  - `along issue sync`: Recompiles `.along/ISSUES.md` deterministically from atomic files in `.along/ISSUES/` and `.along/ISSUES/done/`.
  - `along issue done <slug>`: Marks the issue as completed, records `completed: YYYY-MM-DD`, and moves the file into `.along/ISSUES/done/`.
  - `along issue list`: Lists all active in-progress and open issues in the terminal.
- **Usage**:
  ```bash
  along issue create feat token-refresh --title "Add OAuth token refresh" --priority high
  along issue list
  along issue done token-refresh
  along issue sync
  ```

### `along session`
Manages session logs in `.along/SESSIONS/` and records engineering provenance.
- **Subcommands**:
  - `along session create <slug> --summary "Summary" [options...]`: Initializes a new session log.
    - Options: `--issues "slug1,slug2"`, `--decisions "ADR-slug"`, `--agent <name>`, `--milestone <name>`.
  - `along session wrap <slug> [options...]`: Finalizes a session, updates linked issue states, and recompiles projections.
    - Options: `--status {done,superseded}`, `--summary "Summary"`, `--dry-run`, `-n`.
- **Usage**:
  ```bash
  along session create token-refresh --summary "Implementing OAuth token refresh logic"
  along session wrap token-refresh --status done --summary "Completed implementation and hermetic tests"
  ```

### `along decision`
Manages Architectural Decision Records (ADRs) and architectural constraints.
- **Subcommands**:
  - `along decision create <slug> --title "Title" --context "Why" --decision "What" --consequences "Tradeoffs"`: Creates a decentralized ADR in `.along/DECISIONS/ADR-YYYY-MM-DD--<slug>.md` and mirrors to `docs/decisions/`.
  - `along decision sync`: Recompiles the lean projection board `.along/DECISIONS.md` and active architectural constraints in `.along/CONSTRAINTS.md`.
- **Usage**:
  ```bash
  along decision create jwt-auth --title "Adopt JWT for API Auth" --context "Need stateless tokens" --decision "Use RS256 JWTs" --consequences "Key rotation required"
  along decision sync
  ```

### `along scratch`
Manages ephemeral multi-agent session blackboard memory (`.along/.session/<slug>/`) used by `along-team`.
- **Subcommands**:
  - `along scratch init <slug> [--title "Title"] [--steps N] [--restart]`: Initializes session scratchpad directory, `state.json`, and `plan.md`.
  - `along scratch state <slug> [--json]`: Displays current step progress, status, and retry counters.
  - `along scratch update <slug> [--step N] [--step-status {pending,in-progress,passed,failed}] [--inc-retry] [--status {in-progress,completed,failed}]`: Updates execution state.
  - `along scratch purge <slug>`: Deletes ephemeral session blackboard upon completion.
- **Usage**:
  ```bash
  along scratch init token-refresh --title "Token Refresh Step Loop" --steps 4
  along scratch state token-refresh
  along scratch update token-refresh --step 1 --step-status passed
  along scratch purge token-refresh
  ```

### `along worktree`
Manages runtime Git worktree workspace isolation for parallel or multi-agent execution, enforcing the 3-part Environment Readiness Contract.
- **Subcommands**:
  - `along worktree create <slug> [--branch <name>] [--base-ref <ref>]`: Provisions an isolated worktree at `.along/worktrees/<slug>`, links heavy dependencies (`node_modules`, `.venv`) via NTFS directory junctions on Windows (`mklink /J`) or symlinks on POSIX, copies untracked `.env*` files, and shares the session blackboard.
  - `along worktree remove <slug> [--force] [--keep-branch]`: Safely unlinks dependency junctions (`os.rmdir`) without touching parent files, resets CWD, and prunes the worktree with an exponential backoff loop for Windows file handle lock resilience.
  - `along worktree merge <slug> [--squash]`: Merges changes from the worktree branch into the primary working branch.
  - `along worktree list [--json]`: Lists active worktrees, branches, and linked dependencies.
  - `along worktree status [--json]`: Displays environment readiness and filesystem capability matrix.
  - `along worktree gc`: Prunes orphaned worktrees and purges deferred trash directories (`.along/worktrees/.trash_*`).
- **Usage**:
  ```bash
  along worktree create worker-auth --branch feature/auth
  along worktree list
  along worktree merge worker-auth --squash
  along worktree remove worker-auth --force
  along worktree gc
  ```

### `along rules`
Attaches engineering guidelines and rule packs to the project.
- **Subcommands**:
  - `along rules attach`: Automatically inspects repository dependencies and project manifests, attaching appropriate language and platform rule packs into `.along/rules/`.
- **Usage**:
  ```bash
  along rules attach
  ```

### `along budget` (alias `along context-budget`)
Audits repository token footprint and context budgets against protocol limits.
- **Options**:
  - `--check`: Exits with status code 1 if any measured file exceeds configured budget thresholds (e.g. `AGENTS.md` exceeding 14 KB).
  - `--json`: Outputs structured JSON report for CI/CD gates.
- **Usage**:
  ```bash
  along budget
  along budget --check
  along budget --json
  ```

### `along patch`
Executes deterministic Python AST code modifications without LLM syntax corruption.
- **Subcommands**:
  - `along patch replace-func <target_file> <function_name> <replacement_code_file>`: Replaces an existing Python function definition in `<target_file>` with code from `<replacement_code_file>`, preserving comments, formatting, and surrounding file contents.
- **Usage**:
  ```bash
  along patch replace-func scripts/engine.py validate_token scratch/new_validate.py
  ```

---

## 4. Protocol Tool Engines

Protocol tools provide specialized repository maintenance, release management, and intelligence operations.

### `along wrap`
Transactional end-of-stage wrap engine.
- Validates quality gates, inspects git diffs, updates active issue status, moves files to `done/`, writes session logs, recompiles projections, and appends to `HISTORY.md`.
- **Usage**:
  ```bash
  along wrap
  ```

### `along kb-sync` (alias `along kb sync`)
Idempotent compiler and integrity gate for the living LLM-Wiki in `docs/`.
- Validates SHA-256 provenance against source files, recompiles `docs/INDEX.md`, updates `llms.txt` and `llms-full.txt`, rewrites legacy `.along/KB/` links, and enforces link integrity.
- **Options**:
  - `--strict`: Fails with non-zero exit code on broken relative links or missing targets.
  - `--crosslink-check`: Audits documentation for unlinked topic concepts.
  - `--crosslink-apply`: Automatically applies deterministic markdown cross-links.
  - `--strict-sections`: Enforces Section Taxonomy Contracts across standard topic files.
  - `--dry-run`: Reports planned modifications without writing to disk.
- **Usage**:
  ```bash
  along kb-sync
  along kb-sync --strict
  along kb-sync --crosslink-check
  ```

### `along kb-search` (alias `along kb search`)
Targeted snippet retrieval engine across `docs/` and `.along/` living memory.
- Uses token-based Inverse Document Frequency (IDF) scoring to extract relevant headings and paragraphs, minimizing prompt token consumption.
- **Options**:
  - `--category <cat>`: Filters by category (`topic`, `issue`, `decision`, `session`).
  - `--any`: Matches any query token (OR match).
  - `--prefix`: Enables prefix matching.
  - `--stats`: Outputs query timing and corpus indexing statistics.
- **Usage**:
  ```bash
  along kb-search "worktree readiness contract"
  along kb-search "token refresh" --category issue
  ```

### `along dep-scan`
Hierarchical dependency discovery and AI instruction scanner.
- Traverses multi-project repositories (npm, pip, cargo, nuget, go), parses dependencies, discovers vendor AI instruction files, and updates `docs/topic--dependencies.md`.
- **Options**:
  - `--json`: Emits raw JSON discovery data.
- **Usage**:
  ```bash
  along dep-scan
  along dep-scan --json
  ```

### `along history-sync`
Git commit history reconciliation engine.
- Reconstructs `.along/` milestones, issues, and session logs from existing Git commit history, tags, and PR references.
- **Usage**:
  ```bash
  along history-sync
  ```

### `along commit`
Conventional Commits generator with active issue binding and typography validation.
- Automatically checks modified files for forbidden non-ASCII typography, binds commit messages to the active `.along/` issue slug, and creates clean Git commits.
- **Options**:
  - `-i <slug>`: Explicitly specifies target issue slug (otherwise auto-detected from active issue).
  - `-m "<message>"`: Commit message body.
  - `--fix-typography`: Automatically rewrites non-ASCII typography violations before committing.
  - `--no-verify`: Skips pre-commit test gate.
- **Usage**:
  ```bash
  along commit -i token-refresh -m "feat(auth): implement refresh token rotation"
  along commit -i token-refresh -m "fix(auth): handle expired token" --fix-typography
  ```

### `along version-bump` (alias `along bump`)
Multi-stack project version incrementer and release packager.
- Checks pre-release quality gates, updates package manifests (`package.json`, `pyproject.toml`, `Cargo.toml`), updates `CHANGELOG.md`, creates annotated Git release tags, and generates release commits with transactional rollback on test failure.
- **Options**:
  - `patch` | `minor` | `major` | `<version>`: Version increment level (default: `patch`).
  - `-c`, `--commit`: Automatically creates release commit.
  - `-p`, `--push`: Pushes release commit and tag to remote.
  - `--fix-typography`: Automatically repairs typography before releasing.
  - `-n`, `--no-verify`: Bypasses pre-mutation quality gates.
- **Usage**:
  ```bash
  along bump patch
  along bump minor --commit
  ```

### `along update`
Self-update engine for the Along protocol and skills suite.
- Reconciles local repository files, managed protocol blocks, and global user skills (`~/.claude/`, `~/.gemini/`, `~/.codex/`) against the latest upstream release from GitHub.
- Automatically scaffolds and reconciles runtime lifecycle hooks across all supported agent environments (Antigravity `.agents/hooks.json`, Claude Code `.claude/settings.json`, and OpenAI Codex `.codex/hooks.json`).
- **Options**:
  - `--check-only`: Only inspect versions without making modifications.
  - `--dry-run`: Simulate updates, migrations, and hook installations without writing files.
  - `--force`: Force reinstallation even if versions match.
  - `--local-only`: Skip remote GitHub check and use local installation.
  - `--no-hooks`: Skip automatic reconciliation of runtime lifecycle hooks.
  - `--kb-sync`, `--dep-scan`, `--history-sync`, `--all-sync`: Post-update sync triggers.
- **Usage**:
  ```bash
  along update
  along update --dry-run
  along update --no-hooks
  ```

### `along dash` (alias `along dashboard`)
Launches the Along executive dashboard service.
- Provides interactive web UI (FastAPI + MobX), Cytoscape DAG dependency graph, OpenAPI Swagger interface, and static HTML reporting.
- **Options**:
  - `-w`, `--web`: Starts local web server on port 8000.
  - `-c`, `--cli`: Displays terminal summary table.
  - `-e`, `--export`: Generates standalone static HTML report.
- **Usage**:
  ```bash
  along dash --web
  along dash --cli
  ```

### `along migrate`
Protocol migration engine.
- Migrates legacy directory structures (`.agents/` to `.along/`, monolithic `DECISIONS.md` to modular ADRs), updates front-matter schemas, and preserves destination backups in `.along/.migration-backup/`.
- **Options**:
  - `--apply`: Applies planned migration operations (default is safe dry-run plan output).
- **Usage**:
  ```bash
  along migrate
  along migrate --apply
  ```

### `along sanitize` (alias `along typography`)
Typography inspection and ASCII enforcement utility.
- Scans documentation, scripts, and code files for forbidden unicode characters (em-dash, en-dash, curly quotes, guillemets, unicode ellipsis, non-breaking spaces) and reports line-by-line violations.
- **Options**:
  - `--dry-run`: Reports findings and exits with code 0 without modifying files.
  - `--write`: Applies clean ASCII replacements in-place.
  - `--json`: Emits structured JSON findings for CI automation.
  - `--include-data`: Also scans `.json`, `.yaml`, `.yml`, and `.toml` files.
  - `--exclude '<glob>'`: Skips paths matching specified glob pattern.
- **Usage**:
  ```bash
  along sanitize
  along sanitize --write
  along sanitize --check
  ```

### `along feedback` (aliases `diagnostics`, `telemetry`)
System diagnostics and incident dispatch engine.
- Gathers sanitized incident traces from `~/.along/diagnostics/` and exports or dispatches reports via Telegram bot, Webhook, or local export.
- **Options**:
  - `--export`: Exports sanitized diagnostics archive to disk.
  - `--send`: Dispatches incident report to configured alert endpoint.
- **Usage**:
  ```bash
  along feedback
  along feedback --export
  ```

### `along graph-check`
Preflight verification for `code-review-graph` MCP server.
- Verifies graph indexing status, validates `.code-review-graph-ignore` configuration to prevent repository bloat, and checks tool accessibility.
- **Usage**:
  ```bash
  along graph-check
  ```

### `along hook` (alias `along hooks`)
Runtime lifecycle hook interceptor and declarative gate evaluation harness.
- **Subcommands**:
  - `along hook eval <event> [--runtime {antigravity,claude,codex,generic}]`: Evaluates declarative gates against an incoming event payload passed via stdin or argument.
  - `along hook install [--runtime {antigravity,claude,codex,all}]`: Scaffolds or updates runtime hook configuration manifests (`.agents/hooks.json`, `.claude/settings.json`, `.codex/hooks.json`).
  - `along hook verify [--strict]`: Audits bi-directional traceability between prose badges (`[gate: <id>]`) across documentation/skills and declarative YAML gate rules in `default_gates.yaml`.
- **Usage**:
  ```bash
  along hook verify --strict
  along hook install --runtime all
  ```

---

## 5. Exit Codes and CI/CD Automation

All Along CLI commands adhere to standard POSIX process exit code conventions:

| Exit Code | Meaning | Example Scenarios |
| :--- | :--- | :--- |
| `0` | Success | Operation completed cleanly; all gates passed. |
| `1` | General Failure / Gate Denial | Syntax error, broken link (`kb-sync --strict`), forbidden typography (`sanitize`), failed test. |
| `2` | Agent Denied Action | Specific runtime hook denial for OpenAI Codex stderr routing. |

For automated CI/CD validation pipelines, run the following sequence to enforce total repository integrity:

```bash
# 1. Verify gate traceability
along hook verify --strict

# 2. Check typography cleanliness
along sanitize

# 3. Check link integrity and taxonomy
along kb-sync --strict --strict-sections

# 4. Check context budget
along budget --check

# 5. Run hermetic tests
along test
```
