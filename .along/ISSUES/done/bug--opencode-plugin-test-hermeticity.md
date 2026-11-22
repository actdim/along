---
protocol: along
protocol_version: "4.9.1"
slug: opencode-plugin-test-hermeticity
type: bug
status: done
completed: 2026-11-22
priority: high
created: 2026-11-22
updated: 2026-11-22
agent: antigravity
tags: [opencode, tests, hermeticity, gates]
milestone: v5.0.0-agent-run-protocol-and-observability
blocked_by: []
related: [feat--session-hierarchy-and-submodule-automation]
plan_status: approved
---

# Fix OpenCode Node plugin contract test hermeticity on dirty working tree

## Problem
In `tests/test_opencode_runtime.py`, `TestOpenCodeNodePluginContract.test_node_plugin_module_contract` passes `location: { directory: process.cwd() }` to the OpenCode mock context.
When `session.idle` or `session.stop` is invoked for dummy `sessionID: 'ses-1'`, `handleStop` evaluates the along hook against `process.cwd()`.
If the developer or agent has any uncommitted modified files in the repository working tree, the hook denies `ses-1` with `PLAN_REQUIRED` / uncommitted files attributed to other sessions, causing `test_node_plugin_module_contract` to throw and fail.
Because `along commit` and `along wrap` run the automated test suite before committing changes, this creates a deadlock where no working tree with modifications can pass pre-commit tests cleanly.

## Requirements
- REQ-1: Test Hermeticity: `test_node_plugin_module_contract` MUST pass an isolated temporary directory (e.g. `os.tmpdir()`) in `mockCtx.location.directory` and `event.cwd` rather than `process.cwd()`.
- REQ-2: Defensive Failure Handling: The test must assert that `opencode_plugin.js` lifecycle hooks handle non-Along directories gracefully without throwing errors.

## Acceptance Criteria
- [x] `test_node_plugin_module_contract` passes cleanly regardless of whether the git working tree is clean or dirty
- [x] Automated tests in `tests/test_opencode_runtime.py` pass without evaluating gates against `process.cwd()`
