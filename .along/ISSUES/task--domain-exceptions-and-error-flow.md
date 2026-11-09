---
protocol: along
protocol_version: "4.7.0"
slug: domain-exceptions-and-error-flow
type: task
status: in-progress
priority: medium
created: 2026-11-07
updated: 2026-11-09
agent: antigravity
tags: [architecture, error-handling, exceptions, cli, refactoring]
blocked_by: []
related: [task--refactor-cli-chdir-common]
plan_status: approved
---

# Central Domain Exception Hierarchy and Structured Error Flow Control

Establish a domain exception hierarchy in `scripts/alongkit/exceptions.py`, make `along_exec.cli_entry()` the single place where domain errors become exit codes and stderr text, and migrate `sys.exit()` calls out of `scripts/alongkit/commands/` module by module with byte-compatible output. Triage of silent `except ...: pass` blocks is split into a follow-up issue.

## Context and Problem Statement

Measured 2026-11-08 (see [plan.md](./task--domain-exceptions-and-error-flow/plan.md)):
- 358 `sys.exit(` calls in `scripts/`; about 273 are inside `scripts/alongkit/commands/` (lifecycle 52, issue 49, env 34, ops 32, scratch 31, worktree 15, gates 15, session 13, milestone 12, decision 8, telemetry 7, doctor 5). The remainder are engine `main()` exits and stay.
- 195 `except ...: pass` blocks in `scripts/`.
- 11 test files assert `SystemExit` from command handlers.

Command helpers print and call `sys.exit()` deep in the call stack, so callers cannot compose, recover or roll back, and tests must catch `SystemExit`.

`scripts/alongkit/cli.py` runs `along_exec.py` via `runpy.run_path(..., run_name="__main__")`, so `along_exec.cli_entry()` is already the process boundary; `cli.py` needs no exception handling. It may also load a different `alongkit` copy than the router, which would make a `CommandError` catch there unreliable.

## Requirements

- REQ-1 (Hierarchy): `scripts/alongkit/exceptions.py` defines `AlongError(Exception)`; `CommandError(AlongError)` with `message`, `exit_code=1` and optional `usage`; `ValidationError(CommandError)` with `exit_code=2`. Re-exported from `scripts/alongkit/__init__.py`. Existing exceptions (`ProcessError`, `FrontmatterError`, `EnvConfigError`, `MissingDependency`) are not re-parented in this issue.
- REQ-2 (Single Boundary): `along_exec.cli_entry()` catches `CommandError`, prints `[Error] <message>` and, when set, `Usage: <usage>` to stderr, and exits with `exc.exit_code`; `ALONG_DEBUG` re-raises. Exception messages carry no `[Error]` prefix. `scripts/alongkit/cli.py` is not changed.
- REQ-3 (Migration): `commands/common.py` first, then each command module in its own commit (lifecycle, issue, env, ops, scratch, worktree, gates, session, milestone, decision, telemetry, doctor), replacing `print(...); sys.exit(n)` with `CommandError` / `ValidationError`.
- REQ-4 (Output Contract): For every migrated error path, stderr text and exit code are byte-compatible with the pre-migration behavior, enforced by golden tests that run `along_exec.py` as a subprocess. Exit codes: 0 success, 1 operational, 2 usage/validation, 130 SIGINT.
- REQ-5 (Tests): `tests/test_domain_exceptions.py` covers the hierarchy, default exit codes, boundary formatting, `ALONG_DEBUG`, and a structural check that fails on a new `sys.exit(` in `scripts/alongkit/commands/` (with an allow-list). Tests that call handlers directly assert the domain exception.
- REQ-6 (Follow-up issue): Silent `except ...: pass` triage (classify all 195 sites; record corruption of Along-owned state via `DiagnosticsStore.record_incident`, deduped per component/path/mtime; hooks stay fail-open; tests use the isolated home) is filed as its own issue and is out of scope here.
- REQ-7 (ASCII Typography Compliance): `scripts/sanitize_typography.py --check` passes.

## Acceptance Criteria

- [x] `scripts/alongkit/exceptions.py` defines the three classes; `scripts/alongkit/__init__.py` re-exports them.
- [x] `along_exec.cli_entry()` handles `CommandError` / `ValidationError` as specified; `cli.py` unchanged.
- [x] `require_entity_name` and `check_unknown_args` raise `ValidationError`.
- [x] All 12 command modules migrated, one commit each, with golden stderr/exit-code tests.
- [x] Structural test blocks new `sys.exit(` in `scripts/alongkit/commands/`.
- [x] `tests/test_domain_exceptions.py` and the full suite pass.
- [x] Follow-up issue for `except ...: pass` triage filed.
- [ ] Repository passes `python scripts/sanitize_typography.py --check`.
