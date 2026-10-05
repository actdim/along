---
protocol: along
protocol_version: "4.4.5"
slug: parallel-session-closeout
type: feat
status: open
priority: high
created: 2026-10-05
updated: 2026-10-05
agent: claude-code
tags: [session, parallel, wrap, commit, closeout]
blocked_by: [bug--commit-blocked-after-wrap, bug--session-records-not-captured]
related: [bug--commit-blocked-after-wrap, bug--session-records-not-captured]
---

# Close parallel sessions in one step: attribution, readiness, closeout command and approval

## Goal (user requirement, 2026-10-05)
Development runs on several issues in parallel, often in several agent sessions at once. Agents
may touch the same file; avoiding that is the user's concern, not something Along may assume.
When the user sees that the parallel agents are done, they must be able to say once, in any of
those sessions or in a fresh one: "close all sessions". Along must then have enough metadata to:
- find every session / issue still open in the repository;
- tell which ones are finished and which are not, and why;
- close the finished ones (session log with the full record, issue done, wrap);
- commit them without conflicts and without attributing work to the wrong issue;
- push.
Working strictly one isolated issue at a time must never be a precondition.

## What exists today (verified in code)
- Session bindings: `.along/.session/bindings/<key>.json` (`session.load_binding`,
  `save_binding`, `list_bindings`, `gc_bindings`, `resolve_active_session`): session key -> slug,
  `plan_approved`, `approved_slug`, `context`.
- Per-session activity trace: `.along/diagnostics/activity/<key>.json`
  (`hooks/predicates.py`: `get_activity_trace_path`, `load_activity_trace`, `record_tool_activity`):
  `edited_files` (capped at 200, only `is_source_edit` paths, so no `.along/` and possibly no
  docs), `last_edit_time`, `last_test_time`. Diagnostics are per machine and not in git.
- Blackboards `.along/.session/<slug>/` (`plan.md`, `research.md`, `execution_trace.md`,
  `reviews/`, `state.json`); in direct mode they hold only the scaffold
  (see `bug--session-records-not-captured`).
- `along commit` supports `--paths <file>...` (stage only these) besides `--all`
  (`scripts/along_commit.py`).
- No `along issue reopen`: reopening `bug--commit-blocked-after-wrap` today needed a manual
  `git mv` from `ISSUES/done/` back to `ISSUES/`.

## What is missing
1. Edits are attributed to a session, not to an issue: a session that switches issues mixes their
   files; `.along/` and docs edits are not traced at all.
2. No readiness signal: tests after the last edit, acceptance criteria ticked, plan recorded.
3. Wrap leaves no trace of a finished approved issue (handled by `bug--commit-blocked-after-wrap`).
4. Plan and execution are not recorded (handled by `bug--session-records-not-captured`).
5. No command that does the whole closeout, and no approval form for "close these issues".

## Requirements
- REQ-1 Attribution: every traced edit records `{path, slug, ts}` with the session's active issue
  at that moment (all repository paths, including `docs/` and `.along/` entity files, tagged by
  kind: source / docs / state). Test runs record `{ts, ok, slug}`. Cap by count per slug, not a
  global 200.
- REQ-2 Durable attribution: because diagnostics are per machine and untracked, the per-issue
  file list is also written into the issue's blackboard (`execution_trace.md` / `state.json`) so a
  closeout from another session on the same machine sees it, and into the session log at wrap.
- REQ-3 Readiness: `session.closeout_status(repo_root) -> List[dict]` covering every in-progress
  issue, every binding, every orphan blackboard. Per item: sessions, attributed files (exclusive /
  shared with which issues), uncommitted changes not attributed to anyone, last edit vs last
  green test, acceptance criteria ticked/total, plan recorded (not scaffold), verdict
  `ready` / `blocked` with reasons.
- REQ-4 `along session list [--json]`: prints REQ-3 for the repository (and nested contexts).
- REQ-5 `along session close [<slug>...] | --ready [--dry-run] [--push]`:
  1. refuse during a merge/rebase or with conflict markers;
  2. for each selected ready issue: archive the blackboard into its session log
     (`archive_and_purge` from `bug--session-records-not-captured`), `issue done`, wrap without
     per-issue test runs, record a completion token;
  3. run the test suite once for the whole closeout; stop before committing if it fails;
  4. commit grouping: files attributed to exactly one closed issue -> one commit per issue
     (`along commit --paths ... -i <slug>`); files shared by several closed issues -> one combined
     commit with all their refs; entity/projection files (`ISSUES.md`, `HISTORY.md`, session logs)
     -> with their issue, projections in the last commit; files not attributed to any closed issue
     are never committed, only reported;
  5. push once at the end with `--push`;
  6. idempotent: a re-run after a partial failure continues where it stopped;
  7. issues not ready are left untouched and listed with their blockers.
