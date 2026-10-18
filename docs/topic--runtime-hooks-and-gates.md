---
protocol: along
slug: runtime-hooks-and-gates
title: Runtime Lifecycle Hooks & Mechanical Gates
type: architecture
created: 2026-09-11
updated: 2026-10-17
tags: [hooks, gates, runtime, enforcement, antigravity, claude, codex, typography, cli-safety, destructive-command, attribution]
sources:
  - path: scripts/alongkit/attribution.py
  - path: scripts/alongkit/repochecks.py
  - path: scripts/alongkit/hooks/engine.py
  - path: scripts/along_hook.py
  - path: scripts/alongkit/hookpreflight.py
  - path: scripts/alongkit/repo.py
  - path: scripts/alongkit/hooks/adapters/claude.py
  - path: scripts/alongkit/hooks/adapters/codex.py
  - path: scripts/alongkit/hooks/turnstate.py
  - path: scripts/alongkit/hooks/deletion.py
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
|     - CliSafetyGate: warns on heredocs, inline writers, global installs |
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
- `HookEventType`: Enumerates `PreToolUse`, `PostToolUse`, `PreInvocation`, `PostInvocation`, `Stop`, and `UserPromptSubmit`.
- `HookEvent`: Carries normalized event data (`tool_name`, `tool_args`, `workspace_root`, `conversation_id`, `step_idx`).
- `GateDecision`: Categorizes decisions into `allow`, `deny`, `ask`, and `force_ask`.
- `GateResult`: Carries the final decision, remediation message, gate identifier, and optional argument overwrites.

### 2.2 Gate Implementations (`alongkit.hooks.gates`)
1. **`TypographyGate`** (`typography`):
   - Runs at commit only (`enforcement: [git, ci]`: pre-commit, CI and `along lint`); there is no runtime hook on file writes.
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
   - Scans command strings for heredocs (`<<EOF`), inline Python file writers (`python -c "open('...', 'w')"`) and unauthorized global package managers (`npm install -g`). It is a warning in every profile (`cli_safety`); `git reset --hard` and `git clean -f` belong to `destructive_command` (see 2.11).
   - The echo/printf file-writer rule (`alongkit.hooks.shellwrite`) is quote-aware: it flags only `echo` / `printf` / `Write-Output ... > file`, `>> file`, `1> file`, `&> file` and `echo ... | tee file`. `2>/dev/null`, `>/dev/null`, `2>&1`, `&>/dev/null`, `>&2`, other pipes and a `>` inside quotes pass.
4. **`DocRoutingComplianceGate`** (`doc_routing_compliance`):
   - Intercepts file mutation tools (`write_to_file`, `replace_file_content`, etc.).
   - Enforces the Along Documentation Routing Tree: `README.md` must remain a high-level overview.
   - Forbids deep code fences (>50 lines) and oversized coding convention or technical reference sections (>50 lines) directly in `README.md`.
   - Forbids `AGENTS.md` from referencing `README.md` as the conventions source of truth instead of `docs/topic--<slug>.md` or `docs/INDEX.md`.
   - Enforced across runtime hooks, git `pre-commit`, `--ci`, `along kb sync`, and `along doctor`.

### 2.3 Declarative Extension & Traceability Matrix
Beyond hardcoded Python gates, Along provides an extensible, declarative YAML gate catalogue (`default_gates.yaml` and `.along/rules/gates.yaml`) enforcing 33 canonical gates, 11 of them git/CI-only commit-time checks (typography, anti-stub, AI co-author trailers, code fences, links, entry point, filenames, exports, issue lifecycle, session records, secrets; run on demand by `along lint`). Runtime gates include `require_plan_approval` (file-tool target path before the write, `git status` at turn end), `destructive_command`, `worktree_env_readiness` and `workspace_containment`, which keeps file, search and shell-cwd paths inside the workspace; see [Declarative Gates](./topic--declarative-gates-and-traceability.md). The catalogue is verified bi-directionally against prose badges (`[gate: <id>]`) via `along hook verify`.
For full specification and architecture, see [Declarative Gate Engine & Traceability Matrix](./topic--declarative-gates-and-traceability.md).


