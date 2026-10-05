---
protocol: along
protocol_version: "4.4.5"
slug: unconfigured-test-hook-reports-pass
type: bug
status: done
completed: 2026-10-05
priority: medium
created: 2026-10-05
updated: 2026-10-05
agent: claude-code
tags: [lifecycle, gates]
blocked_by: []
related: []
---

# Unconfigured lifecycle test hook looks like a passing test run

## Problem
When no test command is detected, Along synthesizes `.along/scripts/test.py` from
`UNCONFIGURED_HOOK_TEMPLATE`, which prints a notice and exits 0. The wrap and commit
quality gates (`gates.run_repository_tests`) then print "All tests passed successfully",
and `along test` only prints a `[Notice]`. A repository without configured tests looks
verified.

## Requirements
- REQ-1: The unconfigured template prints a `[Warning]` on stderr saying the action is not
  configured and nothing was verified (exit code stays 0, so it never blocks).
- REQ-2: `gates.run_repository_tests` recognizes an unconfigured hook (`# Status:
  unconfigured`) and reports "tests are not configured" as a warning instead of a pass.
- REQ-3: `along test` / `along build` print the unconfigured state as `[Warning]`.
- REQ-4: Tests for the rendered template output and the gate message.

## Acceptance Criteria
- [x] REQ-1..REQ-3 implemented
- [x] REQ-4 tests pass
- [x] Automated tests passing
