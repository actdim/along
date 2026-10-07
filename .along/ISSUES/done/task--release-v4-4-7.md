---
protocol: along
protocol_version: "4.4.6"
slug: release-v4-4-7
type: task
status: done
completed: 2026-10-07
priority: high
created: 2026-10-07
updated: 2026-10-07
agent: claude
tags: [release, closeout]
blocked_by: []
related: [feat--test-gate-cost-reduction, bug--release-tags-not-pushed]
---

# Release v4.4.7: close open sessions, commit pending work, patch bump

## Context

Several parallel sessions (2026-10-06 .. 2026-10-07) finished their issues (wrapped, moved
to `done/`, session logs written) but left 77 changed paths uncommitted and unattributed.
Two blackboards remain: `monorepo-update-gate-friction` (umbrella of the 2026-10-06 bug
batch; its issue file was never created) and `release-tags-not-pushed` (open bug, work not
started past the plan).

## Requirements

- REQ-1: Nothing is lost: blackboards leave only through `along scratch purge`, which writes
  them into a session log first; no history, session log, issue, or ADR is deleted.
- REQ-2: `bug--release-tags-not-pushed` stays open (criteria 1/4); only its idle blackboard is archived.
- REQ-3: Pending work committed in reviewable groups bound to their issues, tests green.
- REQ-4: Patch release v4.4.7 (commit + annotated tag), commit and tag pushed and verified on the remote.

## Acceptance Criteria
- [x] Both blackboards archived into session logs, no stale bindings (old binding files kept: unbound, they carry completion tokens)
- [x] Pending work committed and pushed (4f393e4, 6c62d48)
- [x] v4.4.7 released, tag present on origin (9844157, tag v4.4.7 verified with git ls-remote)
- [x] Automated tests passing (1114 tests, 218 s)

## Notes

- `lifecycle.write_session_record` archives plan, attributed files and execution trace, but not `research.md`; both archived blackboards had scaffold-only research (no edits in their traces), so nothing was lost here. Worth covering in the archiver.
