---
protocol: along
protocol_version: "2.2.21"
slug: runtime-enforcement-of-prose-rules
type: feat
status: in-progress
priority: critical
created: 2026-09-02
updated: 2026-09-07
agent: antigravity
tags: [architecture, runtimes, hooks, gates, security, mechanical-enforcement, transcript]
milestone: v4.0.0-runtime-gates-and-worktree-isolation
blocked_by: []
related: [feat--programmatic-integrity-gates-and-git-guard, feat--systemic-anomaly-circuit-breaker]
---

# Programmatic Runtime Enforcement for Along Protocols and Skills via Lifecycle Hooks

## 1. Problem Statement & Failure Analysis

Passive prose rules in `AGENTS.md`, `CLAUDE.md`, and `skills/*/SKILL.md` suffer from systemic decay during real-world agent execution:
1. **Context Window Attention Dilution**: As agent transcripts grow past 20k-50k tokens, instruction weight diminishes exponentially. Probabilistic LLMs cut corners under token and reasoning pressure.
2. **Path of Least Resistance**: Models bypass multi-step procedures (e.g. creating an issue before editing, running automated tests after modifying code, or performing `along-wrap` before stopping) when there is zero mechanical resistance.
3. **Premature Termination**: Agents habitually output conversational summaries ("I have completed the changes") and terminate the execution turn without running automated tests, updating `.along/ISSUES/`, or recording session logs.
4. **File Corruption and Banned Characters**: Models introduce non-ASCII typographic characters (em-dash U+2014, curly quotes, ellipsis U+2026, NBSP) and dangerous shell commands (heredocs `<<EOF`, inline `python -c` file writers) despite explicit rules against them.

Prose instructions are suggestions; runtime hooks are deterministic mechanical barriers. To guarantee protocol compliance, Along must intercept agent actions at runtime and mechanically gate tool execution and turn termination.

---

## 2. Technical Insights from Reference Frameworks

1. **Harmonist (`GammaLabTechnologies/harmonist`)**:
   - Implements "mechanical protocol enforcement" with zero external runtime dependencies using pure Python.
   - Enforces checkpoints (`beforeShellExecution`, `afterFileEdit`, `subagentStart`, `sessionStart`).
   - Uses session markers and state checks to prevent an agent turn from completing if mandatory steps (QA verification, memory updates) were skipped.
2. **Claude Code Hooks (`code.claude.com/docs/en/hooks`)**:
   - Intercepts lifecycle events (`PreToolUse`, `PostToolUse`, `Stop`).
   - Uses exit codes: `exit 0` permits execution, `exit 2` blocks execution and feeds `stderr` back to the model as an error message.
   - Configured via `.claude/settings.json` or `~/.claude/settings.json`.
3. **Antigravity Hooks (`antigravity.google/docs/hooks`)**:
   - Supports `PreToolUse`, `PostToolUse`, `PreInvocation`, `PostInvocation`, and `Stop`.
   - Communicates via JSON over stdin/stdout.
   - `PreToolUse` returns `{"decision": "deny" | "allow" | "ask", "reason": "...", "overwrite": {...}}`.
   - `Stop` returns `{"decision": "continue", "reason": "..."}` to block turn termination and force protocol completion.
4. **OpenAI Codex Hooks (`learn.chatgpt.com/docs/hooks`)**:
   - Configured via `.codex/hooks.json` or `config.toml`.
   - Supports `PreToolUse`, `PostToolUse`, and `Stop` with exit code 2 blocking.
5. **Superset (`superset.sh`)**:
   - Employs git worktree isolation and lifecycle scripts (setup/teardown) to isolate agent modifications and prevent dirty-tree race conditions.
6. **Akto Atlas (`ai-security-docs.akto.io`)**:
   - Demonstrates endpoint agentic security: runtime guardrails operate at `PreToolUse` (preventive block) and `Stop` (audit and compliance verification).

---

## 3. Architecture: Along Unified Hook & Gate System

To avoid code duplication across IDEs, Along implements a unified core engine with thin runtime adapters:

