---
protocol: along
protocol_version: "4.4.5"
slug: session-records-not-captured
type: bug
status: open
priority: high
created: 2026-10-05
updated: 2026-10-05
agent: claude-code
tags: [session, blackboard, wrap, gates]
blocked_by: []
related: [bug--diagnostics-files-stay-tracked]
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

## Acceptance Criteria
- [ ] Hermetic tests for REQ-1..REQ-8, positive and negative.
- [ ] Docs: session/blackboard lifecycle in `docs/topic--*.md`, CLI reference for `plan approve`, `scratch purge`, `issue done`, `wrap`.
- [ ] Automated tests passing
