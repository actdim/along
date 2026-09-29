---
protocol: along
protocol_version: "4.4.1"
slug: roadmap-shift-after-v440-release
type: task
status: done
completed: 2026-09-29
priority: high
created: 2026-09-29
updated: 2026-09-29
agent: claude-code
tags: [milestones, roadmap, entities]
milestone: v4.4.0-multi-user-merge-automation
blocked_by: []
related: [feat--entity-reference-integrity-gate]
---

# Carry v4.4.0 open scope to new v4.5.0 and shift v4.5-v4.7 milestones

## Context

The `v4.4.0` release (`c1ed519`) set `v4.4.0-multi-user-merge-automation` to `completed` / 100% although only
`feat--suppress-ai-coauthor-attribution` had shipped and 19 of its 20 target issues were open. The tag is
published, so the milestone keeps its name and records what actually shipped. The engine defect itself is
tracked as `REQ-8` of `feat--entity-reference-integrity-gate`.

## Changes

- New milestone `v4.5.0-multi-user-merge-automation` (open) with the 19 carried issues and the original merge-automation plan.
- `v4.4.0-multi-user-merge-automation`: `target_issues` trimmed to what shipped, plus a "Release Outcome" section.
- Roadmap shifted one minor up, slugs, titles, headings and issue `milestone:` fields rewritten:
  - `v4.5.0-structured-state-and-blackboard-engine` -> `v4.6.0-structured-state-and-blackboard-engine` (5 issues)
  - `v4.6.0-clean-turn-agent-loops-and-state-recovery` -> `v4.7.0-clean-turn-agent-loops-and-state-recovery` (2 issues)
  - `v4.7.0-empirical-benchmarking-and-publications` -> `v4.8.0-empirical-benchmarking-and-publications` (3 issues)
- Session logs and `HISTORY.md` keep the names that were valid when written.

## Acceptance Criteria
- [x] No open issue targets a completed milestone
- [x] `along doctor --entities` reports 0 errors
- [x] Automated tests passing
