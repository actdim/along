---
protocol: along
protocol_version: "4.4.6"
slug: uncommitted-issue-deleted-without-trace
type: bug
status: open
priority: medium
created: 2026-10-07
updated: 2026-10-07
agent: claude
tags: [entities, integrity, gates]
milestone: v4.5.0-multi-user-merge-automation
blocked_by: []
related: [feat--entity-reference-integrity-gate, task--release-v4-4-7]
---

# Uncommitted issue file deleted without supersede or trace

## Problem

Session `claude--be725b0a` bound `monorepo-update-gate-friction`, edited
`.along/ISSUES/bug--monorepo-update-gate-friction.md` (execution trace 2026-10-06T18:38:41Z),
then split the work into five bugs. The umbrella issue file is gone: not on disk, never in
git, no `superseded_by`, no session log until the orphan blackboard was archived at the
`release-v4-4-7` closeout. The entity-reference gate did not fire because nothing referenced
the file, and the deletion of an untracked entity file leaves no git trace either.

## Requirements

- REQ-1: Deleting an issue / ADR / milestone / risk / spike file (tracked or not) through
  the agent's tools is rejected; the remediation names `along issue supersede` /
  `along issue rename` (split: supersede into several keys).
- REQ-2: `along issue supersede <slug> --by a,b,c` supports a split into several issues.
- REQ-3: A blackboard whose issue file is missing is reported with the last trace entry
  that touched the file (`along doctor`).

## Acceptance Criteria
- [ ] Hermetic test: deleting an untracked issue file is rejected
- [ ] Supersede to several successors works and keeps the original in `done/`
- [ ] Automated tests passing
