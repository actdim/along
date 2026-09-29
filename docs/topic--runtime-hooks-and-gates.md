---
protocol: along
slug: runtime-hooks-and-gates
title: Runtime Lifecycle Hooks & Mechanical Gates
type: architecture
created: 2026-09-11
updated: 2026-09-29
tags: [hooks, gates, runtime, enforcement, antigravity, claude, codex, typography, cli-safety, circuit-breaker, attribution]
sources:
  - path: scripts/alongkit/attribution.py
  - path: scripts/alongkit/circuit.py
  - path: scripts/alongkit/hooks/engine.py
  - path: scripts/along_hook.py
  - path: scripts/alongkit/hooks/adapters/claude.py
  - path: scripts/alongkit/hooks/adapters/codex.py
---

# Runtime Lifecycle Hooks & Mechanical Gates

## 1. System Topology & Overview

Passive prose instructions in `AGENTS.md` and `skills/*/SKILL.md` decay as agent conversation transcripts expand. When context windows fill, probabilistic LLMs cut corners, emit forbidden non-ASCII typography (em-dashes, curly quotes, guillemets), write heredocs over shell tools, or attempt to terminate turns prematurely without executing tests.

The Along Runtime Hook and Gate System establishes deterministic, programmatic interception at the agent harness boundary. Rather than relying on fragile in-process monkey-patching or invasive Git-level hooks (`.git/hooks/*`), Along hooks directly into host agent runtime lifecycle events (`PreToolUse`, `PostToolUse`, `Stop`) supported natively by Google Antigravity, Claude Code, and OpenAI Codex.

```
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
Beyond hardcoded Python gates, Along provides an extensible, declarative YAML gate catalogue (`default_gates.yaml` and `.along/rules/gates.yaml`) enforcing 15 canonical gates (including `require_plan_approval` for inquiry read-only locks, `circuit_breaker`, and `worktree_env_readiness`), verified bi-directionally against prose badges (`[gate: <id>]`) via `along hook verify`.
For full specification and architecture, see [Declarative Gate Engine & Traceability Matrix](./topic--declarative-gates-and-traceability.md).


### 2.4 Runtime Adapters (`alongkit.hooks.adapters`)
- **`AntigravityAdapter`**: Translates Google Antigravity JSON payloads (`toolCall.name`, `toolCall.args`) to `HookEvent`, returning JSON stdout with `allow`/`deny` decisions.
- **`ClaudeCodeAdapter`**: Translates Anthropic Claude Code CLI payloads to `HookEvent`, mapping `Write`/`WriteFile` to `write_to_file`, `Edit`/`EditFile` to `replace_file_content`, and `Bash` to `run_command`. Formats exit code 0 for allow, and exit code 2 with the remediation message written to `stderr` for gate denials.
- **`CodexAdapter`**: Translates OpenAI Codex CLI and headless harness JSON payloads to HookEvent, mapping write_file/create_file to write_to_file, edit_file/patch to replace_file_content, and shell/bash/exec to run_command. Formats exit code 0 for allow, and exit code 2 with the remediation message written to stderr for gate denials.
- **`GenericCliAdapter`**: Translates generic CLI tool invocations, terminal proxy wrappers, Cursor (`.cursor/hooks.json`), and OpenCode to `HookEvent`. Normalizes arguments across tool types, supports plain command strings as fallback `run_command`, and formats exit code 0 for allow or exit code 2 with stderr remediation message for gate denials.

### 2.5 Execution Pipeline & Dispatcher (`alongkit.hooks.engine` & `scripts/along_hook.py`)
- `HookEngine`: Evaluates incoming events sequentially against all registered gates (both built-in and declarative).
- `along_hook.py`: Universal CLI driver handling process I/O, error recovery, adapter dispatch, and `verify` audit.
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

---

## 3. Data Flow & Execution Workflow

When an agent emits a tool call, the execution loop flows through the hook harness:

```
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

1. **Zero Git Hooks Invariant**:
   - Along strictly forbids `.git/hooks/*` and custom Git merge drivers.
   - All protocol enforcement occurs strictly in the agent runtime harness layer (`PreToolUse`, `Stop`). Standard Git commands executed by developers remain untouched.
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
6. **Global Hook Centralization & Recursive Monorepo Purge**:
   - Since Along v3.9.2, runtime hooks are installed globally in user home configurations (`~/.gemini/config/hooks.json`, `~/.claude/settings.json`, `~/.codex/hooks.json`).
   - Consumer repositories and all nested subprojects are recursively purged of legacy local hooks during `along update`.
   - Out-of-band execution via `along update` in an external OS terminal serves as the canonical disaster recovery path if runtime hooks are ever damaged.

## 5. Runtime Capability Matrix

Gates are mechanical only where the runtime loads Along's `PreToolUse`/`Stop` hooks. Everywhere else the protocol in `AGENTS.md` is advisory: the agent must self-apply every gate-tagged rule and route tests, commits, entity changes, and wrap through the `along` CLI. `along doctor` prints the level for the runtime it runs in (`alongkit.runtime`).

| Runtime | Along skills | Along runtime hooks | Enforcement |
| :--- | :--- | :--- | :--- |
| Claude Code | auto (`~/.claude/skills`) | yes (`~/.claude/settings.json`) | mechanical once `along hook install` ran |
| Google Antigravity | auto (`~/.gemini`) | yes (`~/.gemini/config/hooks.json`) | mechanical once installed |
| OpenAI Codex | auto (`~/.codex`) | yes (`~/.codex/hooks.json`) | mechanical once installed |
| Claude Cowork | not loaded (Cowork reads plugins from the claude.ai account, not `~/.claude`) | no (Cowork ignores `settings.json`; plugin hooks are tracked in `feat--cowork-plugin-skill-packaging`) | advisory |
| OpenCode, Cursor, plain shell, human | rules only | no | advisory |

Runtime detection (`entities.detect_agent`) honours `--agent` and `ALONG_AGENT` first; Claude Cowork is recognised by `ALONG_RUNTIME=cowork`, or by `CLAUDE_CODE_HOST_HTTP_PROXY_PORT` together with a `/sessions/` home (markers observed 2026-09-27, heuristic).

### Working from Claude Cowork

Cowork runs the agent in a cloud container plus a Linux VM on the user's machine, with connected folders mounted under `$HOME/mnt/<folder>`:

1. Connect the repository folder in the Claude desktop app.
2. Grant delete permission for the folder before any git write. Without it the mount allows create and rename but not unlink, so `git status`, `git add`, and `git commit` leave a stale `.git/index.lock` and `along wrap` cannot move an issue into `done/`. `along doctor` warns when the lock exists.
3. Run the CLI with a supported interpreter, for example `uv run --python 3.12 --with ruamel.yaml python scripts/along_exec.py <command>` (Python 3.10 is supported from v4.3.0; see `bug--py310-fstring-syntax-error`).
4. Do not run `along worktree` from the VM: the repository is on the host filesystem (`core.symlinks=false`), so worktree metadata would record VM paths. `along doctor` warns on a cross-OS mount.
5. Pass `--agent cowork` only when detection reports `unknown`.
