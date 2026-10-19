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
  issue started; an accepted plan also carries to a newly started slug until the user's next
  message (the plan is recorded under the new slug).
- **Elsewhere**: after the user's explicit yes, write the plan to a file and run
  `along plan approve <slug> --plan-file <path>`, or write it into `plan.md` yourself and run
  `along plan approve <slug>`.
- Approval is refused while `plan.md` is still the scaffold `along start` created.
- Where user messages are recorded (Claude Code `UserPromptSubmit` hook, in
  `.along/.session/prompts/<key>.json`), a CLI approval is refused when the plan file changed
  after the user's last message: show the plan and wait for a reply. With no recorded message
  it passes as `approved_via: cli-unverified`. The binding records `approved_via`
  (`exit-plan-mode`, `cli`, `cli-unverified`), `approved_at` and `plan_sha256`.
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
  `--force-reason "..."` says why; the reason is kept in the trace and the session log.
- `along wrap` runs every check before its first write, so a failed wrap leaves the tree unchanged:
  - Role-based steps (no open steps or missing reviews);
  - Approved living plan recorded (not a scaffold);
  - Issue and plan checklists: verifies that all `- [ ]` checklist items in the issue's `## Acceptance Criteria` and in the living plan `plan.md` are completed (`- [x]`); open checklist items abort wrap unless `--force-reason` is passed;
  - Pre-flight automated tests (or green test run reuse);
  - Zero-byte audit across the working tree;
  - Entity reference integrity (`--force-reason` passes the check).
  KB sync runs after the transaction commits and only warns when it fails.
- Template placeholders (scaffold plan, empty research headings, the generic step list) are not
  written as content: a missing plan shows as `No plan recorded.` Non-scaffold findings (`research.md`)
  and notes (`notes.md`) are preserved under `### Research` and `### Notes`.
- Purge operations refuse across all commands (`along wrap`, `along scratch purge`, `along issue done`,
  `along session close`) if an unknown non-scaffold file is present in the blackboard.
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
  `along scratch purge <slug>` archives and removes one. Run `along doctor issues` to audit scaffold stubs.

## 6. Committing wrapped work

- **Atomic wrap auto-commit**: By default, `along wrap` automatically creates an atomic Git commit linked to the wrapped issue slug (`<type>: <summary> (refs #<slug>)`), bundling all attributed files, the moved issue file in `done/`, today's session log, and recompiled projections. Engine-written files carry no edit events, so two rules cover them. The managed `docs/topic--along-protocol.md` counts as a projection. A changed `AGENTS.md` (root or nested) is included when its only difference from `HEAD` lies inside the managed `ALONG-PROTOCOL` / `ALONG-RULES` blocks; a hand edit outside them leaves it to attribution. `along session close` applies the same rules.
- **Opting out with `--no-commit`**: When `--no-commit` is passed, `along wrap` leaves changes uncommitted. The wrap purge removes the session's binding but preserves a completion token, so a subsequent manual `along commit -i <slug> --paths ...` passes the plan gate without a new approval and consumes the token.
- **Parallel closeout**: Several issues finished in parallel are closed in one step with `along session close`; the record of each one then also lists its attributed files. See [Parallel Sessions](./topic--parallel-sessions.md).
