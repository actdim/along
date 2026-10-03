---
protocol: along
protocol_version: "4.4.2"
slug: along-team-step-enforcement
type: feat
status: done
completed: 2026-10-01
priority: high
created: 2026-10-01
updated: 2026-10-01
agent: claude-code
tags: [along-team, gates, session]
milestone: v4.5.0-multi-user-merge-automation
blocked_by: [bug--session-state-cross-session-leak]
related: [feat--structured-blackboard-state-machine]
---

# Mechanical enforcement of along-team step loop and reviews

## Problem
The along-team skill prescribes Scout, Implementer and Reviewer roles, `scratch update`,
`reviews/step-N.md` and `execution_trace.md`, but nothing checks them. Without enforcement an
agent skips the loop and the blackboard stays empty (seen 2026-10-01 in a consumer repo).

## Requirements
- REQ-1: PreToolUse: when the session's blackboard has steps, source edits are denied unless a
  step is `in-progress`.
- REQ-2: Stop and `along scratch purge` refuse while steps are not `passed` or a passed step lacks
  `reviews/step-N.md` (`--force` with a reason recorded in `execution_trace.md`).
- REQ-3: Single-agent fallback is allowed only with a recorded reason in `execution_trace.md`.

## Acceptance Criteria
- [x] Edits without an in-progress step are denied
- [x] Purge refuses incomplete steps
- [x] Automated tests passing
