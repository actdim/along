---
protocol: along
protocol_version: "4.4.11"
date: 2026-10-12
slug: destructive-authorization-and-lock-hardening
agent: antigravity
branch: main
commit: 6b21678
summary: Harden destructive authorization, doc-manual-lock, git -c allowlist, and env stripping
issues_advanced: []
issues_completed: [bug--destructive-authorization-and-lock-hardening]
decisions: []
risks_logged: []
spikes_conducted: []
---

# Session: Destructive authorization and lock hardening

## Summary
Harden destructive authorization, doc-manual-lock, git -c allowlist, and env stripping

## Decisions
- None (confirmed at wrap: no architectural decisions).

## Blackboard Record

Execution mode: direct; plan revision 1; approved: true.

### Attributed Files

| Path | Kind | Edits | Last edit | Sessions |
| --- | --- | --- | --- | --- |
| `.along/ISSUES/bug--destructive-authorization-and-lock-hardening.md` | state | 2 | 2026-10-12T18:51:28Z | antigravity--568a4191-e5cf-4667-8d6d-138c497344d7 |
| `scripts/along_exec.py` | source | 1 | 2026-10-12T18:30:41Z | antigravity--568a4191-e5cf-4667-8d6d-138c497344d7 |
| `scripts/alongkit/hooks/predicates.py` | source | 4 | 2026-10-12T18:42:49Z | antigravity--568a4191-e5cf-4667-8d6d-138c497344d7 |
| `scripts/alongkit/hooks/shellparse.py` | source | 1 | 2026-10-12T18:31:17Z | antigravity--568a4191-e5cf-4667-8d6d-138c497344d7 |
| `scripts/alongkit/hooks/toolnature.py` | source | 27 | 2026-10-12T18:44:23Z | antigravity--568a4191-e5cf-4667-8d6d-138c497344d7 |
| `scripts/alongkit/session.py` | source | 1 | 2026-10-12T18:30:33Z | antigravity--568a4191-e5cf-4667-8d6d-138c497344d7 |
| `scripts/alongkit/verify.py` | source | 1 | 2026-10-12T18:23:52Z | antigravity--568a4191-e5cf-4667-8d6d-138c497344d7 |
| `tests/test_kb_sync.py` | source | 2 | 2026-10-12T18:46:50Z | antigravity--568a4191-e5cf-4667-8d6d-138c497344d7 |
| `tests/test_session_bindings.py` | source | 1 | 2026-10-12T18:45:04Z | antigravity--568a4191-e5cf-4667-8d6d-138c497344d7 |
| `tests/test_tool_nature.py` | source | 3 | 2026-10-12T18:44:05Z | antigravity--568a4191-e5cf-4667-8d6d-138c497344d7 |
| `tests/test_verify_policy.py` | source | 1 | 2026-10-12T18:45:41Z | antigravity--568a4191-e5cf-4667-8d6d-138c497344d7 |

### Plan

#### Living Plan: destructive-authorization-and-lock-hardening

Title: Harden Destructive Authorization, Doc Manual Lock, Git Security, and Shell Parsing
Execution Mode: Direct

##### Steps
- [x] Step 1: Doc-manual-lock hardening
  - In `predicates.py`: restore `session.is_plan_approved` requirement for keyed sessions in `check_doc_manual_lock`.
  - Read `target_doc` from ticket frontmatter (`i_fm`), not document frontmatter (`fm`).
  - Restrict file-based ticket check to unkeyed runtimes (`not key`).
- [x] Step 2: Remove `.txt` from `_DOC_SUFFIXES`
  - In `verify.py`: remove `.txt` from `_DOC_SUFFIXES`.
  - Ensure only `llms*.txt` and explicit entries in `_DOC_FILES` qualify as doc-only text files.
- [x] Step 3: Harden `_classify_deletion`
  - In `toolnature.py`: classify targets under `.git`, `.along`, `.git/**`, `.along/**` as `DESTRUCTIVE`.
  - Parse Windows cmd flags (`/q`, `/f`, `/s`, etc.) correctly so they are not treated as filesystem root paths.
  - Distinguish subfolder wildcards inside the repo (e.g. `dist/*`) from repo root / filesystem root wildcards.