### 2.4 Runtime Adapters (`alongkit.hooks.adapters`)
- **`AntigravityAdapter`**: Translates Google Antigravity JSON payloads (`toolCall.name`, `toolCall.args`) to `HookEvent`, returning JSON stdout with `allow`/`deny` decisions.
- **`ClaudeCodeAdapter`**: Translates Anthropic Claude Code payloads to `HookEvent`, mapping `Write` to `write_to_file`, `Edit`/`MultiEdit`/`NotebookEdit` to `replace_file_content`, `Bash`/`PowerShell` to `run_command`, and `Read`/`Grep`/`Glob` to the read tools; `session_id` becomes the event's session id. Responses: exit 0 for allow; exit 2 with the remediation on `stderr` for a denial; exit 0 with `hookSpecificOutput.permissionDecision: "ask"` for an ASK (the user decides); on `Stop` with `stop_hook_active: true` a denial is reported once as a `systemMessage` instead of forcing another continuation.
- **Claude Code hook schema**: `along hook install --runtime claude [--global]` writes the nested schema Claude Code reads, `{"matcher": ..., "hooks": [{"type": "command", "command": ..., "timeout": 30}]}`, for `PreToolUse` (`Write|Edit|MultiEdit|NotebookEdit|Bash|PowerShell|Read|Grep|Glob`), `PostToolUse` (edits and `ExitPlanMode`), `Stop` and `UserPromptSubmit` (no matcher; records the time of the user's last message, see 2.8). Legacy flat `{matcher, command}` entries, which Claude Code ignores, are migrated in place; foreign hooks are kept.
- **`CodexAdapter`**: Translates OpenAI Codex CLI and headless harness JSON payloads to HookEvent, mapping write_file/create_file to write_to_file, edit_file/patch to replace_file_content, and shell/bash/exec to run_command. Formats exit code 0 for allow, and exit code 2 with the remediation message written to stderr for gate denials.
- **`GenericCliAdapter`**: Translates generic CLI tool invocations, terminal proxy wrappers, Cursor (`.cursor/hooks.json`), and OpenCode to `HookEvent`. Normalizes arguments across tool types, supports plain command strings as fallback `run_command`, and formats exit code 0 for allow or exit code 2 with stderr remediation message for gate denials.

### 2.5 Execution Pipeline & Dispatcher (`alongkit.hooks.engine` & `scripts/along_hook.py`)
- `HookEngine`: Evaluates incoming events sequentially against all registered gates (both built-in and declarative).
- `along_hook.py`: Universal CLI driver handling process I/O, error recovery, adapter dispatch, and `verify` audit.
- **Activation** (`alongkit.hookpreflight`, stdlib only, before the dependency bootstrap): the gates apply only inside an Along context. A context is an Along installation (`repo.is_installed`): a `.along/` holding Along state (`repo.STATE_ENTRIES`: `ISSUES`, `HISTORY.md`, `DECISIONS`, `.protocol-version`, ...; an empty `.along/` or one with only what Along writes on its own - `diagnostics/`, `scripts/`, `artifacts/`, `.session/`, `.migration-backup/` - is not), a legacy `.agents/` with Along entities, or a declared root. A bare `AGENTS.md` does not activate anything: it is a tool-agnostic convention and, in a subfolder, a folder guide. Outside a context the hook allows and exits without loading dependencies; `Read`/`Grep`/`Glob` inside the root and outside `docs/` and the state directory are answered the same way. Progress notes of the bootstrap are suppressed in hooks, since hook stderr lands in every tool result.
- **Declared roots** (`repo.declared_root`): a directory whose Along state lives elsewhere, for example a nested personal repository, declares it with `<!-- along-root: .local -->` in its `AGENTS.md`, or without touching shared files in `~/.along/config.json`:

  ```json
  { "context_roots": [ { "workspace": "D:/work/product/src", "root": ".local" } ] }
  ```

  State then resolves to `<root>/.along/` (`repo.state_dir`), while gates keep evaluating paths against the declaring directory; paths inside the state directory are matched as `.along/...`.
- Subcommand `along hook install`: Scaffolds runtime hook configurations (`.agents/hooks.json` for Antigravity, `.claude/settings.json` for Claude Code, `.codex/hooks.json` for OpenAI Codex, `.cursor/hooks.json` for Cursor). Accepts `--runtime {antigravity,claude,codex,cursor,all}`. Also turns off AI commit attribution where the runtime documents a key for it (see 2.7).
- Subcommand `along run <cmd...>` (and `along_hook.py run <cmd...>`): Command proxy wrapper evaluating `run_command` through `HookEngine` prior to execution. Provides mechanical gate enforcement in environments without native PreToolUse lifecycle hooks (OpenCode, CI, and external terminals).
- Subcommand `along hook verify`: Audits bi-directional traceability between prose badges and YAML gates.

### 2.6 End-of-Turn Result Check (`alongkit.hooks.turnstate`)
Gates do not predict harm from command text: whether a shell command writes is not decidable before it runs (`debt--gate-simplification`). `require_plan_approval` (catalogue `event: [PreToolUse, Stop]`) judges facts instead:
- **Before a file-writing tool** (`PreToolUse`): the target path. It holds a write to a repository file that is not a planning or session artifact while no plan is approved. Shell commands are never checked before they run.
- **Baseline** (`UserPromptSubmit`): `turnstate.snapshot` records `git status --porcelain -uall` plus content hashes of the dirty files as `turn_baseline` in the session activity trace.
- **At turn end** (`Stop`): `turnstate.changed_since` compares the working tree with the baseline. Paths the turn changed outside Along state (`.along/**`, except `.along/scripts/**`) and planning artifacts, with no approved plan, hold the turn once: `PLAN_REQUIRED [gate: require-plan-approval]: this turn changed <files> ... Ask the user: approve (...) or revert (...)`. Files already dirty before the turn and unchanged are not attributed to it.
- **One continuation**: Claude Code's `stop_hook_active` keeps the hold to a single continuation. Antigravity still gets ASK for file-tool holds.
- **Commits** (`along commit`, `git commit`) are not held by this gate.
- **Process hangs** are handled by runner timeouts; there is no circuit breaker and Stop gates do not wait on one.

### 2.7 Commit Attribution Policy (`alongkit.attribution`)
Agent runtimes append `Co-Authored-By:` trailers naming themselves (for example `Claude ... <noreply@anthropic.com>`). GitHub resolves the trailer email to an account and lists the vendor as a repository contributor; undoing it later needs a history rewrite and a force-push. The `commit_no_ai_coauthor` gate (`enforcement: [git, ci]`) and the attribution settings keep the trailers out in three layers:

| Layer | Where | What it does |
| :--- | :--- | :--- |
| Runtime config | `along hook install --runtime claude` | Sets `attribution.commit = ""` and legacy `includeCoAuthoredBy = false` in `settings.json`; other keys are kept. |
| Runtime config | `along hook install --runtime cursor --global` | Sets `attribution.attributeCommitsToAgent = false` in `~/.cursor/cli-config.json`. |
| Reconcile | `along hook attribution [--runtime claude\|cursor\|all]`, `install.ps1` / `install.sh`, every `/along-update` run | `reconcile_attribution` writes only the attribution keys above, only for runtime homes that already exist, even when the install is up to date. `--no-hooks` skips it in `/along-update`. |
| Gate | `commit_no_ai_coauthor` (`predicates.check_ai_coauthor`) | Rejects a commit whose message carries an AI co-author trailer, at commit time (commit-msg hook, CI, `along lint`). Human co-authors pass. |
| Commit engine | `/along-commit` | Strips AI co-author trailers from the message before committing. |

Codex and Antigravity document no attribution key; for them the gate and `/along-commit` are the only layers. Opt out per repository with `.along/config.json`:

```json
{ "commits": { "allow_ai_coauthor": true } }
```

### 2.8 Agent-Session Binding & Plan Approval (`alongkit.session`)
Several agent sessions may work in one repository at once, so gates never read a repository-wide "active issue". Each session is bound to one issue:

- **Binding**: `along start <slug>` writes `.along/.session/bindings/<runtime>--<session_id>.json` (`slug`, `context`, `plan_approved`, `approved_slug`). The session id comes from the hook payload (`session_id`, antigravity conversation id) and, for CLI calls, from `CLAUDE_CODE_SESSION_ID`, `ANTIGRAVITY_CONVERSATION_ID`, `CODEX_SESSION_ID` or `ALONG_SESSION_ID` (+ `ALONG_SESSION_RUNTIME`). Bindings live in the outermost `.along/` of the workspace (up to the git top, never `~/.along`); `context` names the `.along/` the issue belongs to, so a session bound to a subproject issue is visible at the root.
- **Resolution** (`session.resolve_active_session`): `ALONG_ISSUE_SLUG` (runner) > own binding > the single in-progress blackboard not bound to another session > none. Several unbound candidates are `ambiguous`: gates refuse and point at `along start <slug>`. A single candidate names the issue, but its blackboard's `plan_approved` counts only for the session bound to it (or a runner's `ALONG_ISSUE_SLUG`): an unbound session with a known id never inherits the approval of a blackboard whose session ended. Runtimes that pass no session id keep it.
- **Plan approval**: `along start` binds with `phase: planning`, `plan_approved: false`. Approval is recorded per session when the user accepts a plan in Claude Code (`PostToolUse` on `ExitPlanMode`; the plan text from `tool_input.plan` is written into the blackboard `plan.md`, or kept as `pending_plan` in the binding until the first `along start`), or by `along plan approve [<slug>] [--plan-file <path>]` after the user's explicit yes, which is refused while `plan.md` is still the scaffold (`session.is_scaffold_plan`); an approval given before `along start` carries over to the first bound slug, and an `ExitPlanMode` approval carries over to a newly started slug until the user's next message (the plan is recorded under the new slug). `along start --approved` is for scripted runs.
- **User reply check** (`session.record_user_prompt`, `session.check_cli_approval`): the Claude Code `UserPromptSubmit` hook records the time of the user's last message in `.along/.session/prompts/<key>.json` (it does not bind the session). CLI approvals (`along plan approve`, `along start --approved`, `along scratch approve|phase --approve|update --approve`) are refused when the plan file changed after that message ("plan changed after the user's last message; show it and wait for a reply"); with no recorded message they pass as `approved_via: cli-unverified`. Bindings record `approved_via` (`exit-plan-mode` | `cli` | `cli-unverified`), `approved_at` and `plan_sha256`. The denial hint reads: "Call EnterPlanMode, write the plan, then ExitPlanMode. If plan mode is unavailable, show the plan in chat and wait for the user's reply; run 'along plan approve' only after that reply."
- **What the plan gate holds** (see 2.6): file-tool writes to repository files before approval, and at turn end the files the turn changed according to `git status`. Shell commands are never classified before they run. File-tool writes to `.along/ISSUES|RISKS|SPIKES|SESSIONS|.session|diagnostics` and planning artifacts (`implementation_plan.md`, `walkthrough.md`, `living_plan.md`) pass, and the end-of-turn check ignores Along state under `.along/` (except `.along/scripts/`), so an issue can be written and started before a plan exists.
- **Unbound sessions**: `require_plan_approval` and `test_before_stop` hold only sessions bound to an issue (`along start`, or `ALONG_ISSUE_SLUG` from a runner). A repository that wants unbound sessions held too sets `enforce_unbound: true` for those gates in `.along/rules/gates.yaml` (this repository does). `require_active_issue` is unaffected: source edits still need an in-progress issue.
- **Completion tokens**: `along wrap` purges the blackboard and every binding of the wrapped slug. The wrapping session, if its plan for that slug was approved, keeps a token in its binding (`completed: [{slug, approved_at, wrapped_at}]`; `slug` and approval cleared). The token is ignored after 72 h (by `wrapped_at`), survives `along start <other>`, and leaves with the binding (`along session gc`). `along scratch purge` leaves no token. Tokens and closeout approvals serve `along session close` and the `wrapped_work_uncommitted` warning; commits are not held by `require_plan_approval`.
- **Shell parsing** (`alongkit.hooks.shellparse`): only `split_segments()` and `words()` remain, used to find the explicit forms of `destructive_command` (2.11) and entity deletions (`entity_deletion_protection`). Command substitutions become the placeholder word `SUBST`. There is no read-only or verification classification, so tests and builds run in every phase without a special case.
- **Session root**: the hook evaluates against the session's project, not the agent's current shell cwd (which follows `cd`). With Claude Code, `CLAUDE_PROJECT_DIR` anchors the root whenever the cwd lies inside it (`repo.find_session_root`), so session bindings and containment survive a `cd` into a nested `.along/` context.
- **Entity reference integrity**: the Stop predicate runs only after an entity file changed and blocks only problems absent at `HEAD` (`gitgates.baseline_entity_problems` validates a `git archive` snapshot of every `.along/` entity dir); problems already committed are left to `along doctor --entities`. Schema findings on archived issues (`.along/ISSUES/done/`: enums, dates, slug, dangling milestone) are warnings marked `(archived issue)`, so an older archive never fails `along update` or `issue sync`; dangling issue references stay errors there too. `along doctor --fix` is not read-only for the plan gate. References resolve upward (enclosing contexts up to the outermost one below home, crossing nested git / submodule boundaries; the snapshot check adds the working-tree keys of contexts above the git top, `gitgates.outer_context_keys`) and downward (nested subproject contexts, `entities.descendant_entity_keys`) and sideways (sibling contexts of the same git repository, `entities.sibling_entity_keys`).
- **Repository-level `.along/.session/state.json`** is read only for runtimes that pass no session id; `purge` removes it when it points at the purged slug.
- **Housekeeping**: `along plan status`, `along session bindings`, `along session gc [--dry-run]` (bindings older than 72 h or without a blackboard). `along scratch purge` / `along wrap` remove the slug's bindings (`along wrap` keeps the wrapping session's completion token).
- **Activity trace** (`test_before_stop`): per session in `.along/diagnostics/activity/<key>.json`; edits under `.along/` are not source edits, and documentation edits (Markdown anywhere, anything under a `docs/`) count only when the gate sets `count_docs: true` (this repository does, since its suite tests Markdown). Under `count_docs: true`, doc-only edits can be satisfied by a scoped run of Markdown-facing tests (`along test --doc` or `python .along/scripts/test.py --doc`, running declared `doc_tests: [...]` from `.along/rules/gates.yaml`) rather than the full suite. The activity trace tracks `last_doc_test_time` separately from `last_test_time`. Only what the gates let through is recorded: an edit on `PostToolUse` (the tool succeeded), a test run on `PreToolUse` after every gate allowed it, so changes made outside the session or writes a gate rejected never count. Where `.along/scripts/test.py` exists only `along test` / that script count as a test run; raw runners are named in the Stop message. The same trace holds `turn_baseline` (2.6).
- **Execution trace** (`session.trace_event`): the bound issue's `.along/.session/<slug>/execution_trace.md` records, in direct and role-based mode, every repository edit (`PostToolUse`, except `.along/.session/**` and diagnostics; repeated edits of a path collapse to `(xN)`), enforced gate denials (`engine.py` -> `predicates.record_gate_denial`), plan recorded / approved, phase, step and retry changes (`session.update_state`), and test runs with their result from `along test` and the wrap / commit test gate (`gates.run_repository_tests`). Raw runners are not traced (no Bash `PostToolUse`). Unbound sessions write nothing; the trace keeps the newest 400 entries. See [Session Lifecycle](./topic--session-lifecycle.md).
- **Session event ledger** (ADR-2026-10-05--session-event-ledger-feeds-telemetry): the same capture points append one versioned record `{schema, ts, session, slug, kind, path, path_kind, ok}` (`kind`: edit, test, plan, approve; `path_kind`: source, docs, state; `path` relative to the workspace root) to `.along/.session/<slug>/events.jsonl` (`session.record_event`, append only, at most 2000 events per issue, oldest edits dropped first). It is the source of truth for attribution and closeout readiness (`alongkit.closeout`); the session log keeps it as `### Attributed Files`. A failed append is reported on stderr and counted in `.along/diagnostics/ledger_errors.json`, which blocks that issue's closeout. With a runner Tracer, the PostToolUse span event carries the same record (`along.session.key`, `along.event.*`, `along.issue.slug`; fail-open).
- **Test reuse** (`alongkit.testruns`): every test run is recorded with the tree hash of the working tree (`git write-tree` through a throwaway index; `.along/` except `.along/scripts/`, KB projections and `__pycache__` left out) in `.along/diagnostics/test_runs.json`. The Stop gate (`test_before_stop`) as well as `along wrap`, `along commit` and `along bump` reuse the last run on the same tree when it was green (`testruns.green_run_for(repo_root, tree_hash)`), allowing clean or reverted trees to pass immediately without re-running tests. `along bump` records a green run for the post-bump tree so `along wrap` can reuse it. `along test` always runs.
- **Diagnostics** (`hooks_audit.jsonl`, activity traces, `hook_heartbeat.json`) are machine-local: `.along/diagnostics/` carries its own `*` `.gitignore`. They go to the resolved state directory (`repo.diagnostics_dir`); without one they go to `~/.along/diagnostics/workspaces/<path>/`. The hooks never create a `.along/` of their own.

