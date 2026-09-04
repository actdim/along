---
protocol: along
slug: programmatic-integrity-gates-and-git-guard
type: feat
status: open
priority: critical
created: 2026-09-04
updated: 2026-09-04
agent: antigravity
tags: [stability, gates, git, ast, runtime, inquiry-read-only, role-escalation]
milestone: v2.1.0-along
blocked_by: []
related: []
---

# Programmatic Code Integrity Gates, Git Self-Healing, and Role-Based Process Guards

## Problem Statement

Passive prose rules in `AGENTS.md` (such as "verify every file compiles before proceeding", "never run git commands concurrently", or "do not edit code on questions") have a high failure rate because probabilistic language models cut corners under token and reasoning pressure. This causes five critical failure modes:

1. **Broken Code Syntax on Disk**: Models make regex or imprecise string edits via `replace_file_content` or scratch scripts, leaving syntax errors (`IndentationError`, unterminated strings) unverified on disk. When the user or IDE diff widget accepts the chunk, broken code persists.
2. **Git Index Corruption on Windows**: Concurrent operations between background test runners and IDE Git watchers (VS Code `vscode.git`) trigger NTFS sharing violations, leaving `.git/index` truncated to 0 bytes (`fatal: .git/index: index file smaller than expected`) or locking the repository via stale `.git/index.lock`.
3. **Line Ending Drift**: Mismatches between CRLF on Windows and LF in patch strings cause line offsets to slide, leading to misaligned function bodies.
4. **Opportunistic Mutation on Inquiries**: When asked informational questions ("are all docs updated?", "is feature X implemented?"), agents exhibit a bias-to-act: instead of returning a read-only audit report, they make unprompted file edits in the background to "clean up" discrepancies before answering, breaking user trust and introducing untested changes.
5. **Monolithic Single-Agent Execution Bloat ("Колбаса")**: Complex tasks involving multi-directory traversals, library extractions, and multi-surface documentation updates are executed inside a single bloated context window. When token budget fills with test traces and diffs, reasoning degrades, resulting in chaotic patching.

## Architectural Solutions: Active Programmatic Gates & Process Enforcement

To reduce human friction and eliminate these failures, Along must implement active, non-bypassable runtime gates and process rules:

### 1. Inquiry Read-Only Invariance (Zero-Mutation Rule on Questions)
- **Protocol Rule (`AGENTS.md` / `protocol.md`)**:
  - If a user prompt has an interrogative or verification intent (questions about status, state, audit, or explanation: "is X done?", "why did Y fail?", "are all docs updated?"), calling write or modify tools (`replace_file_content`, `write_to_file`, `git commit`, file-mutating shell commands) is **STRICTLY PROHIBITED**.
  - The agent MUST output a structured read-only audit report:
    1. **Direct Answer**: Current factual status of the system.
    2. **Discrepancies / Findings**: Specific list of files, line numbers, and identified defects.
    3. **Proposed Remediation Plan**: Specific proposed changes without executing them.
    4. **Confirmation Request**: Ask for user approval ("Would you like me to proceed with these changes?").
  - File modifications are permitted ONLY after the user explicitly approves the proposal.
- **Runtime Hook (`.gemini/hooks/` PreToolUse)**:
  - Intercept tool calls in Antigravity: if the turn began with an inquiry and the agent attempts `replace_file_content` or `write_to_file`, abort the call with an error forcing the agent to output the audit report first.
- **Read-Only Role Enforcement**:
  - Delegate inspection tasks to the built-in `research` subagent, which physically lacks write tools and can never corrupt working tree files.

### 2. Mandatory Adaptive Complexity Escalation (`along-team` / Role-Based Execution)
- **Thresholds for Escalation**:
  - In `implementation_plan.md` and agent workflows, tasks that meet any of the following criteria MUST be routed to role-based execution (`along-team` or subagents) rather than executed monotonically in a single context:
    1. Scope touches more than 3 files or crosses subsystem boundaries.
    2. Modifies core shared engine packages (`scripts/alongkit/`).
    3. Triggers cross-package or cascading subproject blast radius.
    4. Involves architectural refactoring or protocol schema changes.
