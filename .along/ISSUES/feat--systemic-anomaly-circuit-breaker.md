---
protocol: along
slug: systemic-anomaly-circuit-breaker
type: feat
status: open
priority: critical
created: 2026-09-04
updated: 2026-09-04
agent: antigravity
tags: [circuit-breaker, stability, gates, systemic-errors, human-in-the-loop]
milestone: v2.1.0-along
blocked_by: []
related: [feat--runtime-enforcement-of-prose-rules, feat--programmatic-integrity-gates-and-git-guard]
---

# Systemic Error Circuit Breaker and Human Escalation Gate

## Problem Statement

When deep infrastructure, operating system, or environment errors occur during an agent session, LLM agents suffer from destructive self-healing loops ("долбление"). Instead of recognizing that the environment itself is compromised, the agent attempts frantic, ad-hoc workarounds:
- Installing global dependencies (`pip install`, `npm install -g`) when an interpreter fails to locate a module, violating repository hermeticity.
- Repeating failing Git commands against a locked or zero-byte `.git/index`.
- Applying speculative edits to source code when the failure is actually an external NTFS file-sharing lock or permission denial.
- Spawning background commands that accumulate zombie processes.

This behavior turns a localized environment glitch into a compounding cascade of local code corruption and corrupted Git history (the "snowball effect"). 

## Systemic Anomaly Taxonomy (Classes of Infrastructure Errors)

The circuit breaker classifies errors into five distinct Systemic Anomaly classes that require an immediate hard halt rather than automated retries:

### Class 1: VCS & Repository State Corruption
- Truncated or empty Git index: `fatal: .git/index: index file smaller than expected`.
- Deadlocked or stale Git locks: `fatal: Unable to create '.../.git/index.lock': File exists`.
- Broken loose objects or index tree corruption reported by `git status` or `git fsck`.

### Class 2: OS & Filesystem Contention (NTFS / POSIX)
- File sharing violations: file locked by an external IDE process, antivirus, or background runner (`EACCES`, `EBUSY`, sharing violation).
- Permission denied during process termination (e.g. `taskkill /F` returning `Access is denied`).
- Read-only filesystem, exhausted disk space, or path-length limits (`MAX_PATH`).

### Class 3: Global Environment & Toolchain Defects
- Missing system binaries required by the project: `uv`, `git`, `dotnet`, `cargo`, `python`.
- `ModuleNotFoundError` or missing site-packages in the active interpreter that tempt the agent to execute unauthorized global package manager commands.
- Incompatible runtime versions (e.g. Python < 3.10 when syntax requires modern typing).

### Class 4: Process Cascades & Zombie Hangs
- Zombie processes (e.g. orphaned `git.exe` instances running for multiple days) holding open file handles.
- Command executions timing out repeatedly across different tools.

### Class 5: Syntax Churn & Self-Destructive Edit Loops
- The same source file failing compilation (`py_compile`, syntax check) 2 or more consecutive times in a session.
- Iterative edits that repeatedly fail to match `replace_file_content` targets due to CRLF/LF drift.

## Architectural Solution: Circuit Breaker & Escalation Gate

### 1. Programmatic Error Classifier & Hard Trip
- In Along command runners (`alongkit.proc`, `along_exec.py`, and Antigravity tool wrappers), inspect stdout/stderr and exit codes against regex patterns for the 5 Systemic Anomaly classes.
- When an anomaly signature is detected:
  - **Tripping the Breaker**: Set internal circuit breaker state to `TRIPPED`.
  - **Zero Retries**: Automatically suppress all automated retries or fallback write commands.
  - **Halt Execution**: Abort the active agent turn immediately without attempting speculative code edits.

### 2. High-Priority Human Escalation Report
When tripped, the engine prints a standardized, high-visibility escalation report and suspends further action:

```text
======================================================================
[CIRCUIT BREAKER TRIPPED] Systemic Environment Anomaly Detected
======================================================================
Class: Class 1 (VCS / Repository State Corruption)
Signature: fatal: .git/index: index file smaller than expected
Impact: Continued automated modifications risk destroying working tree state.

Prescribed Human Remediation:
1. Reload IDE Window: In VS Code, press Ctrl+Shift+P -> 'Developer: Reload Window'.
2. Reset Git Index: In PowerShell, run: Remove-Item .git/index; git reset
3. Verify Git Status: Confirm 'git status' returns exit code 0 before resuming.

Agent Action: Execution halted. Awaiting human confirmation.
======================================================================
```

### 3. Anti-Workaround Hard Blocks
- Explicitly block tools from attempting known destructive workarounds:
  - Intercept and fail any command containing `pip install` (without `-e` or active venv), `npm install -g`, or `apt/choco/winget` inside automated tasks.
  - Intercept multi-line regex replacements when a syntax failure has already occurred on the target file.

### 4. Resumption Gate
- The agent is blocked from modifying files until:
  - The human explicitly resolves the environment issue and sends a confirmation message (e.g. "Environment fixed, proceed").
  - An automated pre-flight health probe confirms that the anomaly condition has cleared (`git status` succeeds, `.git/index` > 0 bytes, target file parses).

## Acceptance Criteria
- [ ] Error signature classifier implemented in `alongkit.proc` detecting Classes 1 through 5.
- [ ] Circuit breaker halts execution immediately upon detecting any Class 1-5 anomaly with zero automatic write retries.
- [ ] High-visibility human escalation report formatted with prescribed remediation steps.
- [ ] Tool execution guard blocks prohibited global install commands (`pip install`, `npm install -g`).
- [ ] Unit tests in `tests/test_skills_and_scripts.py` verify that:
  - 0-byte `.git/index` trips the breaker and stops execution.
  - Repeated syntax failures trigger a circuit breaker halt instead of infinite edit loops.
  - Human confirmation and clean health probe reset the breaker cleanly.

