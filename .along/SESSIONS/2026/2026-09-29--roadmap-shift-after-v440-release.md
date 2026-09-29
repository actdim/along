---
protocol: along
protocol_version: "4.4.1"
date: 2026-09-29
slug: roadmap-shift-after-v440-release
agent: claude-code
branch: main
commit: 27c6642
summary: Moved 19 open issues from the prematurely completed v4.4.0 milestone to a new v4.5.0 and shifted v4.5-v4.7 milestones to v4.6-v4.8
issues_advanced: [feat--entity-reference-integrity-gate]
issues_completed: [task--roadmap-shift-after-v440-release]
decisions: []
risks_logged: []
spikes_conducted: []
milestone: v4.4.0-multi-user-merge-automation
---

# Session: Roadmap shift after the v4.4.0 release

## Summary
The concurrent `v4.4.0` release marked its milestone completed with 19 of 20 target issues still open.
The open scope moved to a new `v4.5.0-multi-user-merge-automation`; the planned v4.5.0-v4.7.0 milestones
moved one minor up to v4.6.0-v4.8.0 so the merge automation stays next in line.

## Work Completed
- Added `REQ-8` to `feat--entity-reference-integrity-gate`: `along bump` must not complete a milestone with
  open target issues, and `progress_pct` must come from issue status.
- `task--roadmap-shift-after-v440-release`: mechanical rewrite with a one-off script (dry run first, then apply):
  3 milestone files renamed with `git mv`, 1 created, 1 trimmed, `milestone:` rewritten in 29 issue files.
- `v4.4.0-multi-user-merge-automation` keeps its slug (the tag is public) and gains a "Release Outcome" section.

## Verification
- `along doctor --entities`: 0 errors, 0 warnings.
- `along issue sync` recompiled `ISSUES.md`.
- Session logs and `HISTORY.md` were left unchanged; they record the names valid at the time.