- **Execution Plan Requirement**:
  - The implementation plan template must include an explicit `Execution Mode` decision:
    - `Direct`: Allowed only for isolated 1-2 file edits.
    - `Role-Based (along-team)`: Required when complexity thresholds are met. Decomposes execution into isolated subagents: `Supervisor` (orchestration), `Research` (read-only audit), `Architect` (interface design), `Implementer` (scoped code edits), `Reviewer` (diff inspection and test verification).

### 3. Test Suite Pre-Flight Syntax Gate (`.along/scripts/test.py`)
- Before executing any test discovery or test runner, `.along/scripts/test.py` must run `python -m compileall -q scripts tests .along/scripts`.
- If any syntax or indentation error is detected, the runner must immediately halt with exit code 1 and emit a human- and agent-readable banner pointing to the exact file, line number, and error type.

### 4. Automated Git Index & Lock Self-Healing (`scripts/alongkit/repo.py` / `proc.py`)
- Provide a resilient Git executor `alongkit.proc.run_git(...)` that inspects repository health before and after Git operations:
  - Check if `.git/index` has length 0. If detected, automatically invoke `Remove-Item .git/index; git reset` to recover the index without losing unstaged work.
  - Check if `.git/index.lock` exists without an active owning `git.exe` process (stale lock). If stale, automatically unlink it.
  - Prevent concurrent Git operations between test runners and IDE file watchers on Windows NTFS.

### 5. Commit Quality Gate (`skills/along-commit/SKILL.md` & `scripts/along_commit.py`)
- Add a mandatory, non-bypassable pre-flight verification step in the commit pipeline:
  1. Syntax validation: `python -m compileall -q .`
  2. Typography check: `python scripts/sanitize_typography.py --check`
  3. Documentation link integrity: `python scripts/along_kb_sync.py --check`
- Reject commit creation immediately if any pre-flight check fails.

### 6. Deterministic AST Code Patching Subcommand (`scripts/along_exec.py patch`)
- Ban multi-line ad-hoc regex code slicing in scratch scripts.
- Introduce an AST-based helper in `along_exec.py`:
  - `python scripts/along_exec.py patch replace-func <target_file> <function_name> <replacement_code_file>`
  - Uses Python `ast` to parse both the target file and replacement code, locate the AST node, swap it, and verify that the resulting file compiles before writing back to disk.

### 7. PostToolUse Syntax Validation Hook (Antigravity Customization)
- Define an IDE lifecycle hook in `.gemini/hooks/` or `agy-customizations`:
  - Hook into `PostToolUse` for `replace_file_content` and `write_to_file`.
  - When the target file ends in `.py`, execute `python -m py_compile <target_file>`.
  - If it fails, report an immediate error to the agent to trigger automatic rollback/correction before user interaction.

### 8. Repository Line Ending Normalization (`.gitattributes`)
- Explicitly enforce `* text=auto eol=lf` across all text files to eliminate byte-offset drift during string replacements on Windows.

## Acceptance Criteria
- [ ] Protocol updated with `Inquiry Read-Only Invariance` rule in `AGENTS.md` and `skills/along-init/protocol.md`.
- [ ] Implementation plan template updated with mandatory `Adaptive Complexity Escalation` routing.
- [ ] `.gemini/hooks/` pre-tool hook blocks file modifications on inquiry prompts.
- [ ] `.along/scripts/test.py` includes a pre-flight `compileall` gate that halts on any syntax error before launching tests.
- [ ] `alongkit.proc` / `alongkit.repo` has automated detection and recovery for 0-byte `.git/index` and stale `.git/index.lock`.
- [ ] `along-commit` executes non-bypassable pre-flight syntax, typography, and link integrity gates.
- [ ] `along_exec.py` provides an AST-safe function replacement command.
- [ ] Clean `.gitattributes` with `eol=lf` committed to repository root.
- [ ] Unit tests in `tests/test_skills_and_scripts.py` verify that every gate correctly blocks invalid changes, heals corrupted indices, and enforces read-only invariance.