### 2.9 along-team Step Discipline & Wrap Record
- `along scratch init` creates a `role-based` blackboard (`--mode direct` opts out); `along start` creates a `direct` one. `[gate: team-step-active]` denies source edits in a role-based session while no step is `in-progress`; `[gate: team-reviews-before-stop]` blocks the turn end while a `passed` step lacks `reviews/step-N.md`.
- `along scratch purge` and `along wrap` refuse while role-based steps are open or reviews are missing; `--force --reason` / `--force-reason` records why in `execution_trace.md`. `along scratch fallback <slug> --reason` switches to single-agent execution with the reason in the trace.
- `along wrap` requires `--decisions ADR-...` or `--no-decisions`, writes (or extends) today's session log with `issues_completed: [<type>--<slug>]`, the decisions answer and the blackboard record (plan, step table, research, trace, reviews), and purges the blackboard only after its transaction committed. It refuses a blackboard whose `plan.md` is the scaffold unless `--force-reason`.
- One archive path (`lifecycle.write_session_record`, `lifecycle.archive_and_purge`) serves `along wrap`, `along scratch purge` and `along issue done`: no blackboard is deleted without its record; scaffold placeholders are not rendered; a forced purge's reason goes into the record; a second record on the same day is appended as `## Blackboard Record (<n>, <ts>)`.
- `wrap_before_stop` (Stop): every issue closed as `done` today (local date) must be in `issues_completed` of a session log of today. `along doctor` warns about orphan blackboards (no binding, issue closed or missing), stale bindings and issues in progress with no session bound.
- `session_record_append_only` (git, ci; `gitgates.check_session_records`, also run by `along commit`): a change never removes or rewrites lines inside a `## Blackboard Record` section of a committed session log; the Summary stays editable.