```
+-------------------------------------------------------------------------+
|                          Runtime Hook Layers                            |
|  Antigravity (.agents/hooks.json)   | Claude Code (.claude/settings.json)|
|  Codex (.codex/hooks.json)          | Cursor / CLI Wrappers             |
+-------------------------------------+-----------------------------------+
                                       |
                                       v
+-------------------------------------------------------------------------+
|                Unified CLI Driver: scripts/along_hook.py                |
|   --runtime [antigravity|claude|codex] --event [PreToolUse|PostToolUse|Stop]
|   Parses stdin payload -> maps to canonical HookEvent                   |
|   Executes Gate Pipeline                                                |
|   Formats output response (JSON stdout vs exit code 2 + stderr)         |
+-------------------------------------------------------------------------+
                                       |
                                       v
+-------------------------------------------------------------------------+
|                       alongkit.hooks Core Engine                        |
|                                                                         |
|  1. State Manager (alongkit.hooks.state):                               |
|     Tracks .along/.hook_state.json (mutations, tests, active issue)     |
|                                                                         |
|  2. PreToolUse Gates (alongkit.hooks.gates):                            |
|     - IssueAnchorGate: Blocks source file edits without active issue    |
|     - InquiryReadOnlyGate: Blocks edits on questions / inquiry prompts  |
|     - TypographyGate: Blocks writes containing forbidden unicode chars  |
|     - CliSafetyGate: Blocks heredocs, inline writes, unvetted installs  |
|     - CommitGuardGate: Enforces issue slug binding in git commit        |
|                                                                         |
|  3. PostToolUse Handlers:                                               |
|     - SyntaxCheckHandler: Compiles modified Python/JS/TS files          |
|     - StateUpdateHandler: Records edit timestamps and test outcomes     |
|                                                                         |
|  4. Stop Gates:                                                         |
|     - TestStopGate: Blocks turn finish if code edited but tests skipped |
|     - WrapStopGate: Blocks turn finish if along-wrap was omitted        |
+-------------------------------------------------------------------------+
```

---

## 4. Detailed Specification of Mechanical Gates

### Gate 1: Mandatory Issue Anchoring (`IssueAnchorGate`)
- **Trigger**: `PreToolUse` on `write_to_file`, `replace_file_content`.
- **Target Filter**: Non-exempt files (project source code, scripts, configuration).
- **Whitelist**: Files inside `.along/ISSUES/`, `.along/SESSIONS/`, `.along/DECISIONS.md`, `.git/`, and scratchpad directories.
- **Rule**: At least one issue file in `.along/ISSUES/` must have `status: in-progress`.
- **Action on Violation**: Block execution (`deny` / `exit 2`).
- **Remediation Message**: "Mandatory Issue Anchoring Violation: You cannot modify project code without an active issue. Run 'python scripts/along_exec.py issue create' or set status to in-progress in an existing issue file first."

### Gate 2: Clean Typography & ASCII Sanitization (`TypographyGate`)
- **Trigger**: `PreToolUse` on `write_to_file`, `replace_file_content`.
- **Scan**: Inspect incoming replacement chunk or file content string in tool arguments.
- **Pattern**: Detect U+2014/U+2013 (em/en-dash), U+201C/U+201D/U+00AB/U+00BB (curly quotes/guillemets), U+2026 (ellipsis), U+00A0/U+202F/U+200B (NBSP/ZWSP), U+2022 (bullet).
- **Action on Violation**: Block execution (`deny` / `exit 2`).
- **Remediation Message**: "Typography Gate Violation: Detected forbidden non-ASCII characters. Replace with standard ASCII equivalents ('-', '\"', ''', '...') before writing."

### Gate 3: Shell Safety & Content Invariance (`CliSafetyGate`)
- **Trigger**: `PreToolUse` on `run_command`.
- **Scan**: Inspect `CommandLine` for forbidden patterns:
  - Heredocs: `<<\s*['"]?EOF['"]?`
  - Inline code file writers: `python -c ".*open\(.*['\"][wa]['\"].*\)"`
  - Large inline writes: `echo "..." > file` or `printf "..." > file`
  - Destructive unstaged git wipes without prompt: `git reset --hard`, `git clean -fdx`
  - Unauthorized global package managers: `pip install` (outside active venv), `npm install -g`, `choco`, `winget`
- **Action on Violation**: Block execution (`deny` / `exit 2`).
- **Remediation Message**: "CLI Safety Gate Violation: Forbidden command pattern or file content over CLI detected."

### Gate 4: Commit Message Issue Binding (`CommitGuardGate`)
- **Trigger**: `PreToolUse` on `run_command`.
- **Scan**: If command begins with `git commit`, inspect `-m` commit message.
- **Rule**: Commit message must match `[type--slug]` or bind to the currently active issue slug.
- **Action on Violation**: Block execution (`deny` / `exit 2`).
- **Remediation Message**: "Commit Gate Violation: Commit message must include the active issue key [type--slug]."

