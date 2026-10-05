---
protocol: along
protocol_version: "4.4.5"
slug: stop-gates-breaker-deadlock
type: bug
status: open
priority: high
created: 2026-10-05
updated: 2026-10-05
agent: claude-code
tags: [hooks, gates, circuit-breaker]
milestone: v4.5.0-multi-user-merge-automation
blocked_by: []
related: []
---

# Stop gates demand commands the tripped circuit breaker forbids (turn deadlock)

On 2026-10-05 `.git/index` got corrupted (`fatal: .git/index: bad signature`) while two test
runs (`along test` and the quality gate of `along bump`) and a parallel session worked on the
same clone. The circuit breaker tripped and held every shell command. At the same time the
Stop gate `projection-sync-before-stop` rejected every turn end, demanding `along issue sync`,
which the breaker held. The agent could not end a turn cleanly until the user repaired the
index by hand (`mv .git/index ...; git reset; along circuit reset`).

## Facts
- `check_projection_sync_before_stop` (`alongkit/hooks/predicates.py`) compares mtimes of all
  issue files with `.along/ISSUES.md`; edits by another session trigger it too (see
  [feat--parallel-session-closeout]).
- `check_circuit_breaker` holds write tools and all shell tools, including `along` state and
  sync commands.

## Acceptance Criteria
- [ ] While the breaker is tripped, Stop gates that demand a command do not reject the turn
      (they report the pending step instead)
- [ ] Breaker message names the repair steps for its class (VCS corruption: index rebuild)
- [ ] Automated tests passing