### 2.10 Stop Gates, Subproject Boundary & Gate Tiers
- **`projection_sync_before_stop`** (`predicates.check_projection_sync_before_stop`): compares content (the compiled board vs `ISSUES.md`, not mtimes) in every context and rewrites a stale board itself, reporting `Auto-synced stale projection(s): ...` on stderr. It never blocks.
- **`wrapped_work_uncommitted`** (Stop): lists in full only the current session's issues (its completion tokens, its bound slug, issues whose ledger names this session); other sessions' issues collapse to "N other session issue(s) have uncommitted attributed files ('along session list')". Without a session id everything is listed.
- **`subproject_boundary`** (`predicates.check_subproject_boundary`): decided from the target file path and the session binding, never the shell cwd. A session bound to a subproject issue may write root `.along/` entities only on that issue's parent chain (`_bound_subproject_owns_root_entity`, `_parent_chain_slugs`); an umbrella issue covers its children at any depth (`ISSUES/` and `done/`).
- **Gate tiers** (`hooks.config.GATE_TIERS`): `invariant` gates (`workspace_containment`, `no_tracked_secrets`, `projection_protection`, `rule_pack_protection`, `entity_deletion_protection`) always enforce, cannot be shadowed or disabled by repository config and have no bypass. `advisory` gates (`wrapped_work_uncommitted`, `projection_sync_before_stop`) always run in shadow. All other gates are `process` gates that follow the configured mode.
- **Bypass accountability** (`alongkit.bypass`): `along commit -n --reason`, `along wrap -n --reason` (or `--force-reason`), `along wrap --force-reason` (when a check is actually forced), `along bump -n --reason`, `along scratch fallback --reason` and `along scratch purge --force --reason` need a non-empty reason. Where user messages are recorded (Claude Code `UserPromptSubmit`), the gate must have failed in this session and the user must have replied after the failure; otherwise the bypass is allowed and marked `unverified`. Every bypass goes to the session trace and to `.along/diagnostics/hooks_audit.jsonl` (`decision: bypass`); a commit also carries an `Along-Bypass: <gate>; <verified|unverified>; <reason>` trailer.
- **Audit record**: each `hooks_audit.jsonl` entry ends with `target`, the command or file path the gate judged (redacted with the telemetry Redactor, cut to 200 chars). A shadow-mode record carries `decision: "warn"`, not the raw `deny`, so an advisory gate such as `wrapped_work_uncommitted` no longer shows up as denials.
- **Gate stats** (`alongkit.gatestats`): `along gates stats [--since YYYY-MM-DD]` prints per-gate blocked / warned / bypassed counts from `hooks_audit.jsonl`, plus "Repeated blocks": identical (gate, target) blocks >= 3 in one conversation, a loop indicator (entries without `target` fall back to the reason). `along doctor` warns about gates set to shadow by config and about the most-bypassed gates (a gate bypassed about as often as it blocks is wrong or too strict).

