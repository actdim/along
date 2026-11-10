---
protocol: along
protocol_version: "4.6.1"
slug: early-raw-runner-warning
type: feat
status: open
priority: low
created: 2026-11-08
updated: 2026-11-08
agent: claude-code
tags: [gates, feedback]
blocked_by: []
related: []
---

# Warn about a raw test runner when it starts, not at Stop

## Problem

Field report (2026-11-08): a package's own `pnpm run test` (vitest) ran after the last edit. Only at Stop did `[gate: test_before_stop]` reject the turn: "A raw test runner ran after the edit, but this repository has a lifecycle test hook, and only it counts." The agent had to run the suite a second time.

## Requirements
- REQ-1: When a raw test runner command starts in a repository with a lifecycle test hook, the hooks MUST emit a non-blocking notice that it will not satisfy `test_before_stop` and name the lifecycle command.
- REQ-2: When `.along/scripts/test.py` delegates to the package's `test` script (detectable from the hook or its config), a successful run of that script after the last edit SHOULD count for `test_before_stop`.

## Acceptance Criteria
- [ ] Running `pnpm run test` in a repo with `.along/scripts/test.py` prints the notice at PreToolUse.
- [ ] Decision on REQ-2 recorded (implemented, or rejected with the reason in this issue).
- [ ] Automated tests passing
