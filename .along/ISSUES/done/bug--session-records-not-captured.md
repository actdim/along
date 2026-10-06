---
protocol: along
protocol_version: "4.4.5"
slug: session-records-not-captured
type: bug
status: done
completed: 2026-10-06
priority: high
created: 2026-10-05
updated: 2026-10-06
agent: claude-code
tags: [session, blackboard, wrap, gates]
blocked_by: []
related: [bug--diagnostics-files-stay-tracked, bug--commit-blocked-after-wrap, feat--parallel-session-closeout]
---

# Session blackboards are lost: direct mode records nothing, issue done and scratch purge drop them

The session blackboard (`.along/.session/<slug>/`: `plan.md`, `research.md`, `execution_trace.md`,
`reviews/`, `state.json`) is the working record of an issue; `along wrap` renders it into the
session log ("Blackboard Record") before purging it. In practice nothing reaches the log:

- **Direct mode records nothing.** `along start` creates a `direct` blackboard holding only the
  scaffold (`Step 1: Step 1`, empty research). The approved plan stays in chat: neither
  `along plan approve` nor the Claude Code `ExitPlanMode` path writes it to `plan.md`, and no
  edit, test run or decision is traced. `direct` only means "not held to the along-team step
  loop", yet it silently turns the whole record off.
- **Wrap records the scaffold as if it were content** (a `Step 1 | pending` table, empty
  headings) and still purges.
- **`along issue done` closes an issue without its record.** Its blackboard is left behind,
  unbound; nothing renders it into any log.
- **`along scratch purge` deletes a direct blackboard unconditionally** (`shutil.rmtree`), with
  no copy and no check. Observed: five blackboards of closed issues were purged without being
  inspected; their content, if any, is gone.
- **wrap-before-stop is satisfied by any session log of the day**, not by a log that records
  each issue completed that day, so issues closed in bulk pass.
- **A session log can be rewritten by hand** and lose its Blackboard Record without any check.

## Requirements
- REQ-1: The approved plan is recorded: `along plan approve` writes the plan text into the
  blackboard `plan.md` (`--plan-file <path>`), refuses while `plan.md` is still the scaffold, and
  the Claude Code `ExitPlanMode` hook path stores the plan from the tool input automatically.
  Plan revisions are kept (revision history in `plan.md`), not overwritten.
- REQ-2: Direct mode keeps an execution trace automatically, from the hooks, independent of the
  agent: files edited (PostToolUse), test runs and their result, gate denials, plan approval,
  phase changes. Wrap renders it.
- REQ-3: A blackboard is never deleted without being recorded: one `archive_and_purge` path writes
  the blackboard into the session log of its issue first, used by `along wrap`,
  `along scratch purge` and `along issue done`. `--force` purges still record, with the reason.
- REQ-4: `along issue done` on an issue that has a blackboard records it (session log entry with
  `issues_completed`) instead of leaving it orphaned.
- REQ-5: Wrap refuses to purge when the plan was never recorded (scaffold only) unless
  `--force --reason`; scaffold placeholders are not rendered as content.
- REQ-6: wrap-before-stop checks that every issue completed today is listed in `issues_completed`
  of a session log of the day.
- REQ-7: The Blackboard Record section of a committed session log is append-only: a git/CI check
  rejects a change that removes lines from it (the Summary stays editable).
- REQ-8: `along doctor` reports orphaned blackboards (no binding, issue closed or missing).

## Code map (verified 2026-10-05)
- Blackboard: `scripts/alongkit/session.py`: `init_session` (writes the scaffold `plan.md` with
  `Step N: Step N` and an empty `research.md`; `execution_mode="direct"` by default),
  `update_state`, `append_trace` (`execution_trace.md`), `render_blackboard_markdown` (what wrap
  writes as "Blackboard Record"), `purge_session` (`unbind_slug` + `shutil.rmtree`, no copy),
  `completion_problems` (role-based only).
- Approval: `session.record_plan_approval` (called from `hooks/predicates.py::record_tool_activity`
  on Claude Code `PostToolUse` of `ExitPlanMode`; the plan text is in the hook payload's tool input
  and is currently dropped), `session.approve_plan`, CLI `along plan approve` in
  `scripts/along_exec.py`.
- Wrap: `scripts/alongkit/lifecycle.py::execute_wrap` -> `_write_wrap_session_log` (renders the
  blackboard, only if the log has no "## Blackboard Record" yet) -> `session.purge_session`.
- Purge CLI: `scripts/along_exec.py` `handle_scratch_command` `purge` (checks
  `completion_problems` only, which is empty for direct blackboards).
