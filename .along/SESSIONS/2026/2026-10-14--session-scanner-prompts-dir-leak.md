---
protocol: along
protocol_version: "4.4.13"
date: 2026-10-14
slug: session-scanner-prompts-dir-leak
agent: antigravity
branch: main
commit: 02c7b9c
summary: Exclude internal prompts directory from session and blackboard scanners
milestone: v4.6.0-structured-state-and-blackboard-engine
issues_advanced: []
issues_completed: [bug--session-scanner-prompts-dir-leak]
decisions: []
risks_logged: []
spikes_conducted: []
---

# Session: Session scanner prompts dir leak

## Summary
Exclude internal prompts directory from session and blackboard scanners

## Decisions
- None (confirmed at wrap: no architectural decisions).

## Blackboard Record

Execution mode: direct; plan revision 1; approved: true.

### Attributed Files

| Path | Kind | Edits | Last edit | Sessions |
| --- | --- | --- | --- | --- |
| `.along/ISSUES/bug--session-scanner-prompts-dir-leak.md` | state | 1 | 2026-10-14T09:52:30Z | antigravity--c22cb941-2ff5-46ae-970f-e9020897551e |
| `scripts/along_exec.py` | source | 1 | 2026-10-14T09:50:41Z | antigravity--c22cb941-2ff5-46ae-970f-e9020897551e |
| `scripts/alongkit/closeout.py` | source | 1 | 2026-10-14T09:50:30Z | antigravity--c22cb941-2ff5-46ae-970f-e9020897551e |
| `scripts/alongkit/lifecycle.py` | source | 1 | 2026-10-14T09:50:36Z | antigravity--c22cb941-2ff5-46ae-970f-e9020897551e |
| `scripts/alongkit/session.py` | source | 2 | 2026-10-14T09:50:22Z | antigravity--c22cb941-2ff5-46ae-970f-e9020897551e |
| `tests/test_session_scanner_leak.py` | source | 1 | 2026-10-14T09:51:10Z | antigravity--c22cb941-2ff5-46ae-970f-e9020897551e |

### Plan

#### Living Plan: session-scanner-prompts-dir-leak

Title: Exclude internal prompts directory from session and blackboard scanners
Execution Mode: Direct

##### Rationale
The `.along/.session/prompts/` directory is an internal storage location for user prompt timestamps.
Directory scanners across `session.py`, `closeout.py`, `lifecycle.py`, and `along_exec.py` only exclude
`BINDINGS_DIRNAME` ("bindings"), causing "prompts" to leak as a phantom issue slug / blackboard directory.
We define `RESERVED_SESSION_DIRS = frozenset({BINDINGS_DIRNAME, PROMPTS_DIRNAME})` in `alongkit.session`
and update all directory scanners to use this shared constant.

##### Steps
- [x] Step 1: Define `RESERVED_SESSION_DIRS` in `scripts/alongkit/session.py` containing `BINDINGS_DIRNAME` and `PROMPTS_DIRNAME` (REQ-1).
- [x] Step 2: Update `_blackboard_slugs` in `scripts/alongkit/closeout.py` to filter entries against `session.RESERVED_SESSION_DIRS` (REQ-2).
- [x] Step 3: Update `in_progress_slugs` in `scripts/alongkit/session.py` to filter entries against `RESERVED_SESSION_DIRS` (REQ-3).
- [x] Step 4: Update `orphan_blackboards` in `scripts/alongkit/lifecycle.py` and active blackboard scanning in `scripts/along_exec.py` to filter entries against `session.RESERVED_SESSION_DIRS` (REQ-4).
- [x] Step 5: Add hermetic unit tests in `tests/test_session_scanner_leak.py` verifying that `prompts/` (and any other reserved directory) is never enumerated by `in_progress_slugs`, `_blackboard_slugs`, `closeout_status`, or `orphan_blackboards` (REQ-5).
- [x] Step 6: Verify all tests pass cleanly and run `along session list` and `along doctor` to verify zero phantom entries.

### Execution Trace

#### Execution Trace: session-scanner-prompts-dir-leak
- 2026-10-14T09:49:41Z plan approved (along plan approve) approved_via: cli-unverified, plan_sha256: e7e9aa94a859
- 2026-10-14T09:50:22Z edit scripts/alongkit/session.py (x2)
- 2026-10-14T09:50:30Z edit scripts/alongkit/closeout.py
- 2026-10-14T09:50:36Z edit scripts/alongkit/lifecycle.py
- 2026-10-14T09:50:41Z edit scripts/along_exec.py
- 2026-10-14T09:51:10Z edit tests/test_session_scanner_leak.py
- 2026-10-14T09:52:30Z edit .along/ISSUES/bug--session-scanner-prompts-dir-leak.md
- 2026-10-14T10:00:25Z test FAIL (along test)
- 2026-10-14T10:01:05Z test pass (along test)