### 2.11 Destructive Command Gate (`alongkit.hooks.deletion`)
`destructive_command` (`predicates.check_destructive_command`, `PreToolUse` on shell tools) looks only at explicit forms, segment by segment:
- Recursive deletes: `rm -r` / `-rf` / `--recursive`, `Remove-Item -Recurse` (`ri`, PowerShell `rm` / `rd` / `del` with `-Recurse`), `del /s`, `erase /s`, `rd /s`, `rmdir /s`.
- History rewrites: `git clean -f`, `git reset --hard`, `git push --force` (`-f`, `--force-with-lease`).

When it holds:
- A delete target is empty, holds an unexpandable variable or a command substitution, is outside the repository (children of the system temp directory excepted), is or contains the repository root, or holds uncommitted work (`git status --porcelain` non-empty under it). Ignored files such as `node_modules` do not count; a non-existent path passes.
- `git reset --hard` when tracked files are modified; `git clean -f` when its dry run (`git clean -n`) would remove something; `git push --force` always.

The message reads `DESTRUCTIVE [gate: destructive-command]: '<segment>': <why>. Fix: <fix>.` Decision: ASK in interactive sessions, DENY in autonomous ones (`ALONG_AUTONOMOUS=1` or Claude Code `bypassPermissions`). Everything else passes; scripts and other tools are out of reach by design (the container covers them, see `debt--gate-simplification`).

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
   - In `shadow` mode, violations emit a stderr warning and append a structured event (`decision: "warn"`) to `.along/diagnostics/hooks_audit.jsonl` without halting tool execution.
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

