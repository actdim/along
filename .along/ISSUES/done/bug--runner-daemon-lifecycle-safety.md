---
protocol: along
protocol_version: "4.5.3"
slug: runner-daemon-lifecycle-safety
type: bug
status: done
completed: 2026-10-24
priority: high
created: 2026-10-23
updated: 2026-10-24
agent: claude-code
tags: [daemon, autonomous, telegram, reliability]
blocked_by: []
related: [feat--vps-runner-daemon, bug--orchestrator-review-fail-open]
plan_status: approved
---

# Runner daemon loses work, replays tasks and can kill foreign processes

## Problem

Review of commit e4e91ee (`feat--vps-runner-daemon`), `scripts/alongkit/daemon.py`.

- Worktree mode deletes the result: `handle_task_command` calls
  `worktree.remove_worktree(..., force=True)` in `finally`, whose default `delete_branch=True`
  removes the `along/<slug>` branch; nothing pushes or merges it first.
- The `getUpdates` offset lives only in memory (`last_update_id`). A task runs synchronously
  inside the poll loop, so a kill mid-run, or an exception outside the caught list, replays the
  same `/task` on restart; with `Restart=always` that becomes a crash loop. `message.date` is not
  checked, so commands queued while the daemon was down run later without notice.
- `stop` / `is_pid_alive` only check that the PID exists: after a crash the stale PID file can
  point at a reused PID, and `along daemon stop` SIGTERMs then SIGKILLs a foreign process; a
  foreground start refuses to run ("already running"). The PID file is written without an
  exclusive create, so two starts race.
- The busy check (`current_task`) is dead code because updates are handled one at a time;
  `/status` gets no reply during a run; SIGTERM only sets a flag and the task runs to the end
  until systemd SIGKILLs it.
- Errors (401, 409) are retried every `poll_interval` forever with no backoff; `daemon.log` has
  no size limit.
- Background start prefers `<repo_root>/scripts/along_daemon.py` over the installed tool, and
  returns 0 when the spawn fails.

## Requirements
- REQ-1: Worktree teardown MUST keep the work branch (or push it) and report its name; it MUST NOT delete commits the run produced.
- REQ-2: The daemon MUST persist the acknowledged `getUpdates` offset before starting a task, so a restart never re-runs an update it already accepted.
- REQ-3: The daemon MUST ignore commands older than a configured age (default 10 minutes) and say so to the sender.
- REQ-4: `stop` MUST verify the PID belongs to an along daemon (recorded start time or command line) before signalling it; a stale PID file MUST be removed, not obeyed.
- REQ-5: The PID file MUST be created exclusively.
- REQ-6: Tasks MUST run off the poll loop (worker thread or subprocess) so `/status`, the busy check and SIGTERM handling work during a run.
- REQ-7: Polling errors MUST back off exponentially (capped); 401 MUST stop the daemon with a clear log line.
- REQ-8: Background start MUST run the installed along entry point, and MUST exit non-zero when the spawn fails.

## Acceptance Criteria
- [x] Worktree run: after teardown the `along/<slug>` branch still exists with the run's commits.
- [x] Simulated crash after accepting an update: on restart the update is not processed again.
- [x] A stale PID file pointing at an unrelated live process: `stop` does not signal it.
- [x] `/status` answers while a task is running.
- [x] Regression tests cover each criterion and fail on the old code; `python .along/scripts/test.py` is green.
