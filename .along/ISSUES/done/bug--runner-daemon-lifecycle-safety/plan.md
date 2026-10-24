# Living Plan: runner-daemon-lifecycle-safety

## Revision 1 (2026-10-24T19:40:39Z, ExitPlanMode)

# Fix: runner daemon loses work, replays tasks, can kill foreign processes (`bug--runner-daemon-lifecycle-safety`)

Execution Mode: Direct (one module `scripts/alongkit/daemon.py`, its unit file and tests; no core engine refactor)

## Context
The review of e4e91ee found the VPS runner daemon unsafe to deploy: worktree runs delete the
branch with the agent's commits, a restart replays an accepted `/task` (crash loop under
`Restart=always`), `stop` can signal a reused PID, and tasks block the poll loop so `/status`
and SIGTERM do nothing during a run. The issue lists REQ-1..REQ-8; this plan implements all of
them. The orchestrator side (fail-closed reviews, claims) is already fixed in
`bug--orchestrator-review-fail-open`.

## Changes - `scripts/alongkit/daemon.py`

1. **Keep the work (REQ-1).** Teardown in the task worker:
   - check `proc.git(["status", "--porcelain"], cwd=wt.path)`; a dirty worktree is **kept**
     (not removed) and the message names its path;
   - otherwise `worktree.remove_worktree(..., force=True, delete_branch=False)`;
   - the completion message always names the branch (`along/<slug>`) holding the run's commits.
2. **Persisted offset (REQ-2).** `telegram_offset` lives in `daemon.json`. `RunnerDaemon.__init__`
   loads it into `last_update_id`. In the poll loop each update's id is saved (`save_daemon_state`)
   **before** `process_update`, so a crash or kill mid-task never re-runs it after restart.
3. **Stale commands (REQ-3).** `max_command_age` (default 600 s; `daemon.max_command_age` in
   `.along/config.json`, env `ALONG_DAEMON_MAX_COMMAND_AGE`). An authorized message whose `date`
   is older is not executed; the sender gets "Ignored /task x sent at <time> (older than N s);
   send it again if you still want it."
4. **PID identity (REQ-4, REQ-5).**
   - `process_identity(pid) -> Optional[str]`: an opaque start-time token. Linux:
     `/proc/<pid>/stat` field 22; Windows: `GetProcessTimes` creation time via ctypes (as
     `is_pid_alive` already uses kernel32); other POSIX: `ps -o lstart= -p <pid>`.
   - The PID file holds `pid` on line 1 and the token on line 2. `read_pid` keeps returning the
     pid; new `read_pid_record` returns `(pid, token)`.
   - `acquire_pid_file(repo_root) -> bool` creates it with `O_CREAT|O_EXCL`; if it exists and the
     recorded process is alive **and** its token matches, return False; otherwise it is stale:
     remove and retry once. `RunnerDaemon.run()` uses it and exits 1 with a clear message when
     another daemon holds it (replaces the racy status check in `start_daemon --foreground`).
   - `get_daemon_status` reports `running` only when alive **and** the token matches; a missing
     or different token is `stale-pid`. `stop_daemon` therefore never signals an unverified PID:
     it removes the stale file and says so (an old-format PID file without a token is treated as
     unverified and is not signalled; the message tells the operator to stop it by hand).
5. **Tasks off the poll loop (REQ-6).** Split `handle_task_command` into validation +
   dispatch and `_execute_task(chat_id, slug, run_id)` (the current body). A `threading.Lock`
   guards `current_task`; the busy check takes it, sets `current_task`, then either starts a
   daemon `threading.Thread` running `_execute_task` (inside `run()`) or calls it inline (direct
   calls in tests and scripts keep today's synchronous behavior). `/status` and further
   commands are answered while a task runs; a second `/task` gets "Runner busy". On
   SIGTERM/SIGINT the loop stops polling at once, tells the chat the task was interrupted, and
   joins the worker for up to `stop_grace_seconds` (default 20 s, below systemd's 30 s) before
   exiting; the orchestrator's claim then expires by TTL if the worker did not finish.
6. **Backoff and auth failure (REQ-7).** `TelegramClient.get_updates` maps `HTTPError` 401/404 to
   new `TelegramAuthError`; `run()` logs it as ERROR and returns `EXIT_CONFIG = 78`. Other poll
   errors sleep `min(poll_interval * 2**n, 300)`, `n` reset on success; 409 logs a hint (another
   poller or a webhook). `append_daemon_log` rotates `daemon.log` to `daemon.log.1` above 5 MB.
7. **Background start (REQ-8).** `start_daemon` spawns the `along_daemon.py` that sits next to the
   running `alongkit` package (`os.path.dirname(os.path.dirname(__file__))`), never
   `<repo_root>/scripts/`. If no PID registers within 5 s and the child has exited
   (`p.poll() is not None`), print its exit code and return 1; if it is still starting, say so and
   return 0.

## Other files
- `docker/along-runner.service`: `RestartPreventExitStatus=78`, plus `NoNewPrivileges=true`,
  `PrivateTmp=true`, `ProtectSystem=full`.
- `docs/topic--autonomous-environment.md` (daemon section, if present): offset persistence, stale
  command window, PID identity, exit 78.

## Tests - `tests/test_daemon.py` (each checked to fail on the old code)
- Worktree run (mocked `create_worktree` / `remove_worktree` / `proc.git`): clean worktree ->
  `remove_worktree` called with `delete_branch=False` and the reply names `along/<slug>`; dirty
  worktree -> not removed, reply names the path.
- Offset: `run()` with a mock client and one `/task` update -> `daemon.json` holds the offset; a
  new `RunnerDaemon` polls with `offset = id + 1`.
- Stale command (`date` one hour old) -> orchestrator not called, reply says "Ignored".
- PID reuse: PID file with this test process's pid and no or wrong token -> `stop_daemon` does
  not call `terminate_pid`, removes the file; status is `stale-pid`.
- `acquire_pid_file` twice with a live matching token -> second returns False; stale file is taken over.
- `/status` while a task runs: orchestrator blocks on an event until the status reply is sent;
  the reply arrives before the task finishes.
- Backoff: three poll errors -> sleeps `[5, 10, 20]`; `TelegramAuthError` -> `run()` returns 78.
- Background start: fake `<repo>/scripts/along_daemon.py` is not used; a child that exits at once
  -> return code 1.
- Log rotation above the size limit.
- Update existing lifecycle tests that wrote a bare PID and patched `is_pid_alive` to also patch
  `process_identity` (they encoded the unsafe semantics).

## Verification
- `python .along/scripts/test.py test_daemon.py`, then the full suite (`-q`), green.
- Stash source changes, rerun the new tests to confirm they fail on the old code.
- Manual: `along daemon start` (background) then `status` / `stop` on Windows; stale PID file
  pointing at a live unrelated process is reported and left alone.
- `git diff --stat`, `along sanitize`; commit via `/along-commit`, `along wrap ... --no-decisions`.
