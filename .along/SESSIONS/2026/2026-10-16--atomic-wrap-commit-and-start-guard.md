---
protocol: along
protocol_version: "4.4.15"
date: 2026-10-16
slug: atomic-wrap-commit-and-start-guard
agent: antigravity
branch: main
commit: e239dbc
summary: 'feat: atomic wrap commit, clean start guard, and CLI black-box invariance'
issues_advanced: []
issues_completed: [feat--atomic-wrap-commit-and-start-guard]
decisions: []
risks_logged: []
spikes_conducted: []
---

# Session: Atomic wrap commit and start guard

## Summary
feat: atomic wrap commit, clean start guard, and CLI black-box invariance

## Decisions
- None (confirmed at wrap: no architectural decisions).

## Blackboard Record

Execution mode: direct; plan revision 1; approved: true.

### Attributed Files

| Path | Kind | Edits | Last edit | Sessions |
| --- | --- | --- | --- | --- |
| `.along/ISSUES/feat--atomic-wrap-commit-and-start-guard.md` | state | 1 | 2026-10-16T09:59:11Z | antigravity--0158c098-571b-401b-9e02-03970334edf5 |
| `AGENTS.md` | docs | 1 | 2026-10-16T09:49:12Z | antigravity--0158c098-571b-401b-9e02-03970334edf5 |
| `llms-full.txt` | source | 1 | 2026-10-16T09:49:22Z | antigravity--0158c098-571b-401b-9e02-03970334edf5 |
| `scripts/along_exec.py` | source | 1 | 2026-10-16T09:47:28Z | antigravity--0158c098-571b-401b-9e02-03970334edf5 |
| `scripts/along_wrap.py` | source | 1 | 2026-10-16T09:46:40Z | antigravity--0158c098-571b-401b-9e02-03970334edf5 |
| `scripts/alongkit/closeout.py` | source | 1 | 2026-10-16T09:47:08Z | antigravity--0158c098-571b-401b-9e02-03970334edf5 |
| `scripts/alongkit/commands/session.py` | source | 1 | 2026-10-16T09:46:50Z | antigravity--0158c098-571b-401b-9e02-03970334edf5 |
| `scripts/alongkit/hooks/containment.py` | source | 1 | 2026-10-16T09:58:33Z | antigravity--0158c098-571b-401b-9e02-03970334edf5 |
| `scripts/alongkit/lifecycle.py` | source | 4 | 2026-10-16T09:52:57Z | antigravity--0158c098-571b-401b-9e02-03970334edf5 |
| `skills/along-init/protocol.md` | source | 1 | 2026-10-16T09:49:05Z | antigravity--0158c098-571b-401b-9e02-03970334edf5 |
| `skills/along-wrap/SKILL.md` | source | 6 | 2026-10-16T09:58:20Z | antigravity--0158c098-571b-401b-9e02-03970334edf5 |
| `tests/test_docs.py` | source | 1 | 2026-10-16T09:49:30Z | antigravity--0158c098-571b-401b-9e02-03970334edf5 |
| `tests/test_lifecycle_wrap.py` | source | 1 | 2026-10-16T09:53:26Z | antigravity--0158c098-571b-401b-9e02-03970334edf5 |
| `tests/test_parallel_closeout.py` | source | 1 | 2026-10-16T09:54:35Z | antigravity--0158c098-571b-401b-9e02-03970334edf5 |
| `tests/test_start_guard.py` | source | 2 | 2026-10-16T09:57:05Z | antigravity--0158c098-571b-401b-9e02-03970334edf5 |
| `tests/test_workspace_containment.py` | source | 1 | 2026-10-16T09:58:58Z | antigravity--0158c098-571b-401b-9e02-03970334edf5 |

### Plan

#### Implementation Plan: Atomic Wrap Commit, Start Guard, and CLI Black-Box Invariance

##### Baseline Architecture
1. `scripts/alongkit/lifecycle.py`: `execute_wrap` finalizes issues, updates projections, and currently calls `_warn_uncommitted_work` which only prints a warning.
2. `scripts/along_exec.py`: `handle_start_command` initializes session and marks issue in-progress without checking working tree state.
3. `skills/along-init/protocol.md` & `AGENTS.md`: Define protocol rules for agents.

##### Implementation Steps
1. **Auto-commit on wrap (`along wrap`)**:
   - In `scripts/along_exec.py`: update `wrap` CLI parser to accept `--no-commit` (defaulting to committing).
   - In `scripts/alongkit/lifecycle.py`: in `execute_wrap`, accept `auto_commit: bool = True`.
   - When `auto_commit` is True, collect dirty attributed files, issue file, session log, and projections. Call `along commit` or execute Git commit directly with Conventional Commit formatting: `<type>(<slug>): <title> (refs #<slug>)`.
   - If `--no-commit` is specified, retain the warning behavior (`_warn_uncommitted_work`).
2. **Start guard on dirty tree (`along start`)**:
   - In `scripts/along_exec.py`: in `handle_start_command`, inspect `git_changes` and `done_issues_attribution`.
   - Check A: If there are uncommitted files from previously wrapped/done issues, exit with error code 1 and instruct the user to commit or resolve them first.
   - Check B: If there are uncommitted changes in the repository from another active issue (and `--worktree` is not passed), check for `--allow-dirty`. If not provided, exit with error advising either `along start <slug> --worktree` or `--allow-dirty`.
3. **Protocol Rule: CLI Black-Box Invariance**:
   - Add the strict `CLI Black-Box Invariance` rule to `skills/along-init/protocol.md`, `AGENTS.md`, and `llms-full.txt`.
4. **Verification**:
   - Add/update unit and hermetic tests in `tests/test_lifecycle.py`, `tests/test_closeout.py`, or a new test case.
   - Run tests to verify the behavior.

### Execution Trace

#### Execution Trace: atomic-wrap-commit-and-start-guard
- 2026-10-16T09:44:07Z plan approved (along plan approve) approved_via: cli-unverified, plan_sha256: 7cfbac694997
- 2026-10-16T09:46:32Z edit scripts/alongkit/lifecycle.py (x3)
- 2026-10-16T09:46:40Z edit scripts/along_wrap.py
- 2026-10-16T09:46:50Z edit scripts/alongkit/commands/session.py
- 2026-10-16T09:47:08Z edit scripts/alongkit/closeout.py
- 2026-10-16T09:47:28Z edit scripts/along_exec.py
- 2026-10-16T09:49:05Z edit skills/along-init/protocol.md
- 2026-10-16T09:49:12Z edit AGENTS.md
- 2026-10-16T09:49:22Z edit llms-full.txt
- 2026-10-16T09:49:30Z edit tests/test_docs.py
- 2026-10-16T09:52:57Z edit scripts/alongkit/lifecycle.py
- 2026-10-16T09:53:26Z edit tests/test_lifecycle_wrap.py
- 2026-10-16T09:54:35Z edit tests/test_parallel_closeout.py
- 2026-10-16T09:57:05Z edit tests/test_start_guard.py (x2)
- 2026-10-16T09:58:20Z edit skills/along-wrap/SKILL.md (x6)
- 2026-10-16T09:58:33Z edit scripts/alongkit/hooks/containment.py
- 2026-10-16T09:58:58Z edit tests/test_workspace_containment.py
- 2026-10-16T09:59:11Z edit .along/ISSUES/feat--atomic-wrap-commit-and-start-guard.md
- 2026-10-16T10:03:30Z test pass (Wrap Quality Gate)
