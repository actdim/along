---
protocol: along
protocol_version: "4.4.5"
slug: hook-activation-and-gate-deadlock
type: bug
status: done
completed: 2026-10-05
priority: high
created: 2026-10-05
updated: 2026-10-05
agent: claude-code
tags: [hooks, activation, diagnostics, shellparse, inquiry]
blocked_by: []
related: []
---

# Hooks: false activation, self-created subproject roots, read-only misclassification, gate deadlock

Field report from a consumer repository (Windows, Claude Code, global hooks): the runtime hooks
activated in a repository that never adopted Along, created `.along/diagnostics/` in whatever
directory the session sat in, then treated that directory as a subproject and blocked every edit
under it. A read-only audit command was rejected, and test-before-stop demanded tests that
require-plan-approval forbade running.

Root causes found in the code:
- `along_hook.py` activates on `.along/`, `.agents/` or a bare `AGENTS.md` (a tool-agnostic convention).
- `repo.ensure_diagnostics_dir()` creates `<root>/.along/diagnostics/` for any root; `find_state_dir()`
  then counts that diagnostics-only `.along/` as a context, so `subproject_context()` reports a subproject.
- No way to declare an Along root whose state lives elsewhere (e.g. a nested personal `.local/.along/`).
- `shellparse` has no `awk`; `dotnet build` / `cargo check` / linters are not accepted as verification.
- `record_tool_activity()` records edits at PreToolUse before the gates run, so a blocked Write still
  counts as "source modified" for test-before-stop.
- Unbound sessions default to inquiry with no approval, so every mutation is blocked.

## Requirements
- REQ-1: Hooks activate only on an Along context: a `.along/` (or legacy `.agents/`) holding more than
  hook runtime output, or a declared root. A bare `AGENTS.md` does not activate. Without a context the
  hook exits before the dependency bootstrap.
- REQ-2: An Along root can be declared without a `.along/` of its own: an `<!-- along-root: <dir> -->`
  pointer in `AGENTS.md`, or `context_roots` in `~/.along/config.json`. State resolves to `<dir>/.along/`,
  gates keep evaluating paths against the workspace.
- REQ-3: Diagnostics go to the resolved state dir when it exists, else to `~/.along/diagnostics/`;
  the hooks never create a `.along/`. A `.along/` holding only `diagnostics/` is never a subproject.
- REQ-4: `awk` without writes (`system()`, print redirection/pipes, `-i inplace`, `-f`) is read-only.
- REQ-5: Verification commands (build, test, lint, typecheck; no `--fix`/format) pass the plan gate in
  every phase.
- REQ-6: test-before-stop counts only edits that succeeded (PostToolUse) and test runs the gates
  allowed; it does not fire while the circuit breaker blocks commands.
- REQ-7: require-plan-approval and test-before-stop fail open for sessions not bound to an issue,
  unless the repository opts in with `enforce_unbound: true` in `.along/rules/gates.yaml`.
- REQ-8: Read/Grep/Glob inside the workspace are answered without the dependency bootstrap.
- REQ-9: No code, test or doc refers to a specific consumer repository.

## Acceptance Criteria
- [x] Hermetic tests for REQ-1..REQ-8, positive and negative (`tests/test_hook_activation.py`)
- [x] Automated tests passing (953 tests, OK)

## Notes
- This repository opts into `enforce_unbound: true` (`.along/rules/gates.yaml`) to keep its own
  AGENTS.md contract; consumer repositories fail open for unbound sessions by default.
- `find_agent_contexts()` still lists bare `AGENTS.md` directories: init/update/kb-sync use it to find
  folders to scaffold, which is not hook activation.
- A `.along/` left behind by older hooks (only `diagnostics/`) is now ignored; it can be deleted by hand.
