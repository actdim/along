---
protocol: along
protocol_version: "4.4.16"
slug: session-record-gate-lifecycle-resilience
type: bug
status: open
priority: medium
created: 2026-10-16
updated: 2026-10-16
agent: antigravity
tags: [gates, git, ci, sessions]
blocked_by: []
related: [debt--consolidate-dashboard-ui-subproject]
---

# Improve session-record-append-only gate for deletions, renames, and subproject consolidation

## Problem

The commit and CI gate `session_record_append_only` (implemented in `alongkit.gitgates.check_session_records`) enforces that lines inside the `## Blackboard Record` section of committed session logs (`.along/SESSIONS/**.md`) are never removed or mutated.

However, the current implementation has several structural limitations during repository maintenance and lifecycle operations:

1. **False positive on file deletions / subproject retirement**: When an entire session file is removed (e.g. retiring an accidental subproject like `packages/dashboard-ui/.along/` or purging stale sessions), `diff -U0` against the base tree reports all lines as deleted. The gate flags every single line of `## Blackboard Record` as a violation, rather than treating file deletion as a distinct lifecycle event.
2. **Failure during session file moves and renames**: When a session file is relocated (for example, consolidating a subproject session into the root context), git diff on the old path reports total deletion, triggering spurious violations unless rename detection is performed.
3. **Multi-commit CI range bypass unawareness**: In CI (`along gates check --ci`), the checker diffs the entire push range `ALONG_CI_BEFORE..HEAD`. If an intermediate commit legitimately bypassed pre-commit hooks via `Along-Bypass: ...` to execute a one-time migration or consolidation, CI runs a flat range diff that ignores commit-level bypass trailers and fails the build.

## Requirements

- `REQ-1`: `check_session_records` MUST differentiate between line modifications in an existing session file and complete file deletion (`--diff-filter=D` or non-existence in target).
- `REQ-2`: If session file deletion requires authorization, it MUST emit a single structured violation per file (`session_deletion`), or be permitted when explicit consolidation or bypass metadata is provided.
- `REQ-3`: Git rename detection (`-M`) MUST be utilized to match relocated session files and verify that the blackboard record lines are preserved across renames.
- `REQ-4`: Multi-commit CI range checks MUST evaluate commit-level bypass annotations (`Along-Bypass`) when checking diff ranges, or provide an explicit mechanism for authorized historical transitions.
- `REQ-5`: All unit tests in `tests/test_session_records.py` and `tests/test_gitgates.py` MUST be updated and pass cleanly.

## Acceptance Criteria

- [ ] File deletions in `check_session_records` do not emit per-line Blackboard Record violations.
- [ ] Relocated or renamed session files are validated across paths without false deletion alerts.
- [ ] CI range gate verification respects authorized bypass trailers or subproject consolidation markers.
- [ ] Hermetic unit tests cover file deletion, session relocation, and CI range validation.
