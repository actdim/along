---
protocol: along
protocol_version: "4.4.2"
slug: session-state-cross-session-leak
type: bug
status: done
completed: 2026-10-01
priority: critical
created: 2026-10-01
updated: 2026-10-01
agent: claude-code
tags: [session, gates, concurrency]
milestone: v4.5.0-multi-user-merge-automation
blocked_by: []
related: [bug--activity-trace-shared-across-sessions, feat--plan-approval-exit-plan-mode]
---

# Repo-level session state.json leaks active slug and plan approval across parallel sessions

## Problem
Several agent sessions in one repository are a normal workflow. `alongkit.session` keeps a
repository-level `.along/.session/state.json` with `active_slug`, `phase`, `plan_approved`;
`get_active_session_slug()` reads it first and falls back to the first in-progress blackboard in
`os.scandir` order. Consequences:
- Last writer wins: `along start` in session B changes which issue and approval session A's
  gates (`require_plan_approval`, `require_active_issue`, `doc_manual_lock`) see.
- The pointer is never cleared: `purge` removes only `.session/<slug>/`, so a new session inherits
  a stale `plan_approved: true` (seen in a consumer repo from 2026-09-27, and in this repo:
  `active_slug: rule-packs-local-extensions` with 8 leftover blackboards).
- With two in-progress blackboards the fallback is nondeterministic.

## Requirements
- REQ-1: Bind a slug to an agent session: `.along/.session/bindings/<runtime>--<session_id>.json`
  `{slug, runtime, session_id, bound_at}`. Written by `along start` / `along scratch init` when a
  session id is known (`CLAUDE_CODE_SESSION_ID`, `ALONG_SESSION_ID`, antigravity conversation id).
- REQ-2: Gates resolve the slug from the event's own binding (`event.conversation_id`); phase and
  approval come only from `.session/<slug>/state.json`.
- REQ-3: No binding: exactly one in-progress blackboard is used; several give no guess (gates
  report ambiguity and point at `along start <slug>`).
- REQ-4: The repository-level `state.json` no longer drives gate decisions.
- REQ-5: `purge` / `wrap` remove the slug's bindings; doctor reports and `along session gc` removes
  bindings older than N hours or pointing at missing blackboards.

## Acceptance Criteria
- [x] Two simulated sessions bound to different slugs get independent gate decisions
- [x] Purge clears bindings; stale global pointer has no effect
- [x] Automated tests passing
