---
protocol: along
slug: runtime-hooks-and-gates
title: Runtime Lifecycle Hooks & Mechanical Gates
type: architecture
created: 2026-09-11
updated: 2026-10-05
tags: [hooks, gates, runtime, enforcement, antigravity, claude, codex, typography, cli-safety, circuit-breaker, attribution]
sources:
  - path: scripts/alongkit/attribution.py
  - path: scripts/alongkit/circuit.py
  - path: scripts/alongkit/repochecks.py
  - path: scripts/alongkit/hooks/engine.py
  - path: scripts/along_hook.py
  - path: scripts/alongkit/hookpreflight.py
  - path: scripts/alongkit/repo.py
  - path: scripts/alongkit/hooks/adapters/claude.py
  - path: scripts/alongkit/hooks/adapters/codex.py
---

# Runtime Lifecycle Hooks & Mechanical Gates

## 1. System Topology & Overview

Passive prose instructions in `AGENTS.md` and `skills/*/SKILL.md` decay as agent conversation transcripts expand. When context windows fill, probabilistic LLMs cut corners, emit forbidden non-ASCII typography (em-dashes, curly quotes, guillemets), write heredocs over shell tools, or attempt to terminate turns prematurely without executing tests.

The Along Runtime Hook and Gate System establishes deterministic, programmatic interception at the agent harness boundary. Rather than relying on fragile in-process monkey-patching or invasive Git-level hooks (`.git/hooks/*`), Along hooks directly into host agent runtime lifecycle events (`PreToolUse`, `PostToolUse`, `Stop`) supported natively by Google Antigravity, Claude Code, and OpenAI Codex.

```text
+-------------------------------------------------------------------------+
|                         Agent Runtime Harness                           |
|       Google Antigravity (.agents/hooks.json)                           |
|       Claude Code (.claude/settings.json)                               |
|       OpenAI Codex (.codex/hooks.json)                                  |
+-------------------------------------------------------------------------+
                                   |
                         stdin (JSON / protojson)
                                   v
+-------------------------------------------------------------------------+
|                  Universal Dispatcher: scripts/along_hook.py            |
|                  --runtime <name> --event <event_type>                  |
+-------------------------------------------------------------------------+
                                   |
                                   v
+-------------------------------------------------------------------------+
|                       alongkit.hooks Pipeline                           |
|                                                                         |
|  1. Configuration & Governance (alongkit.hooks.config):                 |
|     - Modes: enforce vs shadow                                          |
|     - Audit Log: .along/diagnostics/hooks_audit.jsonl                   |
|                                                                         |
|  2. Stateless Content & Command Gates (alongkit.hooks.gates):           |
|     - TypographyGate: blocks non-ASCII typography (table in typography) |
|     - ProjectionProtectionGate: blocks manual edits to ISSUES.md/INDEX  |
|     - CliSafetyGate: blocks heredocs, inline python writers, wipes      |
|                                                                         |
|  3. Runtime Adapters (alongkit.hooks.adapters):                         |
|     - AntigravityAdapter: JSON { decision: "deny" | "allow" }          |
|     - ClaudeCodeAdapter: exit code 0 (allow) / 2 (deny + stderr)        |
|     - CodexAdapter: exit code 0 (allow) / 2 (deny + stderr)             |
+-------------------------------------------------------------------------+
```

---

## 2. Core Components & Engine Implementation

### 2.1 Canonical Event Models (`alongkit.hooks.models`)
- `HookEventType`: Enumerates `PreToolUse`, `PostToolUse`, `PreInvocation`, `PostInvocation`, and `Stop`.
- `HookEvent`: Carries normalized event data (`tool_name`, `tool_args`, `workspace_root`, `conversation_id`, `step_idx`).
- `GateDecision`: Categorizes decisions into `allow`, `deny`, `ask`, and `force_ask`.
- `GateResult`: Carries the final decision, remediation message, gate identifier, and optional argument overwrites.

