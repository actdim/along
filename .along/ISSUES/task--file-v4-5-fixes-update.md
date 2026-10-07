---
protocol: along
protocol_version: "4.4.6"
slug: file-v4-5-fixes-update
type: task
status: in-progress
priority: medium
created: 2026-10-07
updated: 2026-10-07
agent: claude
tags: [issues, install]
blocked_by: []
related: [task--release-v4-4-7]
---

# File v4.5.0 fix tickets and update the global installation

## Context

The `release-v4-4-7` closeout surfaced Along defects without tickets. The user asked
(2026-10-07) to file them all for v4.5.0, then update the global installation (still
v4.4.6 in `~/.along`).

## Requirements

- REQ-1: Tickets filed in v4.5.0: archive-drops-research-md, wrapped-work-left-uncommitted,
  history-append-blocked-after-wrap, uncommitted-issue-deleted-without-trace,
  plan-gate-blocks-help, inquiry-readonly-commands-blocked, release-ci-precondition-check,
  protocol-friction-cleanup; feat--test-gate-cost-reduction gains REQ-6 and moves to v4.5.0.
- REQ-2: Committed and pushed.
- REQ-3: Global installation updated to the repository version (v4.4.7) via `along update`
  (or the installer); `along doctor` reports the new version.

## Acceptance Criteria
- [ ] Tickets filed and pushed
- [ ] Global installation at v4.4.7
- [ ] Automated tests passing
