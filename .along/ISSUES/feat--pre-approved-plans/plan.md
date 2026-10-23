# Living Plan: pre-approved-plans

## Revision 1 (2026-10-23T15:59:05Z, ExitPlanMode)

Execution Mode: Direct (one feature - the issue plan and its status - threaded through entities, CLI, gate and orchestrator; each piece is small and depends on the previous one, so a role split would only pass the same context back and forth)

### Context
The user wants: a detailed ticket; then, with the agent, a plan saved next to the ticket; the
ticket marked "plan ready"; later "do it" (chat or Telegram/daemon) runs the plan with no
second approval and no re-planning. The user never types commands - the agent runs the CLI.

Decisions taken in discussion:
- No staleness tracking, no hashes. A plan is valid until someone says otherwise; agents
  correct it during work themselves and record each revision; the user is asked only when
  the ticket itself cannot be met as written.
- Plans live under the issue, in a folder named after it, committed to Git.
- One guard against self-approval (the `bug--plan-approval-self-approval-bypass` lesson):
  only the CLI, after the user's approval, sets `approved`; file-tool edits that set it are
  denied; an approval with no local approval event is not trusted (asked again).

### Model
```text
.along/ISSUES/feat--x.md               ticket (what/why); front-matter plan_status: <state>
.along/ISSUES/feat--x/plan.md          plan (how); moves with the ticket (done/, rename, supersede)
.along/.session/plan-approvals.jsonl   local, git-ignored, CLI-only approval events
```
`plan_status`: absent (no plan) | `needs-approval` | `approved` | `needs-rework`.
- The agent may set `needs-approval` / `needs-rework` (file edit or CLI).
- `approved` only through `along plan approve`, which appends an approval event.
- `approved` in the ticket + event on this machine = run without asking; without an event
  (other machine, or set by hand) = show the plan and ask once in the current channel;
  an autonomous run stops with `needs-input`.

### The plan is living (direct and along-team alike)
One file, `ISSUES/<key>/plan.md`, for the whole life of the issue: approved baseline, then
corrections appended as revisions with a reason. Escalation boundary is the ticket, not the
plan: deviations the agents can resolve within the ticket's requirements are resolved and
recorded (`along plan revise`); only a ticket-level problem goes to the user (`along plan rework`).

### Steps
- Step 1: Entities - issue folder helpers; `move_issue_folder` wherever a ticket moves; `plan_status` in the schema; board markers.
- Step 2: Session/approval API - approval log `.along/.session/plan-approvals.jsonl`; `APPROVED_VIA_ISSUE_PLAN`.
- Step 3: CLI - `plan approve` ahead of start; `plan revise`; `plan rework`; `plan status [<slug>]`; `along start` uses a ready plan; ExitPlanMode for a bound slug also approves the issue plan.
- Step 4: Gate - approval log closed to file tools; file-tool edits setting `plan_status: approved` denied; shell-written approvals reported at Stop.
- Step 5: Orchestrator / daemon - approved plan replaces the architect; unconfirmed plan -> `needs-input`; briefs carry the plan rule.
- Step 6: Tests - `tests/test_issue_plans.py`, written first and run red.
- Step 7: Docs - ADR; protocol reference; domain model; along-team skill.

## Revision 2 (2026-10-23T18:30:00Z, during implementation)

Reason: corrections within the ticket found while implementing; no requirement changed.

- `along start` does not copy the plan: `session.plan_path` already resolves to the issue
  plan. A plan written into an issue's blackboard `plan.md` (older instructions, sessions
  begun before this change) is moved into the issue folder on first use.
- The Stop check reports a ticket saying `approved` whose approval log does not end with an
  approval for it (not "since the turn baseline"): a ticket approved earlier and edited for
  another reason in a later turn must not be reported.
- `needs-approval` also halts the orchestrator with `needs-input` (it never approves for the user).
- Files in issue folders are not tickets: `entities.is_issue_ticket_path` keeps the commit-time
  issue stub gate and the recursive entity scans off `ISSUES/<key>/plan.md`; closeout
  attributes the issue folder's files to their issue (`closeout.issue_folder_files`).
- The orchestrator initializes a blackboard for an issue run straight from the daemon: the
  claim lives in `state.json`, so such a run returned `blocked` before.
- `docs/topic--along-protocol.md` is the rendered copy of `skills/along-init/protocol-reference.md`
  (and `write_policy: manual`): edited the template, regenerated the doc with `along init`.
  Also updated `docs/topic--cli-reference.md` and `docs/topic--runtime-hooks-and-gates.md`;
  `skills/along-issue-sync` has no plan text to change.
