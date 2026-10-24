---
protocol: along
protocol_version: "4.5.3"
date: 2026-10-24
slug: runner-daemon-lifecycle-safety
agent: claude-code
branch: main
commit: '5985218'
summary: 'Runner daemon: worktree teardown keeps the along/<slug> branch (dirty worktrees are kept whole); the Telegram offset is persisted before each update runs; commands older than max_command_age are ignored with a reply; PID file holds a start-time identity, is created exclusively, and stop/status never act on an unverified PID; tasks run on a worker thread so /status, busy replies and SIGTERM (20 s grace) work during a run; poll errors back off exponentially, a rejected token exits 78 (RestartPreventExitStatus=78); background start uses the engine script and fails when the child exits; daemon.log rotates at 5 MB. 10 new regression tests, all failing on the old code.'
issues_advanced: []
issues_completed: [bug--runner-daemon-lifecycle-safety]
decisions: []
files: [docker/along-runner.service, docs/topic--autonomous-environment.md, scripts/alongkit/daemon.py, tests/test_daemon.py]
---

# Session: Runner daemon lifecycle safety

## Summary
Runner daemon: worktree teardown keeps the along/<slug> branch (dirty worktrees are kept whole); the Telegram offset is persisted before each update runs; commands older than max_command_age are ignored with a reply; PID file holds a start-time identity, is created exclusively, and stop/status never act on an unverified PID; tasks run on a worker thread so /status, busy replies and SIGTERM (20 s grace) work during a run; poll errors back off exponentially, a rejected token exits 78 (RestartPreventExitStatus=78); background start uses the engine script and fails when the child exits; daemon.log rotates at 5 MB. 10 new regression tests, all failing on the old code.

## Decisions
- None (confirmed at wrap: no architectural decisions).

## Blackboard Record

Execution mode: direct; plan revision 1; approved: true.

Plan: kept with the issue (`plan/plan.md`, 1 revision(s)).

### Execution Trace

#### Execution Trace: runner-daemon-lifecycle-safety
- 2026-10-24T19:40:39Z plan recorded: revision 1 (ExitPlanMode)
- 2026-10-24T19:40:39Z phase: planning -> execution
- 2026-10-24T19:40:39Z plan approved (ExitPlanMode) approved_via: exit-plan-mode, plan_sha256: 1c503253b78a
- 2026-10-24T19:43:44Z edit scripts/alongkit/daemon.py (x23)
- 2026-10-24T19:45:10Z edit tests/test_daemon.py (x6)
- 2026-10-24T19:45:54Z edit docs/topic--autonomous-environment.md
- 2026-10-24T19:46:05Z edit docker/along-runner.service
