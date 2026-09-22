---
protocol: along
protocol_version: "3.9.4"
slug: cli-reference
title: Along CLI Command Reference
type: topic
curated: true
created: 2026-09-14
updated: 2026-09-21
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

### In-Band vs Out-of-Band Execution

- **In-Band (Inside Agent Session)**: Standard day-to-day workflow driven by the agent using specialized skills (`/along-test`, `/along-wrap`, `/along-kb-sync`).
- **Out-of-Band (External OS Terminal CLI)**: Direct command execution by the developer or bootstrap scripts via `along <command>` (e.g. `along update`, `along doctor`). Essential for initial bootstrapping, protocol upgrades, and disaster recovery when runtime lifecycle hooks are in a broken state.

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
    - Options: `--priority {high,medium,low,critical}`, `--tags "t1,t2"`, `--agent <name>`, `--milestone <name>`.
  - `along issue update <slug> [options...]` (alias: `along issue edit`): Updates frontmatter metadata of an existing issue, preserving YAML comments and ordering.
    - Options:
      - `--milestone <name>`, `-m <name>`: Assigns or reassigns issue to a milestone. Supports fuzzy matching (exact slug, version prefix such as `v4.0` or `4.0`, or unambiguous substring). Use `"none"`, `"null"`, or `""` to unassign. Automatically triggers bidirectional milestone synchronization.
      - `--priority <p>`, `-p <p>`: Updates priority (`critical`, `high`, `medium`, `low`).
      - `--status <s>`, `-s <s>`: Updates status (`open`, `in-progress`, `blocked`, `done`, `superseded`, `cancelled`, `duplicate`).
      - `--tags <t1,t2>`: Replaces tags with a comma-separated list.
      - `--title <title>`, `-t <title>`: Updates the issue title in frontmatter.
    - Side-effects: Automatically recompiles `.along/ISSUES.md` board projection and synchronizes affected milestones.
  - `along issue show <slug> [--json]` (alias: `along issue get`): Displays detailed summary of an issue, including frontmatter metadata, priority, status, milestone, and body excerpt.
    - Options: `--json` outputs structured JSON payload.
  - `along issue done <slug> [options...]`: Marks the issue as completed, records `completed: YYYY-MM-DD`, and moves the file into `.along/ISSUES/done/`.
    - Options: `--status {done,superseded,cancelled,duplicate}`, `--superseded-by <slug>`, `--duplicate-of <slug>`.
  - `along issue sync`: Recompiles `.along/ISSUES.md` deterministically from atomic files in `.along/ISSUES/` and `.along/ISSUES/done/`.
  - `along issue list`: Lists all active in-progress and open issues in the terminal.
- **Usage**:
  ```bash
  along issue create feat token-refresh --title "Add OAuth token refresh" --priority high
  along issue update token-refresh --priority critical --tags "auth,security" --milestone v4.0.0
  along issue show token-refresh
  along issue list
  along issue done token-refresh
  along issue sync
  ```

### `along start`
Atomically marks an issue as `in-progress`, updates `updated: YYYY-MM-DD`, recompiles the active board projection (`.along/ISSUES.md`), initializes the session blackboard (`.along/.session/<slug>/`), marks the living plan as approved (`phase: execution`, `plan_approved: true`), and binds the active issue for agent execution.
- **Options**:
  - `--worktree`: Enforces git worktree workspace isolation. Verifies environment readiness, provisions an isolated worktree at `.along/worktrees/<slug>` on branch `along/<slug>`, links heavy dependencies (`node_modules`, `.venv`) via NTFS junctions on Windows or symlinks on POSIX, copies untracked configuration (`.env*`), and points agent execution to the worktree path.
- **Usage**:
  ```bash
  along start token-refresh
  along start token-refresh --worktree
  ```