Every rule of the managed `AGENTS.md` block, classified: **a** enforced by a gate or test, **b** mechanically checkable but not yet enforced, **c** judgment-only. Layers come from the catalogue `enforcement` field (`along hook verify` prints the full matrix). Class-a rules are one line in `AGENTS.md` with a gate tag; the gate's error message carries the detail. Commit-time checks (typography, anti-stub, AI co-author, code fences, links, entry point, filenames, secrets) carry no tag: `AGENTS.md` lists them on one line as checked by `along lint` (pre-commit and CI), not while you work.

Since `debt--agents-md-core-slimming` the managed block is a core of at most 6 KB: where state lives, issue anchoring, every gate tag with one line, and class-c rules as one-liners. The full wording of every rule below, plus situational procedure (completion checklist, documentation routing tree, concurrency and merge, parallel closeout, along-team routing, tool-use rules), lives in [Along Protocol Reference](./topic--along-protocol.md). Its source is `skills/along-init/protocol-reference.md`; `along init` / `along update` render it into each FULL root's `docs/`. `tests/test_scaffold_profiles.py` checks that no gate tag leaves the core and no named rule leaves the reference.

| Rule | Class | Enforced by | Layer |
| :--- | :--- | :--- | :--- |
| Nearest context boundary, precedence, session-start reading | c | - | - |
| Subproject localization (edits under a subproject `.along/` need its issue or a root umbrella with `parent:` children) | a | `subproject_boundary` | runtime |
| Subproject boundary: only a nested `.git` or a user-run `along init` (never a manifest folder) | a | `subproject_boundary` ignores bare manifests; `along update` creates no context; `along doctor` lists unmarked nested installs | runtime |
| Zero-manual-merge of projections | a | `projection_protection`, merge drivers (`along git setup`) | runtime, git, ci |
| Append-only `HISTORY.md` merge | a | `along git setup` writes `merge=union` | git |
| Untracked exports | a | `untracked_exports` | git, ci |
| Context isolation | c | - | - |
| No code without issue | a | `require_active_issue` | runtime |
| Commit binding | a | `commit_issue_binding` | runtime, git, ci |
| No AI co-authors | a | `commit_no_ai_coauthor` | git, ci |
| Canonical keys, reference by key (front-matter reference fields) | a | `entity_reference_integrity` (a path or unknown key is dangling) | runtime, git, ci |
| Never delete a referenced entity; rename / supersede | a | `entity_reference_integrity`, `along issue rename` / `supersede` | runtime, git, ci |
| ADRs never edited, only superseded | c | - | - |
| Issue lifecycle (`done/` placement) | a | `issue_lifecycle` | git, ci |
| Session log Blackboard Record is append-only | a | `session_record_append_only` (also `along commit`) | git, ci |
| Auto-entity creation | c | - | - |
| Stable entry point | a | `stable_entry_point` (also `along kb-sync --check`) | git, ci |
| Portable links | a | `portable_links` (also `along kb-sync --check`) | git, ci |
| Fact grounding, doc blast radius, routing tree | c | - | - |
| Fast retrieval (`along kb-search` recommended) | c | - | - |
| Manual document lock | a | `doc_manual_lock` | runtime, git, ci |
| Managed rule packs (`.along/rules/**/*.md`) not edited by agents | a | `rule_pack_protection` (runtime: file tools only; shell edits are caught at commit, where git / ci check that the body matches the managed header hash) | runtime, git, ci |
| Lifecycle hooks first, token hygiene, post-change review | c | - | - |
| Checklist: tests (edits under `.along/scripts/` count as source edits) | a | `test_before_stop` | runtime |
| Checklist: session log | a | `wrap_before_stop` | runtime |
| Checklist: uncommitted wrapped work | a | `wrapped_work_uncommitted` | runtime |
| Checklist: projections | a | `projection_sync_before_stop`, projection freshness in `along gates check` | runtime, git, ci |
| Checklist: file integrity, review, reconciliation, HISTORY, compaction | c | - | - |
| Environment isolation (no global installs) | a | `cli_safety` (warning) | runtime |
| Workspace containment | a | `workspace_containment` | runtime |
| Explicit recursive deletes and history rewrites (`rm -rf`, `git reset --hard`, `git clean -f`, `git push --force`) on unrecoverable targets | a | `destructive_command` (ASK interactive, DENY autonomous) | runtime |
| Anti-deletion, anchored edits | c | - | - |
| No stubs or skeletons | a | `anti_stub_injection`, `along lint` | git, ci |
| Clean ASCII (incl. BOM) | a | `typography`, `along sanitize`, `along lint` | git, ci |
| Code fence languages | a | `code_fence_language` | git, ci |
| File content via tools only | a | `cli_safety` (warning) | runtime |
| CLI black-box invariance | c | - (Treat Along CLI as strict opaque black box; no engine source inspection in consumer repos) | - |
| Verify written files | c | - | - |
| Hermetic tests | a | `tests/test_zz_hermetic_suite.py` (this repo) | ci |
| Plan approval before repository changes (file-tool target path; files changed by the turn at Stop) | a | `require_plan_approval` | runtime |
| Complexity escalation to `along-team` | c | - | - |
| along-team step loop and reviews | a | `team_step_active`, `team_reviews_before_stop`, `along scratch purge` / `along wrap` refusal | runtime |
| Bounded subagent step prompt footprint | a | `bounded_prompt_gate` (`[gate: bounded-prompt-gate]`, hard limit 32 KB, soft warning 16 KB, attention leak detection) | runtime |
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