### 2.2 Gate Implementations (`alongkit.hooks.gates`)
1. **`TypographyGate`**:
   - Intercepts file mutation tools (`write_to_file`, `replace_file_content`).
   - Uses `alongkit.typography.findings()` to scan text payloads.
   - Forbids em-dashes (U+2014), en-dashes (U+2013), math minus (U+2212), curly quotes (U+201C, U+201D), guillemets (U+00AB, U+00BB), ellipsis glyphs (U+2026), and non-breaking spaces (U+00A0, U+202F, U+200B).
   - Exempts localized resource directories (`locales/`, `i18n/`, `translations/`).
   - Returns exact 1-based line numbers and character descriptions in remediation messages.
2. **`ProjectionProtectionGate`**:
   - Intercepts file mutation tools.
   - Prevents direct manual writes to compiled projection views (`.along/ISSUES.md`, `docs/INDEX.md`).
   - Instructs agents to mutate atomic files (`.along/ISSUES/<type>--<slug>.md`) and run compiler sync commands.
3. **`CliSafetyGate`**:
   - Intercepts command execution tools (`run_command`, `execute_command`, `bash`).
   - Scans command strings for forbidden patterns: heredocs (`<<EOF`), inline Python file writers (`python -c "open('...', 'w')"`), destructive unstaged Git wipes (`git reset --hard`, `git clean -f`), and unauthorized global package managers (`npm install -g`).

### 2.3 Declarative Extension & Traceability Matrix
Beyond hardcoded Python gates, Along provides an extensible, declarative YAML gate catalogue (`default_gates.yaml` and `.along/rules/gates.yaml`) enforcing 24 canonical gates, 7 of them git/CI-only repository-state checks (including `require_plan_approval` for inquiry read-only locks, `circuit_breaker`, `worktree_env_readiness`, and `workspace_containment`, which keeps file, search and shell-cwd paths inside the workspace; see [Declarative Gates](./topic--declarative-gates-and-traceability.md)), verified bi-directionally against prose badges (`[gate: <id>]`) via `along hook verify`.
For full specification and architecture, see [Declarative Gate Engine & Traceability Matrix](./topic--declarative-gates-and-traceability.md).


### 2.4 Runtime Adapters (`alongkit.hooks.adapters`)
- **`AntigravityAdapter`**: Translates Google Antigravity JSON payloads (`toolCall.name`, `toolCall.args`) to `HookEvent`, returning JSON stdout with `allow`/`deny` decisions.
- **`ClaudeCodeAdapter`**: Translates Anthropic Claude Code payloads to `HookEvent`, mapping `Write` to `write_to_file`, `Edit`/`MultiEdit`/`NotebookEdit` to `replace_file_content`, `Bash`/`PowerShell` to `run_command`, and `Read`/`Grep`/`Glob` to the read tools; `session_id` becomes the event's session id. Responses: exit 0 for allow; exit 2 with the remediation on `stderr` for a denial; exit 0 with `hookSpecificOutput.permissionDecision: "ask"` for an ASK (the user decides); on `Stop` with `stop_hook_active: true` a denial is reported once as a `systemMessage` instead of forcing another continuation.
- **Claude Code hook schema**: `along hook install --runtime claude [--global]` writes the nested schema Claude Code reads, `{"matcher": ..., "hooks": [{"type": "command", "command": ..., "timeout": 30}]}`, for `PreToolUse` (`Write|Edit|MultiEdit|NotebookEdit|Bash|PowerShell|Read|Grep|Glob`), `PostToolUse` (edits and `ExitPlanMode`) and `Stop`. Legacy flat `{matcher, command}` entries, which Claude Code ignores, are migrated in place; foreign hooks are kept.
- **`CodexAdapter`**: Translates OpenAI Codex CLI and headless harness JSON payloads to HookEvent, mapping write_file/create_file to write_to_file, edit_file/patch to replace_file_content, and shell/bash/exec to run_command. Formats exit code 0 for allow, and exit code 2 with the remediation message written to stderr for gate denials.
- **`GenericCliAdapter`**: Translates generic CLI tool invocations, terminal proxy wrappers, Cursor (`.cursor/hooks.json`), and OpenCode to `HookEvent`. Normalizes arguments across tool types, supports plain command strings as fallback `run_command`, and formats exit code 0 for allow or exit code 2 with stderr remediation message for gate denials.