### `along milestone`
Tracks progress across high-level milestones and sprints in `.along/MILESTONES/`. Provides bidirectional synchronization with issues and dynamic progress tracking.
- **Subcommands**:
  - `along milestone sync [<slug>]`: Scans all active and completed issues in `.along/ISSUES/`, discovers issues declaring `milestone: <slug>`, dynamically updates `target_issues: [...]` in milestone frontmatter, recalculates `progress_pct = round(100 * done_count / total)`, and automatically transitions status to `completed` when all target issues are closed. If `<slug>` is omitted, synchronizes all milestones in `.along/MILESTONES/`.
  - `along milestone list [--status <status>] [--json]`: Lists all milestones with progress statistics, completion percentages, and target issue counts.
    - Options: `--status` filters by status (`open`, `in-progress`, `completed`), `--json` outputs machine-readable JSON array.
  - `along milestone show <slug> [--json]`: Displays detailed milestone status, due date, progress percentage, and checklist of all target issues with individual completion states. Supports fuzzy query resolution (exact slug, version prefix such as `4.0`, or substring).
    - Options: `--json` emits structured JSON payload.
- **Usage**:
  ```bash
  along milestone sync
  along milestone list --status in-progress
  along milestone show v4.0.0-runtime-gates-and-worktree-isolation
  along milestone show 4.0
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

### `along circuit`
Manages the Systemic Anomaly Circuit Breaker and Human Escalation Gate.
- Detects VCS corruption, OS/NTFS file contention, missing toolchain binaries, unauthorized global package manager commands, and repetitive syntax edit churn.
- **Subcommands**:
  - `along circuit status [--json]`: Displays current circuit breaker state (`CLOSED` or `TRIPPED`) and active anomaly escalation report.
  - `along circuit trip [--class N] [-r MSG]`: Manually trips the circuit breaker for a specified anomaly class (1 through 5).
  - `along circuit reset [--force]`: Executes pre-flight health probe and resets breaker to `CLOSED` when healthy.
  - `along circuit verify`: Executes environment health probe (checking `.git/index` size >= 12 bytes, absence of stale locks, and AST syntax parsing) without altering state.
- **Usage**:
  ```bash
  along circuit status
  along circuit verify
  along circuit reset
  along circuit trip --class 1 -r "Corrupted git index detected"
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
- **Options**:
  - `-s, --status <status>`: Closing status (`done`, `superseded`, `cancelled`, `duplicate`). Default: `done`.
  - `-m, --summary "<text>"`: One-line summary for `.along/HISTORY.md` index.
  - `--dry-run`: Simulate wrap-up operations without writing or moving files.
  - `-n, --no-verify`: Skip pre-flight automated tests.
  - `-a, --agent "<name>"`: Explicit agent name.
- **Usage**:
  ```bash
  along wrap <slug> -m "Summary of work"
  along wrap <slug> -s superseded
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
- Automatically scaffolds and reconciles global runtime lifecycle hooks in user home configurations (`~/.gemini/config/hooks.json`, `~/.claude/settings.json`, and `~/.codex/hooks.json`) and recursively purges legacy local hooks and workaround scripts from consumer repositories.
- Performs pre-flight hook cleanup and per-context exception isolation so that corrupt or locked files in one subproject do not abort the update for remaining contexts.
- **Out-of-Band Recovery**: If an agent session is ever locked due to a broken hook configuration (chicken-and-egg problem), running `along update` from an external OS terminal bypasses agent interception, cleans up broken local hooks, and restores the environment.
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

### `along graph-sync` (alias `along graph-build`)
Code intelligence AST knowledge graph synchronization engine.
- Runs incremental AST update (default) or full rebuild (`--full`) via pinned `code-review-graph`.
- Automatically creates or repairs `.code-review-graph-ignore` with standard exclusions (`node_modules/`, `dist/`, `.venv/`, etc.) before indexing.
- **Usage**:
  ```bash
  along graph-sync              # Incremental update (changed files only)
  along graph-sync --full       # Full graph rebuild from scratch
  along graph-sync --status     # Show current graph statistics
  along graph-build             # Alias for graph-sync
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

### `along run`
Executes a shell command behind the Along runtime lifecycle hook and declarative gate pipeline.
- Intercepts shell commands, validating CLI safety, typography, and circuit breaker gates before executing.
- **Usage**:
  ```bash
  along run pytest -q
  along run npm test
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
