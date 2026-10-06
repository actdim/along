---
protocol: along
protocol_version: "3.9.4"
slug: cli-reference
title: Along CLI Command Reference
type: reference
curated: true
created: 2026-09-14
updated: 2026-10-06
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
- **Synthesis**: If no build script exists, automatically synthesizes a verified or unconfigured template in `.along/scripts/build.py`. An unconfigured template exits `0` with a `[Warning]` that nothing was verified, and the wrap / commit quality gates report "tests are not configured" instead of a pass.
- **Usage**:
  ```bash
  along build [args...]
  ```

### `along test`
Executes automated test suites using quiet, token-efficient flags.
- **Engine Script**: `.along/scripts/test.py`
- **Auto-Detection Fallback**: Detects `pytest` (`pytest -q`), `npm` (`npm test -- --silent`), `dotnet` (`dotnet test -v q`), `cargo` (`cargo test -q`).
- **Distilled Output** (`along test`, `along build`): When stdout is not a terminal (an agent or a pipe reads it), the output is distilled by `alongkit.distill`. A pass becomes `PASS: <cmd> completed successfully (code 0, <s>s)` plus the runner summary (`Ran N tests`, `OK`). A failure keeps the failure blocks: tracebacks, unittest `FAIL:` / `ERROR:` sections, pytest `E` lines, compiler `error:` lines, panics. Resolver chatter, deprecation notices, progress redraws and passing-test lines are dropped. The result is capped at 50 lines / 2 KB, with the runner summary always kept. The raw output is written to `.along/artifacts/lifecycle/<action>.log` (gitignored, overwritten per run). In a terminal the output streams as before.
  - `--raw` streams the full output, `--distill` forces distillation. Both flags are consumed by Along and not passed on; `--verbose` is left alone because pytest and cargo use it. `ALONG_OUTPUT=raw|distill` sets the mode for a whole session. `along dev` / `along debug` always stream.
- **Usage**:
  ```bash
  along test [args...]
  along test --raw -q
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
- **Runtime section**: names the runtime (`claude-code`, `cowork`, `antigravity`, `codex`, ...), the gate enforcement level (`mechanical` only when Along hooks are registered for that runtime, otherwise `advisory`), the Python floor (3.10), a stale `.git/index.lock`, and a cross-OS or VM-mounted repository (worktrees unsafe). See the capability matrix in [Runtime Lifecycle Hooks & Mechanical Gates](./topic--runtime-hooks-and-gates.md).
- **Vision & root notes**: warns about a root `VISION.md` next to `.along/`, an unresolved `along:imported-vision needs-restructure` section in `.along/VISION.md`, and root notes (`ROADMAP.md`, `ARCHITECTURE.md`, `SPEC.md`, `TODO.md`, `DESIGN.md`) that the agent must route into the Knowledge Base.
- **Tracked diagnostics**: warns when files under any `.along/diagnostics/` are still tracked in git (committed before the directory ignored itself) and names `along migrate --apply` (or `git rm --cached`) as the fix.
- **Options**:
  - `--entities`: Performs deep validation of the entity DAG graph, verifying parent/child relationships, `blocked_by` dependencies, and detecting circular references. References resolve against the current `.along/`, every enclosing `.along/` up to the git boundary, and every nested subproject `.along/` below it (nested git repositories and dependency/build dirs are not entered).
  - `--entities --fix`: Removes `milestone` fields of issues and session logs that resolve to no milestone, lists the changed files, then validates.
- **Usage**:
  ```bash
  along doctor
  along doctor --entities
  along doctor --entities --fix
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
  - `along issue done <slug> [options...]`: Marks the issue as completed, records `completed: YYYY-MM-DD`, and moves the file into `.along/ISSUES/done/`. In the same transaction the issue's blackboard (if any) is archived into today's session log `.along/SESSIONS/<YYYY>/<date>--<slug>.md` and, with status `done`, the key is added to its `issues_completed` (the log is created without a blackboard too); the blackboard is purged after the commit. See [Session Lifecycle](./topic--session-lifecycle.md).
    - Options: `--status {done,superseded,cancelled,duplicate}`, `--superseded-by <slug>`, `--duplicate-of <slug>`.
  - `along issue sync`: Recompiles `.along/ISSUES.md` deterministically from atomic files in `.along/ISSUES/` and `.along/ISSUES/done/`, then runs the entity reference integrity gate (`validate_entities`): dangling references or schema / enum violations that are absent at `HEAD` exit `1` in `enforce` mode and only warn in `shadow` mode; problems already present at `HEAD` are printed as a warning and never fail it.
  - `along issue list`: Lists all active in-progress and open issues in the terminal.
  - `along issue rename <old-key> <new-key>`: Renames an issue (type and/or slug; a bare slug keeps the type). Rewrites the file name and `slug`/`type`, then every inbound reference in the nearest `.along/`: `related`, `blocked_by`, `parent`, `superseded_by`, `duplicate_of` in issues, risks, spikes, checklists and ADRs, milestone `target_issues`, and session `issues_advanced` / `issues_completed`.
  - `along issue supersede <old-key> --by <new-key>`: Closes the old issue as `superseded` with `superseded_by: <new-key>` and moves it to `done/` (the file is kept, so session history stays valid). Dependency fields of other entities (`related`, `blocked_by`, `parent`, ...) are rewritten to the successor; session logs are left as they are.
  - `along issue create ... --milestone <m>` and `along issue update --milestone <m>` keep the milestone `target_issues` in sync (added on assignment, removed from the previous milestone on reassignment).