- [x] Step 4: Single-use destructive confirmation and anti-self-approval
  - In `session.py`: implement `consume_destructive_confirmation(repo_root, key)`.
  - In `predicates.py`: call `session.consume_destructive_confirmation` in `record_tool_activity` on `POST_TOOL_USE` when a destructive action is executed.
  - In `session.py`: check `via != APPROVED_VIA_CLI_UNVERIFIED` before granting `--confirm-destructive` to block autonomous self-approval without user input.
- [x] Step 5: Dangerous environment variable inspection
  - In `shellparse.py` and `toolnature.py`: inspect environment variable assignments before stripping.
  - If dangerous variables (`GIT_SSH_COMMAND`, `GIT_CONFIG_*`, `GIT_ASKPASS`, `GIT_EXTERNAL_DIFF`, `LD_PRELOAD`, `LD_LIBRARY_PATH`, `PAGER`, `EDITOR`, etc.) are overridden, classify the command segment as `DESTRUCTIVE`.
- [x] Step 6: Git -c safe allowlist
  - In `toolnature.py`: transition `git -c` from denylist to allowlist of known benign flags (`user.name`, `user.email`, `color.*`, `advice.*`, `core.quotepath`, `core.autocrlf`, `core.safecrlf`, `core.eol`, `diff.algorithm`, `rebase.autostash`, etc.). All other `-c` keys classify as `DESTRUCTIVE`.
- [x] Step 7: Classify `gh api -X DELETE` as DESTRUCTIVE
  - In `toolnature.py`: classify `gh api` with `-X DELETE` or `--method DELETE` as `DESTRUCTIVE`.
- [x] Step 8: Fix `Out-File` PowerShell parsing and classification
  - In `toolnature.py`: add `out-file` to built-in commands with path check.
  - Fix `_parse_tokens_into_call` to skip flag arguments (`-Encoding utf8`) from contaminating `subcommand`.
- [x] Step 9: Regression tests and full test suite verification
  - Add comprehensive unit tests in `test_tool_nature.py`, `test_session_bindings.py`, `test_kb_sync.py`, and `test_verify_policy.py`.
  - Run full test suite (`python .along/scripts/test.py -q`) and verify 100% green and clean ASCII typography.

### Execution Trace

