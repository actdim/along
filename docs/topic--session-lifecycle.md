---
protocol: along
slug: session-lifecycle
title: Session & Blackboard Lifecycle Guide
type: guide
created: 2026-10-06
updated: 2026-10-06
tags: [session, blackboard, plan, trace, wrap, purge, issue-done, session-log, gates]
---

# Session & Blackboard Lifecycle Guide

How the working record of an issue is kept from `along start` to the committed session log, and
which commands and gates keep it from being lost. Command details are in the
[CLI Reference](./topic--cli-reference.md); the gates are in
[Runtime Hooks & Gates](./topic--runtime-hooks-and-gates.md).

## 1. The blackboard

Each issue in progress has a blackboard in `.along/.session/<slug>/` (not tracked by git):

| File | Content | Written by |
| --- | --- | --- |
| `state.json` | phase, approval, execution mode, steps, retries | `along start`, `along scratch`, approval |
| `plan.md` | the approved plan, with `## Revision N` sections | `ExitPlanMode`, `along plan approve --plan-file`, the agent |
| `research.md` | findings (role-based work) | the agent |
| `execution_trace.md` | edits, test runs and results, gate denials, approvals, phase and step changes | hooks and Along commands |
| `events.jsonl` | the event ledger: one record per edit, test run, plan and approval, used for attribution | hooks and Along commands |
| `reviews/step-N.md` | step verdicts (role-based work) | the agent |

`along start` creates a `direct` blackboard, `along scratch init` a `role-based` one (held to the
along-team step loop). Both are recorded the same way; `direct` only means "no step loop".

## 2. Recording the plan

The plan the user approved is part of the record:

- **Claude Code**: accepting a plan with `ExitPlanMode` stores its text in `plan.md` of the bound
  issue. A plan accepted before `along start` waits in the session binding and goes to the first
  issue started.
- **Elsewhere**: after the user's explicit yes, write the plan to a file and run
  `along plan approve <slug> --plan-file <path>`, or write it into `plan.md` yourself and run
  `along plan approve <slug>`.
- Approval is refused while `plan.md` is still the scaffold `along start` created.
- A revised plan is appended as the next `## Revision N`; earlier revisions stay.

```bash
along start token-refresh
along plan approve token-refresh --plan-file plan.md
```

## 3. The execution trace

The trace of the issue the session is bound to is written automatically:

- every repository edit made with the agent's file tools (repeated edits of one file collapse to
  `(xN)`); the blackboard and diagnostics themselves are left out;
- `along test` runs and the test gates of `along wrap` / `along commit`, with pass or FAIL;
- gate denials (gate id and the first line of the reason);
- plan recorded and approved; phase, step-status and retry changes.

Raw test runners (`pytest`, `npm test` called directly) are not traced; use `along test`. A
session that is not bound to an issue writes no trace. The newest 400 entries are kept.

## 4. Closing an issue

Every way a blackboard leaves the repository writes it into the issue's session log
`.along/SESSIONS/<YYYY>/<date>--<slug>.md` first, as a `## Blackboard Record` section:

| Command | Session log | Blackboard |
| --- | --- | --- |
| `along wrap <slug> --no-decisions -m "..."` | record, `issues_completed`, decisions | purged after the wrap committed |
| `along issue done <slug>` | record (if any), `issues_completed` for `done` | purged after the move committed |
| `along scratch purge <slug> [--force --reason "..."]` | record, with the reason when forced | purged after the log is written |

- `along wrap` refuses a blackboard whose plan was never recorded, unless
  `--force-reason "..."` says why; the reason is kept in the trace.
- Template placeholders (scaffold plan, empty research headings, the generic step list) are not
  written as content: a missing plan shows as `No plan recorded.`
- A second record of the same issue on the same day is appended as
  `## Blackboard Record (<n>, <timestamp>)`.

## 5. Checks that keep the record

- **wrap-before-stop** (end of turn): every issue closed as `done` today must be listed in
  `issues_completed` of a session log of today. Fix a gap with `along wrap <slug> --no-decisions`,
  which also works for an issue already in `done/`.
- **session-record-append-only** (`along commit`, `along gates check`, CI): a change may not
  remove or rewrite lines inside a `## Blackboard Record` of a committed session log. The Summary
  and Decisions sections stay editable.
- **`along doctor`**: warns about orphan blackboards (no session bound, issue closed or missing).
  `along scratch purge <slug>` archives and removes one.

## 6. Committing after wrap

`along wrap` removes the session's binding. The session that wrapped an issue with an approved
plan keeps a completion token, so `along commit -i <slug> --paths ...` passes the plan gate right
after the wrap; the commit uses the token up.

Several issues finished in parallel are closed in one step with `along session close`; the
record of each one then also lists its attributed files. See
[Parallel Sessions](./topic--parallel-sessions.md).
