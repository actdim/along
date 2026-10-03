---
protocol: along
protocol_version: "4.4.2"
slug: test-gate-lifecycle-hook-only
type: feat
status: done
completed: 2026-10-01
priority: medium
created: 2026-10-01
updated: 2026-10-01
agent: claude-code
tags: [gates, tests]
milestone: v4.5.0-multi-user-merge-automation
blocked_by: []
related: [bug--activity-trace-shared-across-sessions]
---

# test_before_stop credits lifecycle test hook over raw runners

## Problem
`TEST_COMMAND_PATTERNS` credits `pytest`, `npm test`, `cargo test`, `dotnet test`, so raw runners
satisfy `test_before_stop` even where `.along/scripts/test.py` exists, and `npx vitest`, `tsc` or
`vitest run` are not recognized at all. The protocol says lifecycle hooks come first.

## Requirements
- REQ-1: When `.along/scripts/test.py` exists, only `along test`, `/along-test` or that script
  satisfy the gate; raw runners leave a warning in the Stop message.
- REQ-2: Without a lifecycle hook, raw runners (including `vitest`, `jest`, `go test`) count.

## Acceptance Criteria
- [x] Raw pytest does not satisfy the gate when the hook exists
- [x] Automated tests passing
