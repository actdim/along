---
protocol: along
slug: parallel-sessions
title: Parallel Sessions & Closeout Guide
type: guide
created: 2026-10-06
updated: 2026-10-06
tags: [session, parallel, closeout, attribution, ledger, commit, readiness, approval]
---

# Parallel Sessions & Closeout Guide

How several agent sessions work on several issues in one working tree, and how the user closes
the finished ones in one step: "close all sessions". Working on one isolated issue at a time is
never required. The record kept for each issue is described in
[Session Lifecycle](./topic--session-lifecycle.md); commands are in the
[CLI Reference](./topic--cli-reference.md).

## 1. Working in parallel

- Each agent session binds itself to its issue with `along start <slug>`; parallel sessions keep
  their own bindings (`along session bindings`).
- Sessions may touch the same files. Avoiding that is the user's concern; Along records who
  touched what.
- Every edit made with the agent's file tools is attributed to the issue the session is bound to:
  one record in that issue's event ledger (`.along/.session/<slug>/events.jsonl`) with the path,
  its kind (`source`, `docs`, `state`) and the session. Test runs (`along test`, the wrap and commit
  test gates) are recorded with their result.
- A session that is not bound to an issue attributes nothing: its edits show up as unattributed
  changes.
- Changes made by shell commands (`sed`, code generators, `git mv`) are not seen by the hooks and
  are unattributed too. Make edits with the file tools, or commit such changes yourself.

## 2. Is it finished?

```bash
along session list
along session list --json
```

For every issue in progress, every bound issue and every blackboard it shows:

| Field | Meaning |
| --- | --- |
| sessions | bound sessions and the time of their last recorded event |
| files | attributed files: exclusive, or shared with which other issues; how many are still uncommitted |
| tests | the last test run and its result, compared with the last edit |
| criteria | acceptance criteria ticked / total (`## Acceptance Criteria` of the issue) |
| plan | whether the approved plan was recorded |
| verdict | `ready`, or `blocked` with the reasons |

An issue is `blocked` when its plan was never recorded, no test ran after its last edit, the last
run failed, criteria are unticked, its blackboard or issue is missing, or its ledger could not be
written. For the repository it lists unattributed changes, staged files, a merge or rebase in
progress and conflict markers.

Uncommitted files left behind by issues that were previously wrapped are grouped separately by their
done issue key (with commit and closeout commands suggested in `along session list` and `along doctor`),
rather than being mixed into generic unattributed changes.

`along session list` cannot know whether a parallel agent is still typing: the last-event time of
each session is shown, and the user decides.

## 3. Closing out

1. Show the user `along session list` (or `along session close --ready --dry-run`, which prints
   the commit plan and writes nothing).
2. After the user's explicit yes, record the approval in the session that will close out (a fresh
   session works too):

   ```bash
   along plan approve --closeout --ready
   ```

   or name the issues: `along plan approve --closeout alpha beta`.
3. Close out:

   ```bash
   along session close --ready --push
   ```

What `along session close` does:

1. Refuses during a merge, rebase, cherry-pick or revert, with conflicts, with files already
   staged, or without the approval for every issue it would close.
2. Plans the commits from the attribution, before anything changes.
3. Runs the test suite once. If it fails, nothing is wrapped or committed.
4. Wraps each issue: the blackboard (with its attributed files) goes into the session log, the
   issue moves to `done/`, `HISTORY.md` gets a line.
5. Commits by attribution, each commit through `along commit` with its gates:
   - files attributed to one issue: one commit for that issue, with its issue file and session log;
   - files attributed to several closed issues: one combined commit with all their refs;
   - projections (`ISSUES.md`, `HISTORY.md`, KB indexes and what the wraps' KB sync rewrote): last.
6. With `--push`, pushes once at the end.

The test gate of each commit reuses the closeout's green run: the wraps change only Along state
and documentation. A source change made while the closeout runs makes the commits run the tests
again.

Never committed: unattributed changes, and files that are also attributed to an issue that is not
being closed now (held back until that issue closes). Issues that are not ready are listed with
their blockers and left untouched.

Done issues with uncommitted attributed files: `along session close <done-slug>` can also be invoked
directly for an issue that was already wrapped. It reconstructs the attributed file list from the
issue's session log (`## Attributed Files` table) and commits those files cleanly without re-wrapping.

## 4. When something fails

- The run is saved in `.along/.session/.closeout.json`. Fix the cause and run
  `along session close` again: wrapped issues are not wrapped twice, finished commits are skipped.
- A closed issue that needs more work: `along issue reopen <slug>`, then `along start <slug>`.
- `along doctor` reports stale bindings, issues in progress that no session is bound to, and
  orphan blackboards.

## 5. Limits

- Attribution lives on the machine where the work was done (blackboard ledger) and, after the
  wrap, in the committed session log. A closeout on another machine sees only what was archived.
- The closeout approval lapses after 72 hours, like a session binding.