- **Usage**:
  ```bash
  along issue create feat token-refresh --title "Add OAuth token refresh" --priority high
  along issue update token-refresh --priority critical --tags "auth,security" --milestone v4.0.0
  along issue show token-refresh
  along issue list
  along issue done token-refresh
  along issue rename feat--token-refresh feat--oauth-token-refresh
  along issue supersede feat--oauth-token-refresh --by feat--session-auth-rework
  along issue sync
  ```

### `along start`
Atomically marks an issue as `in-progress`, updates `updated: YYYY-MM-DD`, recompiles the active board projection (`.along/ISSUES.md`), initializes the session blackboard (`.along/.session/<slug>/`) and binds this agent session to the issue (`.along/.session/bindings/<runtime>--<session_id>.json`). The plan is not approved by starting: the blackboard is in `phase: planning` until the user approves (Claude Code `ExitPlanMode`, or `along plan approve` after an explicit yes). An approval recorded earlier in the same session carries over.
- **Options**:
  - `--approved`: Mark the plan approved at once (scripted and runner use only).
  - `--worktree`: Enforces git worktree workspace isolation. Verifies environment readiness, provisions an isolated worktree at `.along/worktrees/<slug>` on branch `along/<slug>`, links heavy dependencies (`node_modules`, `.venv`) via NTFS junctions on Windows or symlinks on POSIX, copies untracked configuration (`.env*`), and points agent execution to the worktree path.
  - `--allow-root <path>` (repeatable): Adds `path` to the issue's `allowed_roots` frontmatter: extra read-only roots for `[gate: workspace-containment]` (for example a sibling contracts repository).
  - `--write-scope <path>` (repeatable): Adds `path` to the issue's `write_scope` frontmatter: once set, workspace writes are limited to these subfolders plus `.along/`.
- **Usage**:
  ```bash
  along start token-refresh
  along start token-refresh --worktree
  along start token-refresh --allow-root ../contracts --write-scope packages/auth
  ```

### `along milestone`
Tracks progress across high-level milestones and sprints in `.along/MILESTONES/`. Provides bidirectional synchronization with issues and dynamic progress tracking.
- **Subcommands**:
  - `along milestone sync [<slug>]`: Scans all active and completed issues in `.along/ISSUES/`, discovers issues declaring `milestone: <slug>`, dynamically updates `target_issues: [...]` in milestone frontmatter, recalculates `progress_pct = round(100 * done_count / total)`, and automatically transitions status to `completed` when all target issues are closed. If `<slug>` is omitted, synchronizes all milestones in `.along/MILESTONES/`.
  - `along milestone list [--status <status>] [--json]`: Lists all milestones with progress statistics, completion percentages, and target issue counts.
    - Options: `--status` filters by status (`open`, `in-progress`, `completed`), `--json` outputs machine-readable JSON array.
  - `along milestone show <slug> [--json]`: Displays detailed milestone status, due date, progress percentage, and checklist of all target issues with individual completion states. Supports fuzzy query resolution (exact slug, version prefix such as `4.0`, or substring).
    - Options: `--json` emits structured JSON payload.
  - `along milestone create <slug> --title "Title" [--due YYYY-MM-DD]`: Creates `.along/MILESTONES/<slug>.md` with standard front-matter (`status: open`, empty `target_issues`, `progress_pct: 0`). Refuses to overwrite an existing file and rejects a slug whose version collides with an existing milestone.