### 2.5 Execution Pipeline & Dispatcher (`alongkit.hooks.engine` & `scripts/along_hook.py`)
- `HookEngine`: Evaluates incoming events sequentially against all registered gates (both built-in and declarative).
- `along_hook.py`: Universal CLI driver handling process I/O, error recovery, adapter dispatch, and `verify` audit.
- **Activation** (`alongkit.hookpreflight`, stdlib only, before the dependency bootstrap): the gates apply only inside an Along context. A context is a `.along/` holding Along state (a `.along/` with nothing but `diagnostics/` is hook output, not a context), a legacy `.agents/` with Along entities, or a declared root. A bare `AGENTS.md` does not activate anything: it is a tool-agnostic convention. Outside a context the hook allows and exits without loading dependencies; `Read`/`Grep`/`Glob` inside the root and outside `docs/` and the state directory are answered the same way. Progress notes of the bootstrap are suppressed in hooks, since hook stderr lands in every tool result.
- **Declared roots** (`repo.declared_root`): a directory whose Along state lives elsewhere, for example a nested personal repository, declares it with `<!-- along-root: .local -->` in its `AGENTS.md`, or without touching shared files in `~/.along/config.json`:

  ```json
  { "context_roots": [ { "workspace": "D:/work/product/src", "root": ".local" } ] }
  ```

  State then resolves to `<root>/.along/` (`repo.state_dir`), while gates keep evaluating paths against the declaring directory; paths inside the state directory are matched as `.along/...`.
- Subcommand `along hook install`: Scaffolds runtime hook configurations (`.agents/hooks.json` for Antigravity, `.claude/settings.json` for Claude Code, `.codex/hooks.json` for OpenAI Codex, `.cursor/hooks.json` for Cursor). Accepts `--runtime {antigravity,claude,codex,cursor,all}`. Also turns off AI commit attribution where the runtime documents a key for it (see 2.7).
- Subcommand `along run <cmd...>` (and `along_hook.py run <cmd...>`): Command proxy wrapper evaluating `run_command` through `HookEngine` prior to execution. Provides mechanical gate enforcement in environments without native PreToolUse lifecycle hooks (OpenCode, CI, and external terminals).
- Subcommand `along hook verify`: Audits bi-directional traceability between prose badges and YAML gates.

### 2.6 Systemic Anomaly Circuit Breaker (`alongkit.circuit`)
When deep infrastructure or toolchain failures occur (corrupted `.git/index`, NTFS file locks, permission denials, missing system binaries, or repeated syntax edit thrashing), probabilistic LLMs often enter destructive self-healing loops (e.g. attempting unauthorized global package installations or repeatedly overwriting corrupted files).

The Circuit Breaker (`[gate: circuit-breaker]`) acts as a programmatic hard stop:
- **5 Systemic Anomaly Classes**:
  - Class 1: VCS & Repository State Corruption (truncated `.git/index`, stale `index.lock`, loose object corruption).
  - Class 2: OS & Filesystem Contention (NTFS/POSIX sharing violations, `EACCES`, `EBUSY`, permission denied, disk full).
  - Class 3: Global Environment & Toolchain Defects (missing `uv`/`git`/`python`, unauthorized global package manager commands like `pip install` or `npm install -g`).
  - Class 4: Process Cascades & Zombie Hangs (process timeouts, zombie runners).
  - Class 5: Syntax Churn & Self-Destructive Edit Loops (consecutive syntax compilation failures on the same file >= 2 times).
- **Zero-Retry Tripping**: Trips immediately to `TRIPPED` state in `.along/diagnostics/circuit_breaker.json`, prints a standardized high-visibility human escalation banner, and blocks modifying tool calls via `PreToolUse`.
- **Pre-Flight Health Probe & Resumption Gate**: Requires human remediation and execution of `along circuit reset`, which executes `run_health_probe()` (verifying `.git/index` integrity, absence of stale locks, and clean AST syntax) before unlocking agent tools.

