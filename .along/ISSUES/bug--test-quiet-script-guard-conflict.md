---
protocol: along
protocol_version: "4.2.0"
slug: test-quiet-script-guard-conflict
type: bug
status: open
priority: low
created: 2026-09-27
updated: 2026-09-27
agent: cowork
tags: [tests, dx]
milestone: v4.3.0-developer-experience-and-runtime-resilience
blocked_by: []
related: [bug--safe-command-prefix-bypass]
---

# package.json test:quiet is refused by the test runner guard

## Problem

`tests/__init__.py` and `tests/hermetic.py` abort with `[Error] Tests must not be run directly or via standard test commands (unittest/pytest).` unless `ALONG_TEST_RUNNER=1` is set by `.along/scripts/test.py`. At the same time:

- `package.json` script `test:quiet` is `python -m unittest discover tests -q`, which always fails with 17 import errors;
- `SAFE_READ_COMMAND_PATTERNS` whitelists `python -m unittest` and `unittest discover` as test invocations.

Three places disagree on what the supported test entry point is.

## Requirements

- REQ-1: `test:quiet` calls the canonical runner with a quiet flag (add `-q` / `--quiet` support to `.along/scripts/test.py`, verbosity 1).
- REQ-2: Decide and document (ADR or `docs/topic--setup-and-workflow.md`) whether raw `unittest`/`pytest` are supported. If not, remove them from the safe-command allowlist; if yes, drop the guard and set up the environment in `tests/__init__.py`.
- REQ-3: The guard error message names the exact command to run.

## Acceptance Criteria

- [ ] `pnpm run test:quiet` / `npm run test:quiet` runs the suite
- [ ] Allowlist and guard agree
- [ ] Automated tests passing