- **Usage**:
  ```bash
  along milestone create v5.5.0-priority-aware-planning --title "v5.5.0: Priority-Aware Planning" --due 2027-09-30
  along milestone sync
  along milestone list --status in-progress
  along milestone show v4.0.0-runtime-gates-and-worktree-isolation
  along milestone show 4.0
  ```

### `along session`
Manages session logs in `.along/SESSIONS/` and records engineering provenance.
- **Subcommands**:
  - `along session create <slug> --summary "Summary" [options...]`: Initializes a new session log.
    - Options: `--issues "slug1,slug2"`, `--decisions "ADR-slug"`, `--agent <name>`, `--milestone <name>`, `--commit <sha>`.
    - Front-matter is emitted through `ruamel.yaml`; `branch` and `commit` come from git (omitted outside a repository), and the body records test evidence only when the runtime hooks recorded a run.
  - `along session wrap <slug> [options...]`: Same as `along wrap` (see below), including the required `--decisions` / `--no-decisions` answer.
    - Options: `--status {done,superseded,cancelled,duplicate}`, `--summary "Summary"`, `--decisions "ADR-a,ADR-b"` or `--no-decisions`, `--force-reason "..."`, `--dry-run`, `-n`.
  - `along session bindings`: Lists agent-session bindings (session key, issue, approval, last update).
  - `along session gc [--dry-run]`: Removes bindings older than 72 hours or pointing at a purged blackboard.
- **Usage**:
  ```bash
  along session create token-refresh --summary "Implementing OAuth token refresh logic"
  along session wrap token-refresh --status done --no-decisions --summary "Completed implementation and hermetic tests"
  along session gc --dry-run
  ```

### `along plan`
Plan approval for this agent session ([gate: require-plan-approval]).
- **Subcommands**:
  - `along plan approve [<slug>] [--plan-file <path>]`: Records the user's approval of the presented plan for the bound issue (or for the next `along start` when none is bound). Run it only after the user's explicit yes; in Claude Code accepting a plan via `ExitPlanMode` records it automatically, plan text included. `--plan-file` writes the approved plan into the blackboard `plan.md` (the scaffold becomes `## Revision 1`, later plans are appended as `## Revision N`). With an issue, approval is refused (exit 2) while `plan.md` is still the scaffold.
  - `along plan status`: Prints the session key, the resolved issue (`binding`, `single`, `ambiguous`, `elsewhere`, `none`), the phase and the approval.
- **Usage**:
  ```bash
  along plan status
  along plan approve token-refresh --plan-file plan.md
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
  - `along scratch init <slug> [--title "Title"] [--steps N] [--restart] [--mode direct]`: Initializes session scratchpad directory, `state.json`, and `plan.md`. The blackboard is `role-based` (held to the along-team step loop by `[gate: team-step-active]` and `[gate: team-reviews-before-stop]`) unless `--mode direct` is given.
  - `along scratch state <slug> [--json]`: Displays current step progress, status, and retry counters.
  - `along scratch phase <slug> <inquiry|planning|execution> [--approve]`: Sets the session phase; `--approve` also marks the plan as approved.
  - `along scratch approve <slug>` (alias: `plan-approve`): Grants plan approval and moves the session to the `execution` phase. Refused while `plan.md` is the scaffold.
  - `along scratch update <slug> [--step N] [--step-status {pending,in-progress,passed,failed}] [--inc-retry] [--status {in-progress,completed,failed}]`: Updates execution state.
  - `along scratch fallback <slug> --reason "..."`: Switches the blackboard to single-agent (`direct`) execution and records the reason in `execution_trace.md`.
  - `along scratch purge <slug> [--force --reason "..."]`: Archives the blackboard into today's session log of the issue, then deletes it and the bindings to it (direct blackboards included). Refuses (exit 2) while a role-based blackboard has steps that are not `passed` or passed steps without `reviews/step-N.md`, unless forced with a reason; the reason is written into the record and the trace.
- **Usage**:
  ```bash
  along scratch init token-refresh --title "Token Refresh Step Loop" --steps 4
  along scratch state token-refresh
  along scratch update token-refresh --step 1 --step-status in-progress
  along scratch update token-refresh --step 1 --step-status passed
  along scratch fallback token-refresh --reason "single file change, no parallel roles"
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

