---
protocol: along
protocol_version: "4.5.2"
slug: plan-approval-self-approval-bypass
type: bug
status: in-progress
priority: high
created: 2026-10-23
updated: 2026-10-23
agent: claude-code
tags: [security, gates, regression, risk]
blocked_by: []
related: [feat--autonomous-gate-profile, bug--commit-blocked-after-wrap]
---

# Plan gate accepts agent-written approval markers

`feat--autonomous-gate-profile` (commit a8ea884) extended `session.is_plan_approved` with
role-approval checks that run in every profile, not only `autonomous`:

- `approved_by` / `plan_approval` in the blackboard `state.json`;
- `status: approved`, `approved: true`, `approved_by: architect` matched by regex in `plan.md`;
- `plan_approved: true` / `approved_by` / `plan_approval` in the issue front-matter.

All of these files sit on the plan gate's own whitelist (`.along/ISSUES/**`,
`.along/.session/**`), so an agent can approve its own plan by writing one line, e.g. adding
`plan_approved: true` to its issue file under the standard profile. The new block also returns
before the session-ownership check, regressing `bug--commit-blocked-after-wrap`: an issue
front-matter marker outlives the session and approves any later or unbound session.

The approval records the gate does trust (the session binding and `state.json`
`plan_approved`, written by `along plan approve` / `along start --approved` / the orchestrator
through `session.approve_plan`) are also writable through file tools, because
`.along/.session/**` is whitelisted wholesale.

## Requirements
- REQ-1: `is_plan_approved` MUST NOT treat `plan.md` text, issue front-matter, or `state.json` `approved_by` / `plan_approval` as plan approval in any profile.
- REQ-2: Under the autonomous profile, `is_plan_approved` MUST accept only `state.json` `plan_approved: true` written by `session.approve_plan` (the orchestrator / `along plan approve`), and only for a session that owns the slug.
- REQ-3: `is_plan_approved` MUST apply the session-ownership check (binding slug or runner `ALONG_ISSUE_SLUG`) before any blackboard approval counts, in every profile.
- REQ-4: The `require-plan-approval` gate MUST deny file-tool writes to approval records (`.along/.session/bindings/**`, `.along/.session/*/state.json`) in any context, bound or unbound.

## Acceptance Criteria
- [x] Writing `plan_approved: true` into the issue front-matter does not approve the plan (standard and autonomous profiles).
- [x] `status: approved` / `approved_by: architect` in `plan.md` does not approve the plan.
- [x] `approved_by: architect` in `state.json` without `plan_approved: true` does not approve the plan.
- [x] A worker session with `ALONG_ISSUE_SLUG` set to the slug is approved under the autonomous profile when `session.approve_plan` ran; a session owning another slug is not.
- [x] A PreToolUse write by a file tool to `.along/.session/bindings/<key>.json` or `.along/.session/<slug>/state.json` is denied by `require-plan-approval`.
- [x] Regression tests cover each criterion; `python .along/scripts/test.py` is green.

## Notes
- Out of scope (separate findings from the same review): who may switch on the autonomous
  profile (env / payload `profile`), shell-command writes to approval records (the Stop-time
  check does not classify `.along/` state), and the orchestrator's architect self-approval.
