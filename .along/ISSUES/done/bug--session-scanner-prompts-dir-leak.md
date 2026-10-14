---
protocol: along
protocol_version: "4.4.13"
slug: session-scanner-prompts-dir-leak
type: bug
status: done
completed: 2026-10-14
priority: medium
created: 2026-10-14
updated: 2026-10-14
agent: antigravity
tags: [session, scanner, closeout]
milestone: v4.6.0-structured-state-and-blackboard-engine
blocked_by: []
related: [feat--parallel-session-closeout, feat--gate-strictness-profiles]
---

# Exclude internal prompts directory from session and blackboard scanners

## Problem

The internal directory `.along/.session/prompts/` stores timestamps of recent user prompts per runtime session (`<runtime>--<session_id>.json`). When `along session list` or `along session close` inspects directory entries under `.along/.session/`, directory scanners (`_blackboard_slugs` in `scripts/alongkit/closeout.py`, `in_progress_slugs` in `scripts/alongkit/session.py`, and blackboard cleanup in `scripts/alongkit/lifecycle.py`) only filter out `BINDINGS_DIRNAME` (`bindings`).

As a result:
1. `prompts` is mistakenly interpreted as an issue slug or blackboard directory.
2. `along session list` reports a phantom blocked item:
   ```
   - prompts [blocked]
       sessions: none bound
       files: 0 exclusive, 0 shared; 0 still uncommitted
       tests: none; last edit -; criteria 0/0; plan missing
       blocked: issue missing (archive the blackboard: along scratch purge)
       blocked: no blackboard: nothing was recorded (along start)
   ```
3. Lifecycle blackboard cleanup logic may attempt to inspect or archive `prompts`.

## Requirements

- REQ-1: Introduce a centralized tuple/frozenset of reserved internal `.along/.session/` subdirectories (`RESERVED_SESSION_DIRS = frozenset({BINDINGS_DIRNAME, PROMPTS_DIRNAME})`) in `scripts/alongkit/session.py`.
- REQ-2: Update `_blackboard_slugs` in `scripts/alongkit/closeout.py` to ignore entries in `RESERVED_SESSION_DIRS`.
- REQ-3: Update `in_progress_slugs` in `scripts/alongkit/session.py` to ignore entries in `RESERVED_SESSION_DIRS`.
- REQ-4: Update `lifecycle.py` blackboard scanners to ignore entries in `RESERVED_SESSION_DIRS`.
- REQ-5: Add hermetic unit tests verifying that `.along/.session/prompts/` (and any other reserved internal session directory) is never enumerated as a candidate session, blackboard, or issue slug.

## Acceptance Criteria

- [x] `RESERVED_SESSION_DIRS` defined in `scripts/alongkit/session.py` covering `BINDINGS_DIRNAME` and `PROMPTS_DIRNAME`.
- [x] `along session list` outputs zero entries when only `bindings/` and `prompts/` exist in `.along/.session/`.
- [x] All scanners in `session.py`, `closeout.py`, and `lifecycle.py` use the unified exclusion filter.
- [x] Unit tests added and passing in `tests/`.
- [x] Automated tests passing cleanly.