### `along git`
Registers Along's custom git merge drivers so concurrent branches merge projections and entity files without conflict markers. Drivers live in the local `.git/config` (per clone, never tracked); the file bindings live in a managed block of the tracked `.gitattributes`. No git hooks are installed. `along update` runs `setup` on the root context automatically.
- **Drivers**:
  - `along-projection` (`**/.along/ISSUES.md`, `**/.along/CONSTRAINTS.md`, `**/docs/INDEX.md`, plus `**/.along/DECISIONS.md` when modular `.along/DECISIONS/` exists): keeps "ours", exits 0, and records the path in `$GIT_DIR/along-projection-resync`. Git runs drivers before the merged entity files reach the working tree, so recompiling inside the driver would only rebuild the pre-merge board. A file that is not an Along projection falls back to a standard 3-way merge.
  - `along-frontmatter` (`**/.along/ISSUES/**/*.md`, `**/.along/DECISIONS/**/*.md`): 3-way YAML merge. A key changed on one side takes that side; if both sides changed it, lists get a 3-way set merge, `status` takes the most advanced lifecycle state, `updated`/`completed` take the later date, and other scalars take the side with the newer `updated` (ours on a tie). Bodies merge through `git merge-file`; overlapping body edits still leave conflict markers and a non-zero exit.
- **Subcommands**:
  - `along git setup [--uninstall] [--dry-run]`: Idempotently writes `merge.along-projection.*` / `merge.along-frontmatter.*` (absolute paths to the interpreter and `along_merge_driver.py`) and refreshes the `.gitattributes` block. `--uninstall` removes both.
  - `along git status [--json]`: Reports driver registration, the `.gitattributes` bindings, and projections awaiting a resync. `along doctor` reports the same.
  - `along git sync`: Recompiles `ISSUES.md`, `DECISIONS.md`, `CONSTRAINTS.md` (root and subprojects named in the marker) and `docs/INDEX.md`, then clears the marker. Run it after a merge.
- **Usage**:
  ```bash
  along git setup
  git merge feature/x
  along git sync
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
  - `along rules attach`: Automatically inspects repository dependencies and project manifests, attaching appropriate language and platform rule packs into `.along/rules/`. A pack whose body differs from its managed header hash is kept (`--on-conflict preserve|diff|overwrite`); an obsolete pack is pruned only when it is unmodified (a headerless legacy pack must match the current template).
  - `along rules status [--json]`, `along rules diff <rule>`, `along rules restore [<rule>]`: audit, diff and restore packs against the Along templates (restore backs up to `.along/.migration-backup/`).
- Agents never edit `.along/rules/**/*.md` directly: [gate: rule-pack-protection] denies it at runtime and `along gates check` flags an edited pack.
- **Usage**:
  ```bash
  along rules attach
  along rules status
  along rules restore platforms/web.md
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
  - `-d, --decisions "ADR-a,ADR-b"` or `--no-decisions` (one is required): The answer to "were architectural decisions made?". The session log for today is written or extended with `issues_completed: [<type>--<slug>]`, the decisions, and the blackboard record (plan, step table, research, execution trace, reviews). A second record of the same issue on the same day is appended as `## Blackboard Record (<n>, <ts>)`. The blackboard is purged only after the wrap transaction committed.
  - `--force-reason "<text>"`: Wrap a role-based blackboard with open steps or missing reviews, or a blackboard whose `plan.md` is still the scaffold (refused otherwise, exit 2); the reason is recorded in the trace.
