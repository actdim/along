---
protocol: along
protocol_version: "4.5.2"
slug: pre-approved-plans
type: feat
status: done
completed: 2026-10-23
priority: high
created: 2026-10-23
updated: 2026-10-23
agent: claude-code
tags: [gates, autonomous, approval]
blocked_by: []
related: [bug--plan-approval-self-approval-bypass, feat--autonomous-gate-profile]
---

# Pre-approved plans: approve an issue's plan ahead of along start

A user wants to write a detailed plan for an issue in advance, approve it once, and later
have `along start <slug>` (run by a human, or by the orchestrator / runner daemon in
autonomous mode) begin execution without asking for approval again.

Today a plan approval belongs to one agent session and its blackboard: it comes from
`along start --approved`, `along plan approve` or ExitPlanMode, and `along wrap` purges it.
An issue cannot be approved before it is started. Commit a8ea884 tried issue front-matter
`plan_approved: true`; that let an agent approve its own plan and was removed by
`bug--plan-approval-self-approval-bypass`.

Also, the plan itself was not kept: it lived in the git-ignored blackboard and `along wrap`
did not copy it into the session log.

Design agreed with the user (see ADR-2026-10-23--issue-plans-approved-ahead): the plan is a
committed artifact next to the ticket; the ticket's `plan_status` says where it stands; only
the CLI sets `approved`. No hashes and no staleness tracking: agents correct the plan during
work and record revisions; only a problem the ticket cannot absorb goes to the user.

## Requirements
- REQ-1: An issue's plan MUST live in `.along/ISSUES/<key>/plan.md`, committed, moving with the ticket (done, reopen, rename, supersede; removed on delete); blackboards and along-team MUST read and write it through `session.plan_path`.
- REQ-2: `along plan approve <slug>` before `along start` MUST approve the plan ahead (from `--plan-file`, an unbound ExitPlanMode acceptance, or the existing issue plan) without starting the issue: ticket `plan_status: approved` plus an approval event in `.along/.session/plan-approvals.jsonl`, held to the same user-message check as `session.check_cli_approval` (`cli-unverified` when no user message is recorded).
- REQ-3: `along start <slug>` MUST run an approved plan with an approval event on this machine without a second approval; `approved` without an event, `needs-rework` or no plan MUST leave the session in planning.
- REQ-4: The `require-plan-approval` gate MUST deny file-tool edits that set `plan_status: approved` and file-tool writes to the approval log, and MUST report at Stop a ticket set to `approved` with no logged approval.
- REQ-5: `along plan revise` MUST append a correction as the next plan revision with its reason, keeping the status; `along plan rework` MUST set `needs-rework` and return a started session to planning.
- REQ-6: The orchestrator MUST use an approved plan confirmed on this machine instead of running and self-approving the architect, and MUST stop with `needs-input` for an unconfirmed, unapproved or needs-rework plan.

## Acceptance Criteria
- [x] Approve ahead, then `along start`: the session is approved, phase `execution`, the plan is the issue plan.
- [x] Hand-written `plan_status: approved` (no logged approval): `along start` leaves the session unapproved.
- [x] A file-tool edit setting `plan_status: approved` and a write to the approval log are denied; a shell write is reported at Stop.
- [x] Approval with no recorded user message is logged as `cli-unverified`; a plan newer than the user's last message is refused.
- [x] The orchestrator skips the architect with an approved plan and stops with `needs-input` for an unconfirmed one.
- [x] The issue folder moves with the ticket on done, reopen and rename.
- [x] The new tests ran red before the feature (16 of 18 failed; the other 2 guard behaviour that already held: no plan, and a blackboard without an issue); `python .along/scripts/test.py -q` is green (1590 tests).
- [x] `docs/topic--along-protocol.md` documents the flow; an ADR records the decision.

## Notes
- The approval log is machine-local and git-ignored: an approval does not travel between
  machines; on another machine (e.g. the VPS daemon) the user confirms once in the current channel.
- The guard raises the bar, it is not absolute: an agent with a shell can still forge the log.
- The orchestrator now initializes a blackboard for an issue run straight from the daemon
  (its claim lives in `state.json`; before, such a run returned `blocked`).