### 2.7 Commit Attribution Policy (`alongkit.attribution`)
Agent runtimes append `Co-Authored-By:` trailers naming themselves (for example `Claude ... <noreply@anthropic.com>`). GitHub resolves the trailer email to an account and lists the vendor as a repository contributor; undoing it later needs a history rewrite and a force-push. `[gate: commit-no-ai-coauthor]` keeps the trailers out in three layers:

| Layer | Where | What it does |
| :--- | :--- | :--- |
| Runtime config | `along hook install --runtime claude` | Sets `attribution.commit = ""` and legacy `includeCoAuthoredBy = false` in `settings.json`; other keys are kept. |
| Runtime config | `along hook install --runtime cursor --global` | Sets `attribution.attributeCommitsToAgent = false` in `~/.cursor/cli-config.json`. |
| Reconcile | `along hook attribution [--runtime claude\|cursor\|all]`, `install.ps1` / `install.sh`, every `/along-update` run | `reconcile_attribution` writes only the attribution keys above, only for runtime homes that already exist, even when the install is up to date. `--no-hooks` skips it in `/along-update`. |
| Gate | `commit_no_ai_coauthor` (`predicates.check_ai_coauthor`) | Denies `git commit` whose command line or `-F` message file carries an AI co-author trailer. Human co-authors pass. |
| Commit engine | `/along-commit` | Strips AI co-author trailers from the message before committing. |

Codex and Antigravity document no attribution key; for them the gate and `/along-commit` are the only layers. Opt out per repository with `.along/config.json`:

```json
{ "commits": { "allow_ai_coauthor": true } }
```

### 2.8 Agent-Session Binding & Plan Approval (`alongkit.session`)
Several agent sessions may work in one repository at once, so gates never read a repository-wide "active issue". Each session is bound to one issue:

- **Binding**: `along start <slug>` writes `.along/.session/bindings/<runtime>--<session_id>.json` (`slug`, `context`, `plan_approved`, `approved_slug`). The session id comes from the hook payload (`session_id`, antigravity conversation id) and, for CLI calls, from `CLAUDE_CODE_SESSION_ID`, `ANTIGRAVITY_CONVERSATION_ID`, `CODEX_SESSION_ID` or `ALONG_SESSION_ID` (+ `ALONG_SESSION_RUNTIME`). Bindings live in the outermost `.along/` of the workspace (up to the git top, never `~/.along`); `context` names the `.along/` the issue belongs to, so a session bound to a subproject issue is visible at the root.
- **Resolution** (`session.resolve_active_session`): `ALONG_ISSUE_SLUG` (runner) > own binding > the single in-progress blackboard not bound to another session > none. Several unbound candidates are `ambiguous`: gates refuse and point at `along start <slug>`.
- **Plan approval**: `along start` binds with `phase: planning`, `plan_approved: false`. Approval is recorded per session when the user accepts a plan in Claude Code (`PostToolUse` on `ExitPlanMode`), or by `along plan approve [<slug>]` after the user's explicit yes; an approval given before `along start` carries over to the first bound slug. `along start --approved` is for scripted runs. Along state commands (`issue`, `start`, `scratch`, `plan`, `decision`, `milestone`, `session`, `wrap`, `kb sync`) and writes to `.along/ISSUES|RISKS|SPIKES|SESSIONS|.session|diagnostics` pass `require_plan_approval`, so an issue can be written and started before a plan exists.
- **Unbound sessions**: `require_plan_approval` and `test_before_stop` hold only sessions bound to an issue (`along start`, or `ALONG_ISSUE_SLUG` from a runner). A repository that wants unbound sessions held too sets `enforce_unbound: true` for those gates in `.along/rules/gates.yaml` (this repository does). `require_active_issue` is unaffected: source edits still need an in-progress issue.
- **Read-only shell commands**: before approval, `alongkit.hooks.shellparse.is_read_only_command` lets a Bash call through only when every segment reads: inspection commands and pure filters (`cat`, `grep`, `head`, `tail`, `cut`, `sort`, `uniq`, `tr`, `diff`, ...), `sed` without `-i`, `-f` or `w`/`W`/`e` script commands, `awk` without `-i inplace`, `-f`, `system()` or print redirection/pipes, `find` without `-exec`/`-delete`/`-fprint*`, and test runs.
- **Verification commands** (`shellparse.is_verification_command`) pass in every phase: builds, tests, linters and type checkers (`dotnet build|test`, `cargo build|check|test|clippy`, `go build|vet|test`, `npm|pnpm|yarn [run] build|test|lint|typecheck|check`, `tsc`, `mypy`, `pyright`, `ruff check`, `eslint`, `along build|test`). They write build output, never sources; `--fix`, formatters, snapshot updates and output redirection are excluded. Without this, test-before-stop could demand a run the plan gate forbids. `$(...)` and backquote substitutions are classified recursively, and shell keywords (`for ... in`, `do`, `done`, `if`, `then`, `else`, `fi`, `while`) defer to the commands they wrap.
- **Session root**: the hook evaluates against the session's project, not the agent's current shell cwd (which follows `cd`). With Claude Code, `CLAUDE_PROJECT_DIR` anchors the root whenever the cwd lies inside it (`repo.find_session_root`), so session bindings and containment survive a `cd` into a nested `.along/` context.
- **Entity reference integrity**: the Stop predicate runs only after an entity file changed and blocks only problems absent at `HEAD` (`gitgates.baseline_entity_problems` validates a `git archive` snapshot of every `.along/` entity dir); problems already committed are left to `along doctor --entities`. References resolve upward (enclosing contexts) and downward (nested subproject contexts, `entities.descendant_entity_keys`).
- **Repository-level `.along/.session/state.json`** is read only for runtimes that pass no session id; `purge` removes it when it points at the purged slug.
- **Housekeeping**: `along plan status`, `along session bindings`, `along session gc [--dry-run]` (bindings older than 72 h or without a blackboard). `along scratch purge` / `along wrap` remove the slug's bindings.
- **Activity trace** (`test_before_stop`): per session in `.along/diagnostics/activity/<key>.json`; edits under `.along/` are not source edits. Only what the gates let through is recorded: an edit on `PostToolUse` (the tool succeeded), a test run on `PreToolUse` after every gate allowed it, so changes made outside the session or writes a gate rejected never count. Where `.along/scripts/test.py` exists only `along test` / that script count as a test run; raw runners are named in the Stop message. The gate is quiet while the circuit breaker is tripped, since no command could run.
- **Diagnostics** (`hooks_audit.jsonl`, activity traces, `hook_heartbeat.json`, circuit breaker) are machine-local: `.along/diagnostics/` carries its own `*` `.gitignore`. They go to the resolved state directory (`repo.diagnostics_dir`); without one they go to `~/.along/diagnostics/workspaces/<path>/`. The hooks never create a `.along/` of their own.

### 2.9 along-team Step Discipline & Wrap Record
- `along scratch init` creates a `role-based` blackboard (`--mode direct` opts out); `along start` creates a `direct` one. `[gate: team-step-active]` denies source edits in a role-based session while no step is `in-progress`; `[gate: team-reviews-before-stop]` blocks the turn end while a `passed` step lacks `reviews/step-N.md`.
- `along scratch purge` and `along wrap` refuse while role-based steps are open or reviews are missing; `--force --reason` / `--force-reason` records why in `execution_trace.md`. `along scratch fallback <slug> --reason` switches to single-agent execution with the reason in the trace.
- `along wrap` requires `--decisions ADR-...` or `--no-decisions`, writes (or extends) today's session log with `issues_completed: [<type>--<slug>]`, the decisions answer and the blackboard record (plan, step table, research, trace, reviews), and only then purges the blackboard.

---

## 3. Data Flow & Execution Workflow

When an agent emits a tool call, the execution loop flows through the hook harness:

```text
[Agent Emits Tool Call]
          |
          v
[Runtime Harness: PreToolUse]
          |
          +--> Invokes: python ../scripts/along_hook.py --runtime antigravity --event PreToolUse
                     |
                     v (JSON payload over stdin)
          [Adapter parses HookEvent]
                     |
                     v
          [HookEngine evaluates Gates]
                     |
         +-----------+-----------+
         |                       |
     (Violation)              (Clean)
         |                       |
   [Mode == enforce?]            v
      /         \         [GateResult: ALLOW]
    YES          NO (shadow)     |
     |            |              v
     v            +--------> [Audit Log Appended]
 [GateResult: DENY]              |
     |                           v
     +---------------------> [Adapter formats JSON stdout]
                                 |
                                 v
                     [Runtime Harness receives output]
                                 |
                     +-----------+-----------+
                     |                       |
                (ALLOW: runs tool)      (DENY: blocks tool & reports reason to model)
```

---

## 4. Invariants & Failure Modes

1. **No Git Hooks by Default Invariant** (supersedes "Zero Git Hooks", see ADR `opt-in-git-hooks-supersede-zero-git-hooks`):
   - Nothing Along installs by default (`along-init`, `along update`, `install.*`) writes `.git/hooks/*`. Standard Git commands stay untouched until the user opts in.
   - Opt-in: `along hooks install --git` writes `pre-commit` and `commit-msg` shims that run `along gates check --hook <name>`. A foreign hook already in place is moved to `<hook>.pre-along` and run first; with `core.hooksPath` (husky, lefthook) nothing is written and the command to add to the manager is printed. `--uninstall` removes the shims and restores the previous hooks. The checks are read-only.
   - Merge drivers (`along git setup`) are per-clone `.git/config` entries, not hooks. See ADR `projection-merge-driver-defers-recompile`.
   - Runtime gates (`PreToolUse`, `Stop`) remain the primary layer, but they exist only where the host runtime loads Along's hooks. The portable baseline is the CI job `along gates check --ci`, plus the opt-in git hooks. Each gate declares its layers in `enforcement: [runtime, git, ci]`; `along hook verify` prints the matrix.
2. **Deterministic Rejection over Silent Overwrites**:
   - In `enforce` mode, gate violations result in an immediate `deny` decision with actionable remediation text. Silent auto-replacement is avoided so LLMs receive explicit negative feedback and learn rule adherence.
3. **Dual-Mode Governance (Shadow vs Enforce)**:
   - Configurable per-gate in `.along/config.json` or via `ALONG_HOOK_MODE`.
   - In `shadow` mode, violations emit a stderr warning and append a structured event to `.along/diagnostics/hooks_audit.jsonl` without halting tool execution.
4. **Hermetic Test Guarantees**:
   - All hook engine unit tests target temporary directories (`tempfile.mkdtemp()`).
   - The test suite strictly asserts that `.along/diagnostics/` is never written into the repository root during automated testing.
5. **Fail-Open & Crash Resilience Invariant**:
   - Runtime lifecycle hooks must never cause agent paralysis (tool interception deadlock) due to missing scripts, unhandled exceptions, or non-Along workspaces.
   - Hook commands use direct, robust script paths rather than fragile shell inline scripts (`python -c`).
   - If `along_hook.py` encounters any unexpected internal error or runs in a workspace without Along protocol files, it catches the exception and exits `0` (`ALLOW`), ensuring tools are never blocked by infrastructure faults.
   - A missing `ruamel.yaml` with no usable `uv` is such a fault: `along_hook.py` calls `bootstrap.ensure_deps(missing_exit_code=0)`, because Claude Code reads exit code `2` as "block the tool".
   - When the interpreter lacks the dependencies, `bootstrap.ensure_deps()` re-executes into a cached runtime environment (`~/.along/venv`, override with `ALONG_VENV`). It is built once with `uv`, stamped with the dependency specs in `.along-deps`, and rebuilt when those specs change. `uv run --with` is only the fallback when the build fails, so a hook does not re-resolve dependencies on every tool use.
   - The re-exec marker (`ALONGKIT_BOOTSTRAPPED`) guards one re-exec only: `ensure_deps()` clears it once the dependencies import, so an engine started from a bootstrapped process (an installer running `install_manifest.py` under a bare interpreter) still bootstraps itself instead of exiting `2`.
   - `~/.along/venv` carries the runtime dependencies only. The repository's own test hook (`.along/scripts/test.py`) first calls `bootstrap.ensure_project_env()`, which re-executes through `uv run --project <repo>` so the suite gets the `dev` group (the dashboard stack); without `uv`, tests that need that stack are skipped with a reason.
   - On Windows, global hook commands use forward slashes only (`python C:/Users/<user>/.along/bin/along_hook.py ...`). Claude Code runs hooks through Git Bash, which strips backslashes; Python then cannot open the script and exits `2`, blocking every tool. Re-running `along update --global` rewrites old entries in place.