- **Completion token**: the purge removes the session's binding; when this session had an approved plan for the slug, it keeps a completion token so the following `along commit -i <slug>` passes the plan gate without a new approval (see `along commit`).
- **Usage**:
  ```bash
  along wrap <slug> --no-decisions -m "Summary of work"
  along wrap <slug> --decisions ADR-2026-10-01--session-bindings -m "Summary of work"
  along wrap <slug> -s superseded --no-decisions
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
  - `-a, --all` / `--paths <file>...`: Stage the whole tree / only these paths. Prefer `--paths` when other sessions have uncommitted work in the tree.
  - `-p, --push`: Push after the commit.
- **After `along wrap`**: the plan gate passes `along commit -i <slug>` only for the session that wrapped `<slug>` with an approved plan (completion token); the commit uses the token up. `-i` is required on this path; `--fix-typography`, a write redirect or a chained mutation take the command off it.
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
  - `--carry-over <milestone>`: Moves still-open issues of the released milestone to `<milestone>` (issue `milestone` field and both `target_issues` lists) instead of aborting.
- **Milestone reconciliation**: The milestone whose slug names the new version is set to `completed` only when all its issues (by `milestone` field or `target_issues`) are closed (`done`, `superseded`, `cancelled`, `duplicate`). Otherwise the release aborts inside the transaction and lists the open issues. `progress_pct` is closed / total.
- **Usage**:
  ```bash
  along bump patch
  along bump minor --carry-over v4.6.0-next-release
  along bump minor --commit
  ```

### `along init`
Deterministic scaffolder behind `/along-init` (`scripts/along_init.py`). Idempotent; existing state is never overwritten.
- **AGENTS.md**: FULL protocol block at an architecture root; a short REF block (`ref=<relpath>`) in a nested folder whose ancestor inside the same git working tree carries the FULL block. A git repository or submodule root always gets FULL. A hand-written file without markers gets the block on top and keeps its text under `## Project specifics`.
- **Files**: `CLAUDE.md` import line, `.gitattributes` merge lines, `.along/` skeleton (`ISSUES.md`, `ISSUES/done/`, `DECISIONS/`, `GLOSSARY.md`, `HISTORY.md`, `SESSIONS/<YYYY>/`), `docs/INDEX.md`.
- **VISION**: a root `VISION.md` ends up only in `.along/VISION.md` (moved, deduplicated, or merged under an `along:imported-vision needs-restructure` marker); links to it are repointed (public files -> `docs/INDEX.md`). Otherwise a skeleton with `## Scope`, `## Non-goals`, `## Roadmap` is created.
- **Pipeline**: `along rules attach`, `along git setup` (git roots), `along hook install --runtime all`, `along migrate --apply`.
- **Report**: CREATED / UPDATED / UNTOUCHED files, VISION outcome, repointed links, `AGENT ACTIONS` (imported VISION section, root notes `ROADMAP.md` / `ARCHITECTURE.md` / `SPEC.md` / `TODO.md` / `DESIGN.md`, adopted hand-written `AGENTS.md`) and, when `.along/` already existed, `RE-RUN QUESTIONS` for the user.
- **Options**: `--dry-run`, `--json`, `--no-rules`, `--no-git`, `--no-hooks`, `--no-migrate`.
- **Usage**:
  ```bash
  along init --dry-run
  along init
  along init packages/lib --no-hooks
  ```

