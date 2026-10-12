---
protocol: along
protocol_version: "4.4.11"
date: 2026-10-12
slug: destructive-pre-tool-consumption-and-false-positives
agent: antigravity
branch: main
commit: c261135
summary: Consume destructive confirmation on PreToolUse and eliminate false positives in env, git, and path classifiers
issues_advanced: []
issues_completed: [bug--destructive-pre-tool-consumption-and-false-positives]
decisions: []
risks_logged: []
spikes_conducted: []
---

# Session: Destructive pre tool consumption and false positives

## Summary
Consume destructive confirmation on PreToolUse and eliminate false positives in env, git, and path classifiers

## Decisions
- None (confirmed at wrap: no architectural decisions).

## Blackboard Record

Execution mode: direct; plan revision 1; approved: true.

### Attributed Files

| Path | Kind | Edits | Last edit | Sessions |
| --- | --- | --- | --- | --- |
| `.along/ISSUES/bug--destructive-pre-tool-consumption-and-false-positives.md` | state | 1 | 2026-10-12T19:51:05Z | antigravity--568a4191-e5cf-4667-8d6d-138c497344d7 |
| `scripts/alongkit/hooks/config.py` | source | 1 | 2026-10-12T19:43:30Z | antigravity--568a4191-e5cf-4667-8d6d-138c497344d7 |
| `scripts/alongkit/hooks/predicates.py` | source | 1 | 2026-10-12T19:43:20Z | antigravity--568a4191-e5cf-4667-8d6d-138c497344d7 |
| `scripts/alongkit/hooks/shellparse.py` | source | 1 | 2026-10-12T19:43:51Z | antigravity--568a4191-e5cf-4667-8d6d-138c497344d7 |
| `scripts/alongkit/hooks/toolnature.py` | source | 7 | 2026-10-12T19:50:04Z | antigravity--568a4191-e5cf-4667-8d6d-138c497344d7 |
| `tests/test_session_bindings.py` | source | 1 | 2026-10-12T19:49:08Z | antigravity--568a4191-e5cf-4667-8d6d-138c497344d7 |
| `tests/test_tool_nature.py` | source | 3 | 2026-10-12T19:48:25Z | antigravity--568a4191-e5cf-4667-8d6d-138c497344d7 |

### Plan

#### Plan: Fix PreToolUse Destructive Consumption, Eliminate Env Var and Git False Positives

##### Execution Mode: Direct

##### Steps

1. [x] **Step 1: PreToolUse Atomic Destructive Consumption & Claude Hook Matcher**
   - In `scripts/alongkit/hooks/predicates.py`, consume destructive authorization directly on PreToolUse in `check_require_plan_approval` before returning `None` (`session.consume_destructive_confirmation(repo_root, slug=slug, key=key)`).
   - In `scripts/alongkit/hooks/config.py`, update `CLAUDE_POST_TOOL_MATCHER` to include `Bash|PowerShell`.

2. [x] **Step 2: Dangerous Environment Variables Expansion & Position Scoping**
   - In `scripts/alongkit/hooks/shellparse.py`, expand `is_dangerous_env_var` to treat `PATH` and all `GIT_*` variables as dangerous alongside `_DANGEROUS_ENV_VARS`.
   - In `scripts/alongkit/hooks/toolnature.py`, rewrite `extract_dangerous_env_overrides` so environment variable overrides are checked exclusively in assignment positions before the command:
     - Leading assignments: `VAR=val ... cmd`
     - `env` arguments: `env [opts] VAR=val ... cmd`
     - `export` / `set` commands: `export VAR=val`, `set VAR=val`
     - PowerShell assignments: `^\s*\$env:VAR\s*=`
   - Eliminate false positives on read expressions such as `echo $env:EDITOR`, `grep EDITOR= file`, and `echo "export PAGER=less"`.

3. [x] **Step 3: Git Global Options Scoping & val_options Sanitization**
   - In `scripts/alongkit/hooks/toolnature.py`:
     - Scope `git -c` allowlist checks strictly to global options occurring before the git subcommand. Options after the subcommand (e.g. `git grep -c foo`, `git commit -c HEAD`, `git diff -c`) are ignored by global git config checks.
     - Remove `-c` and `-p` from `val_options` in `_parse_tokens_into_call`.
     - Scope tool-specific options (PowerShell parameter names, find options, etc.) to their respective tools rather than polluting global `val_options`.

4. [x] **Step 4: Temp Directory Safe Writes & PowerShell Path Expansion**
   - In `scripts/alongkit/hooks/toolnature.py`:
     - Add helper to expand PowerShell `$env:VAR` and system path variables.
     - Permit writes and deletions within system temporary directories (`tempfile.gettempdir()`, `$env:TEMP`, `%TEMP%`, `/tmp`, `/var/tmp`) in `_classify_out_file` and `_classify_deletion`.

5. [x] **Step 5: Automated Testing & Verification**
   - Add unit tests in `tests/test_tool_nature.py` and `tests/test_session_bindings.py` covering all targeted fixes.
   - Run the full test suite and verify clean typography.

### Execution Trace

#### Execution Trace: destructive-pre-tool-consumption-and-false-positives
- 2026-10-12T19:43:07Z plan approved (along plan approve) approved_via: cli-unverified, plan_sha256: f67bf0f70c96
- 2026-10-12T19:43:20Z edit scripts/alongkit/hooks/predicates.py
- 2026-10-12T19:43:30Z edit scripts/alongkit/hooks/config.py
- 2026-10-12T19:43:51Z edit scripts/alongkit/hooks/shellparse.py
- 2026-10-12T19:47:35Z edit scripts/alongkit/hooks/toolnature.py (x6)
- 2026-10-12T19:48:25Z edit tests/test_tool_nature.py (x3)
- 2026-10-12T19:49:08Z edit tests/test_session_bindings.py
- 2026-10-12T19:50:04Z edit scripts/alongkit/hooks/toolnature.py
- 2026-10-12T19:51:05Z edit .along/ISSUES/bug--destructive-pre-tool-consumption-and-false-positives.md
