---
protocol: along
protocol_version: "4.2.0"
slug: py310-fstring-syntax-error
type: bug
status: open
priority: high
created: 2026-09-27
updated: 2026-09-27
agent: cowork
tags: [python, compat, cli]
milestone: v4.3.0-developer-experience-and-runtime-resilience
blocked_by: []
related: [task--ci-test-matrix-workflow, debt--along-exec-argparse-migration]
---

# along_exec.py fails to compile on Python 3.10 and 3.11

## Problem

`pyproject.toml` declares `requires-python = ">=3.10"`, but `scripts/along_exec.py` uses a backslash inside an f-string expression, which is legal only from Python 3.12 (PEP 701). On 3.10 and 3.11 the canonical `along` CLI does not start at all, and the Pre-Flight Syntax Gate in `.along/scripts/test.py` aborts the whole test suite before discovery.

## Evidence

```text
File "scripts/along_exec.py", line 822
  decisions_str = f"[{', '.join([f'\"{d}\"' for d in decisions])}]" if decisions else "[]"
SyntaxError: f-string expression part cannot include a backslash
```

Reproduced on Python 3.10.12: `python3 -m py_compile scripts/along_exec.py` fails; every other tracked `.py` file compiles.

## Requirements

- REQ-1: `along_exec.py` compiles and runs on Python 3.10, 3.11, 3.12 and 3.13.
- REQ-2: No other PEP 701-only constructs remain in `scripts/`, `tests/`, `dashboard/` or `.along/scripts/`.
- REQ-3: A regression guard exists: CI runs the minimum declared Python version (see `task--ci-test-matrix-workflow`), or a test compiles all sources with a 3.10 grammar check.

## Acceptance Criteria

- [ ] `python3.10 -m compileall -q scripts tests dashboard .along/scripts` exits 0
- [ ] `python3.10 .along/scripts/test.py` reaches test discovery
- [ ] Automated tests passing