---

## 6. Gate Strictness Profiles per Model Tier

Complex procedural ceremonies and rigid review checklists impose significant token overhead. To accommodate varying model capabilities, Along decouples the immutable **state layer** from the **control layer** via named Gate Strictness Profiles.

### 6.1 Named Profiles

| Profile | Target Tier | Behavior |
| :--- | :--- | :--- |
| `strict` | Standard & Junior models | Full procedural ceremony, mandatory plan approval for all mutations, low complexity escalation thresholds, full 9-step completion checklist. |
| `standard` | Default baseline | Preserves default Along behavior: all 33 catalogue gates at their default severity, role-based escalation for multi-file/cross-system tasks. |
| `light` | Frontier / Strong models | Streamlines procedural ceremony: warns rather than blocks on procedural gates (`require_plan_approval`, `code_fence_language`, `team_step_active`), compacts the Stage Completion Checklist to 5 core invariants, and allows direct execution with user alignment. |

Profile-specific prose is declared in the protocol sources, not patched in by code: a line `<!-- profile: light -->` (or `<!-- profile: !light -->`, or a comma list) opens a section that only the named profiles keep (or that every other profile keeps), and `<!-- /profile -->` closes it. `alongkit.scaffold.render_profile_sections` resolves the sections and strips the markers for both the `AGENTS.md` core and `docs/topic--along-protocol.md`. `along init` and `along update` both render for the resolved active profile.

### 6.2 State-Layer Invariance

Regardless of active profile (`strict`, `standard`, or `light`), immutable state integrity gates and safety invariants ALWAYS evaluate to `block`:
- **State-Layer Gates**: `require_active_issue`, `projection_protection`, `test_before_stop`.
- **Invariant Safety Gates**: `workspace_containment`, `no_tracked_secrets`, `rule_pack_protection`, `entity_deletion_protection`.

### 6.3 Resolution Hierarchy

Active profile resolves through the following precedence order:
1. **Session Binding**: `along start <slug> --profile <p>` or `.along/.session/<slug>/state.json`.
2. **Environment Variable**: `ALONG_PROFILE=<p>`.
3. **Repository Configuration**: `.along/config.json` or `.along/config.yaml` (`{"profile": "<p>"}`).
4. **Default Baseline**: `standard`.

### 6.4 Inspection & Visibility

- `along doctor`: Reports active profile, resolution source, strictness counts, and the complete gate strictness matrix.
- `along hook verify`: Shows active profile in the traceability report header and annotates each gate with its active strictness mode (`[BLOCK]`, `[WARN]`, `[OFF]`).
- `along init --profile <p>`: Scaffolds `AGENTS.md` with rules tailored to the selected profile.
