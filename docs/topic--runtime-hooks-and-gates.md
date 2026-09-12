---
protocol: along
slug: runtime-hooks-and-gates
title: Runtime Lifecycle Hooks & Mechanical Gates
type: architecture
created: 2026-09-11
updated: 2026-09-11
tags: [hooks, gates, runtime, enforcement, antigravity, typography, cli-safety]
sources:
  - path: scripts/alongkit/hooks/engine.py
  - path: scripts/along_hook.py
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
Beyond hardcoded Python gates, Along provides an extensible, declarative YAML gate catalogue (`default_gates.yaml` and `.along/rules/gates.yaml`) enforcing 11 canonical gates, verified bi-directionally against prose badges (`[gate: <id>]`) via `along hook verify`.
For full specification and architecture, see [Declarative Gate Engine & Traceability Matrix](./topic--declarative-gates-and-traceability.md).

### 2.4 Execution Pipeline & Dispatcher (`alongkit.hooks.engine` & `scripts/along_hook.py`)
- `HookEngine`: Evaluates incoming events sequentially against all registered gates (both built-in and declarative).
- `along_hook.py`: Universal CLI driver handling process I/O, error recovery, adapter dispatch, and `verify` audit.
- Subcommand `along hook install`: Scaffolds `.agents/hooks.json` in the target repository.
- Subcommand `along hook verify`: Audits bi-directional traceability between prose badges and YAML gates.

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