### Gate 5: Inquiry Read-Only Gate (`InquiryReadOnlyGate`)
- **Trigger**: `PreToolUse` on `write_to_file`, `replace_file_content`, mutating git commands.
- **Condition**: Current turn user prompt exhibits interrogative or verification intent (e.g. status inquiries, explanations, audits).
- **Rule**: Agents must output a structured read-only audit report first; mutations require explicit user confirmation.
- **Action on Violation**: Block execution (`deny` / `exit 2`).
- **Remediation Message**: "Inquiry Read-Only Gate Violation: Cannot modify files during an inquiry turn. Output an audit report and ask for user confirmation first."

### Gate 6: Quality Gate on Stop (`TestStopGate`)
- **Trigger**: `Stop` event (agent attempt to terminate turn).
- **Condition**: `.along/.hook_state.json` indicates project code files were modified during the current session, but no test runner execution was recorded AFTER the latest modification timestamp.
- **Action on Violation**: Refuse stop (`decision: continue` in Antigravity, `exit 2` in Claude/Codex).
- **Remediation Message**: "Stop Gate Violation: Code modifications were made during this turn, but automated tests have not been executed. Run repository tests (e.g. 'python .along/scripts/test.py') before completing the turn."

### Gate 7: Session Wrap Gate on Stop (`WrapStopGate`)
- **Trigger**: `Stop` event.
- **Condition**: Code modifications occurred, tests passed, but neither a session log (`.along/SESSIONS/<YYYY>/<date>--<slug>.md`) was created/updated nor `along-wrap` was executed.
- **Action on Violation**: Refuse stop (`decision: continue` / `exit 2`).
- **Remediation Message**: "Stop Gate Violation: Mandatory Session Wrap checklist incomplete. Record session log in .along/SESSIONS/, synchronize issues, and append to .along/HISTORY.md before finishing."

---
## 5. Dual-Mode Governance: Shadow Mode vs Enforce Mode

To prevent breaking existing workflows and to audit false positives before introducing hard blocks, the hook engine supports per-gate and global execution modes:

1. **Configuration (`.along/config.json` or environment variable `ALONG_HOOK_MODE`)**:
   ```json
   {
     "hooks": {
       "mode": "enforce",
       "record_transcript": false,
       "gates": {
         "typography": "enforce",
         "cli_safety": "enforce",
         "issue_anchor": "enforce",
         "commit_guard": "shadow",
         "stop_guard": "shadow"
       }
     }
   }
   ```
2. **Behavior in Shadow Mode**:
   - The gate executes full evaluation logic.
   - When a violation is detected:
     - The violation is recorded in `.along/diagnostics/hooks_audit.jsonl` with timestamp, tool name, arguments, and violation reason.
     - A non-blocking warning banner is emitted to stderr: `[ALONG HOOK: SHADOW] Would deny execution: <reason>`.
     - The tool execution or stop event is permitted (`decision: allow` / `exit 0`).
3. **Rollout Strategy**:
   - Pure syntactic and corruption gates (`typography`, `cli_safety`) deploy directly in `enforce` mode.
   - Workflow state gates (`commit_guard`, `stop_guard`) deploy initially in `shadow` mode to measure telemetry, then graduate to `enforce`.

### 5.1. Opt-In Full Call Transcription (`--transcript`)

To support deep offline analysis, post-run diagnostics, and debugging without bloating Git history or adding unneeded I/O overhead on standard runs, the hook system provides an opt-in transcription mode:

- **Activation**: Explicit CLI flag `--transcript` (e.g. `along --transcript <cmd>`, `along_hook.py --transcript`) or configuration `hooks.record_transcript: true`.
- **Storage Location (Gitignored)**: Stored strictly in gitignored directories: `.along/diagnostics/transcripts/<slug>.jsonl` or `.along/.session/<slug>/transcript.jsonl`. Raw transcripts MUST NOT be checked into Git.
- **Secret Redaction Invariant**: The transcriber applies automatic pattern-based masking for Bearer tokens, private keys (`ghp_`, `sk-`), and passwords before recording tool arguments and outputs to disk.
- **Offline Analysis CLI**: Provide CLI analysis subcommands:
  - `along transcript view <slug>`: Displays formatted call tree with tool names, parameters, and timings.
  - `along transcript stats <slug>`: Summarizes tool call frequency, failure rates, and error distributions.