- `along issue done`: `scripts/along_exec.py::_issue_done` (no blackboard handling).
- wrap-before-stop: `hooks/predicates.py::check_wrap_before_stop` (any session log of the day).
- Repo checks for REQ-7: `scripts/alongkit/repochecks.py` + `default_gates.yaml` (git/ci gates).

## Incident record (2026-10-05)
- Five blackboards (`containment-root-from-shell-cwd`, `entity-gate-blocks-preexisting-problems`,
  `migration-dangling-template-milestones`, `unconfigured-test-hook-reports-pass`,
  `wrap-zero-byte-audit-unscoped`) were purged with `along scratch purge` without inspection;
  their issues had been closed with `along issue done` under one wrap of another slug. Content
  unrecoverable; most likely scaffold only (direct mode, nothing was written to them).
- Generated session logs were rewritten by hand and their Blackboard Record tables dropped
  (`bootstrap-guard-leaks-to-children`, `hook-activation-and-gate-deadlock`, and the log of the
  entity-graph session), which REQ-7 would have rejected.
- Plans were approved in chat only; none reached a `plan.md` until the last two tasks of the day,
  where the plan was written to the blackboard by hand and wrap recorded it correctly
  (`2026-10-05--along-update-dev-repo.md` shows the expected result).

## Implementation plan
Order: after `bug--commit-blocked-after-wrap`, before `feat--parallel-session-closeout` (which
needs `archive_and_purge` and the trace). Execution mode: Role-Based (`along-team`).
1. REQ-1 plan capture: `along plan approve --plan-file <path>` copies the text into `plan.md`
   (keep revisions: append `## Revision N (<ts>)` instead of overwriting); refuse while `plan.md` is
   the scaffold and no `--plan-file`; `record_tool_activity` stores `tool_input.plan` from
   `ExitPlanMode`. Helper `session.is_scaffold_plan(text)`.
2. REQ-2 direct-mode trace: hooks append to `execution_trace.md` of the bound slug: edits
   (PostToolUse), test runs with result, gate denials, approval, phase changes. Bounded size.
3. REQ-3 `session.archive_and_purge(repo_root, slug, reason=None)`: render blackboard into the
   session log of that issue (create the log if missing, same format as wrap), then purge. Used by
   `execute_wrap`, `scratch purge` (with `--force --reason` still recording), `_issue_done`.
4. REQ-4 `_issue_done` calls `archive_and_purge` when a blackboard exists and adds the key to
   `issues_completed` of the day's log.
5. REQ-5 wrap: refuse purge on scaffold-only plan unless `--force --reason`;
   `render_blackboard_markdown` skips scaffold placeholders.
6. REQ-6 stricter `check_wrap_before_stop`.
7. REQ-7 repo check `check_session_log_record_append_only` (diff of `SESSIONS/**` against HEAD:
   no removed lines under `## Blackboard Record`), wired in `default_gates.yaml` as a git/ci gate.
8. REQ-8 doctor: orphan blackboards.
9. Tests per REQ (hermetic fixtures), docs: `docs/topic--session-lifecycle.md` (new, guide) or the
   existing workflow article, `docs/topic--cli-reference.md`.

## Acceptance Criteria
- [x] Hermetic tests for REQ-1..REQ-8, positive and negative.
- [x] Docs: session/blackboard lifecycle in `docs/topic--*.md`, CLI reference for `plan approve`, `scratch purge`, `issue done`, `wrap`.
- [x] Automated tests passing

## Resolution (2026-10-06)
- REQ-1: `session.record_plan` / `is_scaffold_plan` / `record_accepted_plan`; `along plan approve
  --plan-file`, refused (also `scratch approve`) while `plan.md` is the scaffold; ExitPlanMode
  stores `tool_input.plan` (or `pending_plan` until the first `along start`).
- REQ-2: `session.trace_event` / `trace_test_run`, bounded `append_trace` (400 entries, `(xN)`):
  edits (PostToolUse), gate denials (`engine.py`), test runs with result (`along test`,
  `gates.run_repository_tests`), plan, phase, step and retry changes. No Bash PostToolUse matcher.
- REQ-3..REQ-5: `lifecycle.write_session_record`, `archive_and_purge`, `purge_archived`; wrap,
  `scratch purge` and `issue done` archive first; purge after the transaction commit; scaffold
  refusal with `--force-reason`; same-day second record kept.
- REQ-6: `check_wrap_before_stop` per issue completed today (local date).
- REQ-7: `gitgates.check_session_records`, gate `session_record_append_only` (git, ci, `along commit`).
- REQ-8: `lifecycle.orphan_blackboards` in `along doctor`.
- Docs: new `docs/topic--session-lifecycle.md`; CLI reference, runtime hooks and gates (2.8, 2.9,
  gate table), architecture section 8; `along-team` skill.
