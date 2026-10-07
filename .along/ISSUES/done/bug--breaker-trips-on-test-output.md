---
protocol: along
protocol_version: "4.4.5"
slug: breaker-trips-on-test-output
type: bug
status: done
completed: 2026-10-07
priority: high
created: 2026-10-05
updated: 2026-10-07
agent: claude-code
tags: [circuit-breaker, tests, gates]
milestone: v4.5.0-multi-user-merge-automation
blocked_by: []
related: [bug--stop-gates-breaker-deadlock]
---

# Circuit breaker trips on VCS signatures printed by a failing test run

The breaker tripped on the live repository with `fatal: .git/index: bad signature` on
2026-09-29 and again on 2026-10-05, while the real `.git/index` was healthy. The first
hypothesis (concurrent test runs and git commands corrupt the index) was wrong.

## Facts
- `circuit.trip_breaker()` prints the escalation report to stderr. The circuit breaker
  tests trip fixtures with the signature `fatal: .git/index: bad signature`, so the text
  appears in the output of every suite run.
- `gates.run_repository_tests()` (quality gate of `along commit`, `along bump`, `along wrap`,
  `along session close`) ran the suite through `proc.run_capture()` with the default
  `trip_on_anomaly=True`. When the suite failed, `classify_anomaly()` scanned the whole output,
  matched the substring `bad signature` and tripped the breaker of the live repository.
- It surfaces only when the suite fails inside a quality gate: `along test` already passes
  `trip_on_anomaly=False` (`lifecycle.run_lifecycle_command`). On 2026-10-05 the suite failed
  because a parallel session was fixing the Windows short path tests.
- The 2026-09-29 trip is in `circuit_breaker.json` history with unittest output as `detail`.
  The 2026-10-05 record was lost: `reset_breaker` cleared the anomaly without archiving it.
- The health probe checked only the index size, not that git can read it.

## Requirements
- REQ-1: Output-based VCS (Class 1) classification applies only to output of `git` itself;
  test and tool output is data.
- REQ-2: Class 1 patterns match git's own message lines (`fatal:` / `error:` at line start),
  not a substring anywhere.
- REQ-3: Quality gates (`run_repository_tests`, `syntax_gate`) never trip the breaker.
- REQ-4: Before a Class 1 trip, an independent probe (`git status`) must reproduce the
  failure; a healthy probe records a warning instead of tripping.
- REQ-5: The health probe runs `git status`; `reset_breaker` archives the cleared anomaly
  in history.

## Acceptance Criteria
- [x] A failing suite whose output contains `bad signature` does not trip the breaker
- [x] A git command failing with a real index corruption still trips it
- [x] Reset keeps the cleared anomaly in history
- [x] Automated tests passing
