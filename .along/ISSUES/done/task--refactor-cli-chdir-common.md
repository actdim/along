---
protocol: along
protocol_version: "4.6.1"
slug: refactor-cli-chdir-common
type: task
status: done
completed: 2026-11-08
priority: medium
created: 2026-11-06
updated: 2026-11-08
agent: antigravity
tags: []
blocked_by: []
related: [task--domain-exceptions-and-error-flow]
---

# Move _handle_chdir_options into a dependency-free alongkit.cliargs module

Relocate `_handle_chdir_options` from `scripts/alongkit/cli.py` to a new standard-library-only module `scripts/alongkit/cliargs.py`, and remove the duplicate import in `scripts/along_exec.py` (lines 19 and 47 are identical).

`scripts/alongkit/commands/common.py` is NOT a valid destination: importing it executes `scripts/alongkit/commands/__init__.py`, which imports every command router (and through them `entities`, `frontmatter`, `session`, `transaction`). `cli.py` is the thin `along` launcher; it runs before `bootstrap.ensure_deps()` and must stay light. See the 2026-11-08 revision note in [plan.md](./task--refactor-cli-chdir-common/plan.md).

## Requirements
- REQ-1: `_handle_chdir_options` MUST move from `scripts/alongkit/cli.py` to `scripts/alongkit/cliargs.py`, which imports only the standard library and carries the library-module guard.
- REQ-2: `scripts/alongkit/cli.py` MUST import `_handle_chdir_options` from `cliargs` in both its script and package import branches, and MUST NOT import `alongkit.commands`.
- REQ-3: `scripts/along_exec.py` MUST import `_handle_chdir_options` once, from `alongkit.cliargs`.
- REQ-4: Behavior MUST be unchanged: attached and spaced `-C` / `--chdir`, chained `-C`, exit 2 with a stderr message on a missing argument.
- REQ-5: `tests/test_alongkit.py`, `tests/test_cli_chdir.py` and `tests/test_rules.py` MUST pass.

## Acceptance Criteria
- [x] `scripts/alongkit/cliargs.py` exists and imports only `os`, `sys`, `typing`.
- [x] `scripts/alongkit/cli.py` no longer defines `_handle_chdir_options` and does not load `alongkit.commands` on import (covered by a test).
- [x] `scripts/along_exec.py` has a single import of `_handle_chdir_options`, from `alongkit.cliargs`.
- [x] `along -C packages/dashboard-ui status` and `along --version` work.
- [x] Targeted tests pass; `along sanitize` is clean.