---
## 6. Testing Strategy & Verification Architecture

Testing must be split into three distinct levels to ensure speed, determinism, and real runtime verification:

```
+-------------------------------------------------------------------------+
| Level 3: E2E Runtime Tests (Claude Code / Codex + Ollama Local Model)   |
| - Runs real agent CLI with ANTHROPIC_BASE_URL / OPENAI_BASE_URL         |
| - Fast CPU-friendly model (qwen2.5-coder:1.5b / qwen3:1.7b)             |
| - Proves real runtime invokes hook, receives exit 2, and halts edit     |
+-------------------------------------------------------------------------+
                                    ^
+-------------------------------------------------------------------------+
| Level 2: Runtime Configuration & Discovery Tests                        |
| - Validates generated .claude/settings.json, .agents/hooks.json         |
| - Verifies schema compliance, executable paths, and discovery           |
+-------------------------------------------------------------------------+
                                    ^
+-------------------------------------------------------------------------+
| Level 1: Deterministic Contract Tests (tests/test_hooks.py)             |
| - Fast (<10ms), hermetic, 100% deterministic (no LLM, no network)       |
| - Feeds mock JSON payloads on stdin, verifies stdout JSON & exit codes  |
| - Primary quality gate executed on every pre-commit and test run        |
+-------------------------------------------------------------------------+
```

### Critical Distinction: Model SDK vs Agent Runtime Harness
- Standard API client SDKs (`anthropic-python`, `openai-python`) are purely transport clients: they send HTTP requests to `/v1/messages` and do NOT manage agent lifecycle hooks, `.claude/settings.json`, or tool execution loops.
- The **Agent Runtime Harness** (Claude Code CLI `claude`, Codex CLI `codex`, Antigravity) is the entity that reads hook configurations, intercepts tool calls, invokes `along_hook.py`, and inspects exit codes.
- E2E tests target the real Agent Runtime Harness by passing environment overrides:
  - Claude Code: `ANTHROPIC_BASE_URL=http://localhost:11434` (utilizing Ollama native Anthropic API compatibility)
  - Codex: `OPENAI_BASE_URL=http://localhost:11434/v1` and `OPENAI_API_KEY=ollama`
  - Model: lightweight CPU model with tool-calling capabilities (`qwen2.5-coder:1.5b` or `qwen3:1.7b`).

---

## 7. Implementation Phases & Deliverables

- [ ] **Phase 1: Core Hook Framework (`alongkit.hooks`)**:
  - Implement `alongkit/hooks/models.py` (canonical event data class).
  - Implement `alongkit/hooks/state.py` (thread-safe `.along/.hook_state.json` tracker).
  - Implement `alongkit/hooks/config.py` (dual-mode governance: shadow vs enforce).
  - Implement `alongkit/hooks/adapters.py` (Antigravity JSON vs Claude/Codex exit code adapters).
- [ ] **Phase 2: Gate Implementations (`alongkit.hooks.gates`)**:
  - Implement `issue_anchor.py`, `inquiry_read_only.py`, `typography.py`, `cli_safety.py`, `commit_guard.py`, `stop_guard.py`.
- [ ] **Phase 3: CLI Driver (`scripts/along_hook.py`)**:
  - Entry point accepting `--runtime`, `--event`, and `--mode` flags.
  - Comprehensive audit logging in `.along/diagnostics/hooks_audit.jsonl`.
  - Opt-in `--transcript` flag: streams sanitized tool-call JSONL to gitignored `.along/diagnostics/transcripts/<slug>.jsonl`.
- [ ] **Phase 4: Installer & Config Generators**:
  - Add `along hook install` command and integrate into `along-init` and `along-update`.
  - Automatically generate `.agents/hooks.json`, `.claude/settings.json`, `.codex/hooks.json`.
  - Add `along transcript view <slug>` and `along transcript stats <slug>` CLI subcommands for offline inspection.
- [ ] **Phase 5: Automated Test Suite**:
  - Level 1 & 2: `tests/test_hooks.py` and `tests/test_hooks_install.py` (hermetic, fast, zero-dependency).
  - Level 3: `scripts/along_test_runtime_e2e.py` (isolated E2E runner supporting Ollama backends).
- [ ] **Phase 6: Documentation & Knowledge Base**:
  - Create `docs/topic--runtime-hooks-and-gates.md`.
  - Update `docs/INDEX.md`, `README.md`, and `AGENTS.md`.
