---
protocol: along
slug: runtime-enforcement-of-prose-rules
date: 2026-09-11
agent: antigravity
summary: "Implemented runtime-agnostic lifecycle hook engine (alongkit.hooks), Antigravity adapter, .agents/hooks.json, typography/CLI gates, unit test suite, and KB documentation"
milestone: v4.0.0-runtime-gates-and-worktree-isolation
issues_advanced: []
issues_completed: [feat--runtime-enforcement-of-prose-rules]
decisions: []
risks_logged: []
spikes_conducted: []
branch: main
commit: unknown
---

# Session Log: 2026-09-11 - Runtime Enforcement of Prose Rules & Antigravity Hooks

## 1. Objectives & Context

Implementation of `[feat--runtime-enforcement-of-prose-rules]` under milestone `v4.0.0-runtime-gates-and-worktree-isolation`:
- Establish deterministic mechanical barriers intercepting agent actions at runtime instead of relying solely on passive prose rules in `AGENTS.md`.
- Extract a central, runtime-agnostic core engine (`alongkit.hooks`) with normalized event models and a stateless gate pipeline.
- Implement the reference adapter for Google Antigravity (`alongkit.hooks.adapters.antigravity`), translating protojson camelCase stdin/stdout and scaffolding `.agents/hooks.json`.
- Decompose other runtime environments into dedicated subtasks (`feat--runtime-hooks-claude-code`, `feat--runtime-hooks-codex`, `feat--runtime-hooks-cursor-opencode`).
- Add comprehensive hermetic unit tests in `tests/test_hooks_core.py` and publish architectural documentation in `docs/topic--runtime-hooks-and-gates.md`.

## 2. Key Architecture & Changes

1. **Subtasks Dispatched (`.along/ISSUES/`)**:
   - Created `feat--runtime-hooks-claude-code.md` for Anthropic Claude Code CLI adapter (`.claude/settings.json`, exit code 2 contract).
   - Created `feat--runtime-hooks-codex.md` for OpenAI Codex adapter (`.codex/hooks.json`).
   - Created `feat--runtime-hooks-cursor-opencode.md` for Cursor and OpenCode wrappers.

2. **Core Hook Engine (`scripts/alongkit/hooks/`)**:
   - `models.py`: Canonical `HookEvent` (`PreToolUse`, `PostToolUse`, `Stop`) and `GateResult` (`allow`, `deny`, `ask`).
   - `gates.py`:
     - `TypographyGate`: Intercepts `write_to_file` and `replace_file_content` to block non-ASCII characters (em/en-dashes, curly quotes, guillemets, ellipsis glyphs, NBSP) based on `alongkit.typography`. Exempts localized directories (`locales/`, `i18n/`).
     - `ProjectionProtectionGate`: Blocks manual writes to compiled views (`.along/ISSUES.md`, `docs/INDEX.md`).
     - `CliSafetyGate`: Blocks dangerous shell patterns (`<<EOF`, inline Python file writers, destructive Git wipes).
   - `config.py`: Supports `enforce` vs `shadow` governance, logs audit records to `.along/diagnostics/hooks_audit.jsonl`, and supplies `install_antigravity_hooks()`.
   - `engine.py`: Pipeline runner evaluating `HookEvent` against active gates.

3. **Google Antigravity Reference Adapter**:
   - `alongkit/hooks/adapters/antigravity.py`: Parses camelCase JSON from stdin, maps tool arguments, and formats JSON stdout response (`{"decision": "deny" | "allow", "reason": ...}`).
   - Scaffolds `.agents/hooks.json` targeting `write_to_file`, `replace_file_content`, and `run_command`.

4. **Universal CLI Dispatcher & Routing**:
   - `scripts/along_hook.py`: Dispatches hook events and provides `along hook install [--dry-run]` command.
   - `scripts/along_exec.py`: Added `hook` and `hooks` routing.
   - `pyproject.toml`: Registered `along_hook.py` in wheel engine force-include manifest.

5. **Unit Tests & Documentation**:
   - `tests/test_hooks_core.py`: 15 unit tests covering typography blocking, projection protection, CLI safety, shadow mode audit logging, Antigravity JSON roundtrip, and CLI installation.
   - `docs/topic--runtime-hooks-and-gates.md`: Knowledge base article covering topology, components, data flow, and invariants.
   - Recompiled `docs/INDEX.md` via `along kb-sync`.

## 3. Quality & Verification Manifest

- Unit Tests: `python .along/scripts/test.py` -> 396 passed, 0 failed, 1 skipped.
- Typography: `along sanitize` -> 420 files scanned, zero banned characters.
- Link Integrity: `along kb-sync` -> 278 relative Markdown links verified on disk.
- Gate Execution Manifest:
  - File Integrity: EXECUTED (PASS)
  - Automated Tests: EXECUTED (PASS) [396 passed]
  - Diff Scope Audit: EXECUTED (PASS)
  - Requirement Traceability: EXECUTED (PASS) [REQ-1 to REQ-7]
  - Blast Radius: EXECUTED (PASS)
  - Documentation Parity: EXECUTED (PASS)
  - Clean Typography: EXECUTED (PASS)