6. **Global Hook Centralization & Recursive Monorepo Purge**:
   - Since Along v3.9.2, runtime hooks are installed globally in user home configurations (`~/.gemini/config/hooks.json`, `~/.claude/settings.json`, `~/.codex/hooks.json`).
   - Consumer repositories and all nested subprojects are recursively purged of legacy local hooks during `along update`.
   - Out-of-band execution via `along update` in an external OS terminal serves as the canonical disaster recovery path if runtime hooks are ever damaged.

## 4a. Protocol Rule Enforcement Audit

Every rule of the managed `AGENTS.md` block, classified: **a** enforced by a gate or test, **b** mechanically checkable but not yet enforced, **c** judgment-only. Layers come from the catalogue `enforcement` field (`along hook verify` prints the full matrix). Class-a rules are one line in `AGENTS.md` with a gate tag; the gate's error message carries the detail.

| Rule | Class | Enforced by | Layer |
| :--- | :--- | :--- | :--- |
| Nearest context boundary, precedence, session-start reading | c | - | - |
| Subproject localization (edits under a subproject `.along/` need its issue or a root umbrella with `parent:` children) | a | `subproject_boundary` | runtime |
| Uninitialized subprojects need `/along-init` | c | - | - |
| Zero-manual-merge of projections | a | `projection_protection`, merge drivers (`along git setup`) | runtime, git, ci |
| Append-only `HISTORY.md` merge | a | `along git setup` writes `merge=union` | git |
| Untracked exports | a | `untracked_exports` | git, ci |
| Context isolation | c | - | - |
| No code without issue | a | `require_active_issue` | runtime |
| Commit binding | a | `commit_issue_binding` | runtime, git, ci |
| No AI co-authors | a | `commit_no_ai_coauthor` | runtime, git, ci |
| Canonical keys, reference by key (front-matter reference fields) | a | `entity_reference_integrity` (a path or unknown key is dangling) | runtime, git, ci |
| Never delete a referenced entity; rename / supersede | a | `entity_reference_integrity`, `along issue rename` / `supersede` | runtime, git, ci |
| ADRs never edited, only superseded | c | - | - |
| Issue lifecycle (`done/` placement) | a | `issue_lifecycle` | git, ci |
| Auto-entity creation | c | - | - |
| Stable entry point | a | `stable_entry_point` (also `along kb-sync --check`) | git, ci |
| Portable links | a | `portable_links` (also `along kb-sync --check`) | git, ci |
| Fact grounding, doc blast radius, routing tree | c | - | - |
| Fast retrieval | a | `fast_retrieval` | runtime |
| Manual document lock | a | `doc_manual_lock` | runtime, git, ci |
| Managed rule packs (`.along/rules/**/*.md`) not edited by agents | a | `rule_pack_protection` (runtime: file tools and shell writes, `along rules ...` excepted; git / ci: body matches the managed header hash) | runtime, git, ci |
| Lifecycle hooks first, token hygiene, post-change review | c | - | - |
| Checklist: tests (edits under `.along/scripts/` count as source edits) | a | `test_before_stop` | runtime |
| Checklist: session log | a | `wrap_before_stop` | runtime |
| Checklist: projections | a | `projection_sync_before_stop`, projection freshness in `along gates check` | runtime, git, ci |
| Checklist: file integrity, review, reconciliation, HISTORY, compaction | c | - | - |
| Environment isolation (no global installs) | a | `cli_safety` | runtime |
| Workspace containment | a | `workspace_containment` | runtime |
| Anti-deletion, anchored edits | c | - | - |
| No stubs or skeletons | a | `anti_stub_injection` | runtime, git, ci |
| Clean ASCII (incl. BOM) | a | `typography`, `along sanitize` | runtime, git, ci |
| Code fence languages | a | `code_fence_language` | git, ci |
| File content via tools only | a | `cli_safety` | runtime |
| Verify written files | c | - | - |
| Hermetic tests | a | `tests/test_zz_hermetic_suite.py` (this repo) | ci |
| Inquiry read-only | a | `require_plan_approval` | runtime |
| Complexity escalation to `along-team` | c | - | - |
| along-team step loop and reviews | a | `team_step_active`, `team_reviews_before_stop`, `along scratch purge` / `along wrap` refusal | runtime |
| ADR question at wrap | a | `along wrap --decisions / --no-decisions` (required) | runtime |
| Windows-safe filenames | a | `windows_safe_filenames` | git, ci |
| `ISSUES.md` compact | a | `along context-budget --check`, `tests/test_context_budget.py` | ci |
| No secrets in tracked files | a | `no_tracked_secrets` | git, ci |