### `along update`
Self-update engine for the Along protocol and skills suite.
- Refreshes the managed protocol block in every context with the same rules as `along init` (FULL/REF, hand-written adoption) and runs the migration, whose Step 13 reconciles a root `VISION.md` even on an up-to-date repository.
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
Preflight verification for `code-review-graph` AST engine.
- Verifies graph indexing status, validates `.code-review-graph-ignore` configuration to prevent repository bloat, and checks tool accessibility.
- **Usage**:
  ```bash
  along graph-check
  along graph-check --json
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

### `along graph-impact`
Semantic blast radius and affected execution flow analyzer.
- Traces direct callers, callees, and importers using `code-review-graph` AST queries with automatic fallback to static search.
- Automatically maps impacted symbols to candidate tests and affected documentation articles in `docs/topic--*.md`.
- **Options**:
  - `TARGET`: Symbol name or file path (auto-detects changes from git if omitted).
  - `--base REF`: Git base ref for change detection (default: `HEAD~1`).
  - `--max-depth N`: Traversal depth in the call hierarchy (default: `2`).
  - `--json`: Output machine-readable JSON report.
  - `--optional`: Treat offline AST engine state as non-fatal warning.
- **Usage**:
  ```bash
  along graph-impact                          # Auto-detect changed files from git
  along graph-impact scripts/along_exec.py    # Target specific file
  along graph-impact my_symbol --max-depth 3  # Trace symbol callers up to 3 hops
  along graph-impact --json                   # Output machine-readable JSON report
  ```

### `along graph-arch`
Architectural intelligence, community clustering, and coupling hotspot analyzer.
- Analyzes repository modular structure, cohesion-based functional communities, hub hotspots, and critical bridge nodes.
- **Options**:
  - `--detail-level {standard,minimal}`: Output detail level (default: `standard`).
  - `--top-hubs N`: Maximum number of hub nodes to display (default: `5`).
  - `--top-bridges N`: Maximum number of bridge nodes to display (default: `5`).
  - `--json`: Output machine-readable JSON report.
- **Usage**:
  ```bash
  along graph-arch
  along graph-arch --detail-level minimal
  along graph-arch --json
  ```

### `along hook` (alias `along hooks`)
Runtime lifecycle hook interceptor and declarative gate evaluation harness.
- **Subcommands**:
  - `along hook eval <event> [--runtime {antigravity,claude,codex,generic}]`: Evaluates declarative gates against an incoming event payload passed via stdin or argument.
  - `along hook install [--runtime {antigravity,claude,codex,all}]`: Scaffolds or updates runtime hook configuration manifests (`.agents/hooks.json`, `.claude/settings.json`, `.codex/hooks.json`).
  - `along hook attribution [--runtime {claude,cursor,all}] [--claude-home DIR] [--cursor-home DIR] [--dry-run]`: Turns off AI commit attribution (`Co-Authored-By:` trailers) in existing runtime homes: `attribution.commit = ""` + `includeCoAuthoredBy = false` in Claude Code `settings.json`, `attribution.attributeCommitsToAgent = false` in Cursor `cli-config.json`. Writes no hooks. Also run by the installers and every `/along-update`.
  - `along hook install --git [--uninstall] [--dry-run]`: Opt-in, never run by init/update. Writes `pre-commit` and `commit-msg` shims into the repository's hooks directory that run `along gates check --hook <name>`. A foreign hook already there is kept as `<hook>.pre-along` and run first (restored on `--uninstall`); with `core.hooksPath` set (husky, lefthook) nothing is written and the commands to add to the manager are printed.
  - `along hook verify [--strict]`: Audits bi-directional traceability between prose badges (`[gate: <id>]`) across documentation/skills and declarative YAML gate rules in `default_gates.yaml`, and prints the enforcement matrix (`runtime` / `git` / `ci` per gate).
- **Usage**:
  ```bash
  along hook verify --strict
  along hook install --runtime all
  along hooks install --git
  ```

### `along gates`
Runs the commit-time gate subset (catalogue entries with `git` or `ci` in `enforcement`) outside agent runtimes. Read-only: projection freshness is checked by recompiling in a temp snapshot. Exit `0` clean, `1` violations, `2` usage error.
- **Subcommands**:
  - `along gates check`: Staged changes (same as `--hook pre-commit`).
  - `along gates check --hook pre-commit`: Added lines of the staged diff (typography in `.md`/`.py`/`.sh`/`.ps1`/`.bat`, conflict markers, anti-stub) and freshness of staged `.along/` boards (`ISSUES.md`, `DECISIONS.md`, `CONSTRAINTS.md`). Only added lines count, so existing debt elsewhere never blocks a commit.
  - `along gates check --hook commit-msg <file>`: Issue binding and AI co-author trailers in the message.
  - `along gates check --ci [--range R] [--no-links] [--json]`: Every non-merge commit message in the range, the range diff, projection freshness of the checkout, and link integrity (`along kb-sync --check`). The range defaults to `origin/$GITHUB_BASE_REF...HEAD` for PRs, `$ALONG_CI_BEFORE..HEAD` for pushes, else `HEAD^..HEAD`. Used by `.github/workflows/tests.yml`.
- **Usage**:
  ```bash
  along gates check --ci --range origin/main...HEAD
  ```

### `along run`
Executes an agent runtime supervisor or runs a shell command behind the Along runtime lifecycle hook and declarative gate pipeline.

#### 1. Agent Runtime Runner
Supervises an autonomous agent runtime (such as Google Antigravity), enforcing workspace containment, active issue binding, and dual-channel OpenTelemetry tracing:

```bash
along run antigravity [--dry-run] [-i|--issue <slug>] [--run-id <id>] [-e|--endpoint <url>] [-b|--binary <path>] [-- <agent-args...>]
along run agy [--dry-run] [-i|--issue <slug>] [--run-id <id>] [-e|--endpoint <url>] [-b|--binary <path>] [-- <agent-args...>]
```

Parameters:
- `--dry-run`, `-n`: Preview configured environment variables, resolved binary, and active issue binding without spawning the process.
- `-i`, `--issue <slug>`: Bind the run to an explicit active issue (defaults to the currently in-progress issue in `.along/ISSUES/`).
- `--run-id <id>`: Set an explicit 32-character run ID for telemetry grouping.
- `-e`, `--endpoint <url>`: Target OpenTelemetry OTLP/HTTP traces endpoint.
- `-b`, `--binary <path>`: Explicit path to the Antigravity binary executable.

#### 2. Lifecycle Command Proxy
Intercepts shell commands, validating CLI safety, typography, and circuit breaker gates before executing:

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
