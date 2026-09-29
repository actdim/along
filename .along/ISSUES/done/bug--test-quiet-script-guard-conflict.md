---
protocol: along
protocol_version: "4.2.0"
slug: test-quiet-script-guard-conflict
type: bug
status: done
completed: 2026-09-27
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

- [x] `pnpm run test:quiet` / `npm run test:quiet` runs the suite
- [x] Allowlist and guard agree
- [x] Automated tests passing

## Resolution

- REQ-1: `.along/scripts/test.py` accepts `-q` / `--quiet` (unittest verbosity 1); `package.json` `test:quiet` is now `python .along/scripts/test.py -q`.
- REQ-2: decision documented in `docs/topic--setup-and-workflow.md`: the runner is the only supported entry point for this repository's suite, so the guard in `tests/__init__.py` stays. The generic test-runner patterns in the `require-plan-approval` allowlist stay too, because they describe consumer repositories (pytest, npm test, ...), not this one. The two stale `uv run python -m unittest discover tests -q` instructions in that article now point at the runner.
- REQ-3: the guard message already names `python .along/scripts/test.py`; the runner docstring explains why.
- Verified: `.along/scripts/test.py -q` on Python 3.12, 666 tests OK (3 skipped), dot output.