- REQ-6 Closeout approval: `along plan approve --closeout <slug>... | --ready` (run only after the
  user's explicit yes) records the approved set in this session's binding; the commit gate
  (`bug--commit-blocked-after-wrap` REQ-5) accepts commits of those slugs; the approval is
  consumed by the closeout. Works from a fresh session with no binding.
- REQ-7 `along issue reopen <slug>`: moves the file from `ISSUES/done/` to `ISSUES/`, sets
  `status: open`, removes `completed`, recompiles `ISSUES.md`.
- REQ-8 One test run per completion: wrap and commit reuse a green run when the tree has not
  changed since (tree hash recorded with the run); today wrap and commit each run the full suite
  (about 2 min each).
- REQ-9 `along doctor` reports bindings older than the gc age, orphan blackboards, and issues
  in progress with no binding.

## Implementation plan
Prerequisites: `bug--commit-blocked-after-wrap` (completion tokens, narrowed commit gate) and
`bug--session-records-not-captured` REQ-1..REQ-3 (plan capture, direct-mode trace,
`archive_and_purge`). Execution mode: Role-Based (`along-team`), steps and reviews on the
blackboard.
1. Attribution (REQ-1, REQ-2): extend `record_tool_activity` (trace schema version field, migrate
   old traces on read); mirror per-issue file lists into the blackboard; `is_source_edit` stays
   for test-before-stop, attribution uses all repository paths.
2. Readiness (REQ-3): new module `scripts/alongkit/closeout.py` (pure functions over bindings,
   traces, blackboards, issues, `git status --porcelain -z`); AC parsing reuses the issue parser.
3. CLI (REQ-4, REQ-5, REQ-7): `along session list|close`, `along issue reopen` in
   `scripts/along_exec.py`; commit grouping calls `along_commit` with `--paths`; transactional per
   commit (`alongkit.transaction.FileTransaction` for entity moves).
4. Approval (REQ-6): `session.record_closeout_approval`, read by the commit gate.
5. Test reuse (REQ-8): record `{tree_hash, ok, ts}` per run in the diagnostics dir; wrap/commit
   gates skip the run when the hash matches a green run.
6. Doctor (REQ-9).
7. Tests: hermetic git fixtures with two simulated sessions on two issues: exclusive files, one
   shared file, one unattributed file, one not-ready issue; assert commits, refs, untouched files,
   idempotent re-run, failure before commit when tests fail, fresh-session closeout with approval,
   reopen.
8. Docs: new `docs/topic--parallel-sessions.md` (guide: working in parallel, closing out),
   `docs/topic--cli-reference.md`, `docs/topic--runtime-hooks-and-gates.md`, AGENTS.md / protocol
   template line about closing parallel sessions.

## Acceptance Criteria
- [ ] REQ-1..REQ-9 covered by hermetic tests, positive and negative.
- [ ] Scenario test: two sessions, two issues, one shared file, one unrelated change -> one closeout command closes both, three commits (two exclusive, one combined), the unrelated change stays uncommitted, push once.
- [ ] Docs written.
- [ ] Automated tests passing.

## Findings from 2026-10-05 to file as separate issues
- F1: `along update --dry-run` does not show each context's migration plan.
- F2: `migrate_protocol._should_run_migrations` re-runs the full chain whenever `.agents/` exists, even if it holds only `.gitkeep`.
- F3: release tags not pushed: filed by a parallel session as [bug--release-tags-not-pushed] (which also pushed `v4.4.5` by hand). Still open: 7 commits landed after `v4.4.5` under the same version; release 4.4.6 pending (Step 14 label `[v4.4.5]` should become `[v4.4.6]`).
- F4: `packages/dashboard-ui/AGENTS.md` carries no protocol version marker (detected as v1.0.0).
- F5: `.gitattributes` keeps a stale `.along/DECISIONS.md merge=union` line, overridden by the managed block.
- F6: wrap and commit each run the full test suite (covered here by REQ-8).
- F7 (git part filed as [bug--plan-gate-blocks-readonly-git]): the plan gate's read-only classifier does not know PowerShell cmdlets (`Get-Content`, `Select-String`, `Get-ChildItem`); an unbound session cannot even read command output on Windows. Also `cmd 2>&1 | Out-String` around an Along state command makes it unrecognised.