#### Execution Trace: destructive-authorization-and-lock-hardening
- 2026-10-12T18:22:52Z edit .along/ISSUES/bug--destructive-authorization-and-lock-hardening.md
- 2026-10-12T18:23:12Z plan approved (along plan approve) approved_via: cli-unverified, plan_sha256: 0b402c67068f
- 2026-10-12T18:23:33Z edit scripts/alongkit/hooks/predicates.py
- 2026-10-12T18:23:45Z denied [require_plan_approval] run_command: Unclassified Tool Nature [gate: require-plan-approval]: Tool or command 'findstr /s' has unclassified nature. Ask the user for its nature (read-only, verific...
- 2026-10-12T18:23:52Z edit scripts/alongkit/verify.py
- 2026-10-12T18:24:30Z edit scripts/alongkit/hooks/toolnature.py
- 2026-10-12T18:30:33Z edit scripts/alongkit/session.py
- 2026-10-12T18:30:41Z edit scripts/along_exec.py
- 2026-10-12T18:31:00Z edit scripts/alongkit/hooks/predicates.py (x2)
- 2026-10-12T18:31:17Z edit scripts/alongkit/hooks/shellparse.py
- 2026-10-12T18:33:12Z edit scripts/alongkit/hooks/toolnature.py (x4)
- 2026-10-12T18:33:15Z denied [require_plan_approval] run_command: Destructive Action [gate: require-plan-approval]: Tool or command 'python -c "with open('scripts/alongkit/hooks/toolnature.py', 'rb') as f: data = f.read(500...
- 2026-10-12T18:33:39Z edit scripts/alongkit/hooks/toolnature.py
- 2026-10-12T18:33:51Z denied [require_plan_approval] run_command: Destructive Action [gate: require-plan-approval]: Tool or command 'python -c "lines = open('scripts/alongkit/hooks/toolnature.py', encoding='utf-8').readline... (x3)
- 2026-10-12T18:34:04Z edit scripts/alongkit/hooks/toolnature.py
- 2026-10-12T18:34:08Z denied [require_plan_approval] run_command: Destructive Action [gate: require-plan-approval]: Tool or command 'python -c "lines = open('scripts/alongkit/hooks/toolnature.py', encoding='utf-8').readline...
- 2026-10-12T18:34:23Z edit scripts/alongkit/hooks/toolnature.py
- 2026-10-12T18:34:28Z denied [require_plan_approval] run_command: Destructive Action [gate: require-plan-approval]: Tool or command 'python -c "content = open('scripts/alongkit/hooks/toolnature.py', encoding='utf-8').read()...
- 2026-10-12T18:34:34Z edit scripts/alongkit/hooks/toolnature.py
- 2026-10-12T18:34:38Z denied [require_plan_approval] run_command: Destructive Action [gate: require-plan-approval]: Tool or command 'python -c "lines = open('scripts/alongkit/hooks/toolnature.py', encoding='utf-8').readline...
- 2026-10-12T18:35:03Z edit scripts/alongkit/hooks/toolnature.py (x2)
- 2026-10-12T18:35:11Z denied [require_plan_approval] run_command: Destructive Action [gate: require-plan-approval]: Tool or command 'python -c "lines = open('scripts/alongkit/hooks/toolnature.py', encoding='utf-8').readline... (x2)
- 2026-10-12T18:35:22Z edit scripts/alongkit/hooks/toolnature.py
- 2026-10-12T18:35:27Z denied [require_plan_approval] run_command: Destructive Action [gate: require-plan-approval]: Tool or command 'python -c "with open('scripts/alongkit/hooks/toolnature.py', 'rb') as f: data = f.read(); ...
- 2026-10-12T18:35:52Z edit scripts/alongkit/hooks/toolnature.py (x3)
- 2026-10-12T18:35:57Z denied [require_plan_approval] run_command: Destructive Action [gate: require-plan-approval]: Tool or command 'python -c "lines = open('scripts/alongkit/hooks/toolnature.py', encoding='utf-8').readline...
- 2026-10-12T18:36:06Z edit scripts/alongkit/hooks/toolnature.py
- 2026-10-12T18:36:09Z denied [require_plan_approval] run_command: Destructive Action [gate: require-plan-approval]: Tool or command 'python -c "lines = open('scripts/alongkit/hooks/toolnature.py', encoding='utf-8').readline...
- 2026-10-12T18:36:32Z edit scripts/alongkit/hooks/toolnature.py (x2)
- 2026-10-12T18:36:40Z denied [require_plan_approval] run_command: Destructive Action [gate: require-plan-approval]: Tool or command 'python -c "lines = open('scripts/alongkit/hooks/toolnature.py', encoding='utf-8').readline...
- 2026-10-12T18:38:36Z edit scripts/alongkit/hooks/toolnature.py (x8)
- 2026-10-12T18:38:41Z denied [require_plan_approval] run_command: Unclassified Tool Nature [gate: require-plan-approval]: Tool or command 'powershell Copy-Item -Path 'scripts\*' -Destination '$HOME\.along\bin\' -Recurse -Fo...
- 2026-10-12T18:42:49Z edit scripts/alongkit/hooks/predicates.py
- 2026-10-12T18:44:05Z edit tests/test_tool_nature.py (x3)
- 2026-10-12T18:44:23Z edit scripts/alongkit/hooks/toolnature.py
- 2026-10-12T18:45:04Z edit tests/test_session_bindings.py
- 2026-10-12T18:45:41Z edit tests/test_verify_policy.py
- 2026-10-12T18:46:50Z edit tests/test_kb_sync.py (x2)
- 2026-10-12T18:47:13Z denied [require_plan_approval] run_command: Unclassified Tool Nature [gate: require-plan-approval]: Tool or command 'powershell Copy-Item -Path 'scripts\*' -Destination '$HOME\.along\bin\' -Recurse -Fo...
- 2026-10-12T18:51:28Z edit .along/ISSUES/bug--destructive-authorization-and-lock-hardening.md