## 5. Runtime Capability Matrix

Gates are mechanical only where the runtime loads Along's `PreToolUse`/`Stop` hooks. Everywhere else the protocol in `AGENTS.md` is advisory: the agent must self-apply every gate-tagged rule and route tests, commits, entity changes, and wrap through the `along` CLI. `along doctor` prints the level for the runtime it runs in (`alongkit.runtime`).

| Runtime | Along skills | Along runtime hooks | Enforcement |
| :--- | :--- | :--- | :--- |
| Claude Code | auto (`~/.claude/skills`) | yes (`~/.claude/settings.json`, nested schema) | mechanical once `along hook install` ran; `along doctor` also checks the schema and the last hook heartbeat |
| Google Antigravity | auto (`~/.gemini`) | yes (`~/.gemini/config/hooks.json`) | mechanical once installed |
| OpenAI Codex | auto (`~/.codex`) | yes (`~/.codex/hooks.json`) | mechanical once installed |
| Claude Cowork | not loaded (Cowork reads plugins from the claude.ai account, not `~/.claude`) | no (Cowork ignores `settings.json`; plugin hooks are tracked in `feat--cowork-plugin-skill-packaging`) | advisory |
| OpenCode, Cursor, plain shell, human | rules only | no | advisory |

Advisory runtimes are still covered at commit time by the portable layer: `along hooks install --git` (opt-in, local) and the CI job `along gates check --ci` enforce the gates whose catalogue entry lists `git` / `ci` (typography, conflict markers, anti-stub on added lines, issue binding, AI co-author trailers, projection freshness, rule pack integrity), regardless of which agent or human made the commit.

Runtime detection (`entities.detect_agent`) honours `--agent` and `ALONG_AGENT` first; Claude Cowork is recognised by `ALONG_RUNTIME=cowork`, or by `CLAUDE_CODE_HOST_HTTP_PROXY_PORT` together with a `/sessions/` home (markers observed 2026-09-27, heuristic).

### Working from Claude Cowork

Cowork runs the agent in a cloud container plus a Linux VM on the user's machine, with connected folders mounted under `$HOME/mnt/<folder>`:

1. Connect the repository folder in the Claude desktop app.
2. Grant delete permission for the folder before any git write. Without it the mount allows create and rename but not unlink, so `git status`, `git add`, and `git commit` leave a stale `.git/index.lock` and `along wrap` cannot move an issue into `done/`. `along doctor` warns when the lock exists.
3. Run the CLI with a supported interpreter, for example `uv run --python 3.12 --with ruamel.yaml python scripts/along_exec.py <command>` (Python 3.10 is supported from v4.3.0; see `bug--py310-fstring-syntax-error`).
4. Do not run `along worktree` from the VM: the repository is on the host filesystem (`core.symlinks=false`), so worktree metadata would record VM paths. `along doctor` warns on a cross-OS mount.
5. Pass `--agent cowork` only when detection reports `unknown`.
