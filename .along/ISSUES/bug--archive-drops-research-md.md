---
protocol: along
protocol_version: "4.4.6"
slug: archive-drops-research-md
type: bug
status: open
priority: high
created: 2026-10-07
updated: 2026-10-07
agent: claude
tags: [session, archive, blackboard]
milestone: v4.5.0-multi-user-merge-automation
blocked_by: []
related: [task--release-v4-4-7]
---

# Blackboard archive drops research.md

## Problem

`lifecycle.archive_and_purge` -> `write_session_record` writes the plan, the attributed
files table and the execution trace of a blackboard into its session log, then
`session.purge_session` removes `.along/.session/<slug>/` with `shutil.rmtree`.
`research.md` (and any other file a role-based run leaves there, e.g. `reviews/step-N.md`
if not already covered) is not carried into the record, so its content is gone for good:
`.along/.session/` is not tracked by git.

Observed during the `task--release-v4-4-7` closeout (2026-10-07): both archived blackboards
held scaffold-only `research.md`, so nothing was lost that time, but real research findings
would be.

## Requirements

- REQ-1: `write_session_record` includes `research.md` when it differs from the scaffold
  (section "Research"), and every other non-scaffold file of the blackboard (reviews, notes),
  or lists them with content.
- REQ-2: The purge refuses (or keeps the blackboard) when a file of the blackboard is neither
  archived nor a known scaffold: nothing leaves `.along/.session/` unrecorded.
- REQ-3: Same path for `along wrap`, `along scratch purge`, `along issue done`, `along session close`.

## Acceptance Criteria
- [ ] Hermetic test: blackboard with edited research.md -> purge -> session log contains it
- [ ] Unknown non-scaffold file blocks the purge with a clear message
- [ ] Automated tests passing
