---
protocol: along
protocol_version: 2.2.8
slug: subprocess-encoding-breaks-on-non-utf8-locale
type: bug
status: open
priority: critical
created: 2026-09-01
updated: 2026-09-01
agent: claude-code
tags: [encoding, windows, tests, subprocess, cross-platform]
milestone: v3.0.0-global-quality-revision
blocked_by: []
related: []
parent: protocol-quality-audit-remediation
---

# Test suite and engines crash on Windows with a non-UTF8 system locale

## Problem

No `subprocess.run(...)` call in the repository passes `encoding=` or `errors=`. With
`text=True`, Python decodes child output using `locale.getpreferredencoding()`, which on a
Russian Windows install is `cp1251`, on Chinese `cp936`, and so on. Any non-ASCII byte in
child output raises `UnicodeDecodeError` inside the stdout reader thread. The exception is
raised in a thread, so `subprocess.run` returns with `stdout = None` instead of failing
cleanly, and the caller then crashes on a confusing secondary error.

Reproduced on this machine (Windows 11, Python 3.12.10, cp1251 locale):

```text
Exception in thread Thread-11 (_readerthread):
  File "...\encodings\cp1251.py", line 23, in decode
UnicodeDecodeError: 'charmap' codec can't decode byte 0x98 in position 455

ERROR: test_06_along_dash_cli_execution
  File "tests\test_skills_and_scripts.py", line 181, in test_06_along_dash_cli_execution
    self.assertIn("Along Executive Dashboard", res.stdout)
TypeError: argument of type 'NoneType' is not iterable
```

Affected call sites (all `subprocess.run` with `text=True` and no explicit encoding):

- `tests/test_skills_and_scripts.py`: lines 174, 178, 192, 201, 237, 248, 254, 259, 322, 371, 423, 485, 529
- `scripts/along_commit.py`: lines 30, 55, 145, 162
- `scripts/along_version_bump.py`: lines 195, 387
- `scripts/along_kb_sync.py` (via `migrate_protocol.py`): `migrate_protocol.py` lines 618, 744
- `scripts/along_dep_scan.py`: line 709
- `scripts/along_history_sync.py`: line 46
- `scripts/along_update.py`: line 109

## Impact

- The published test suite fails out of the box for any developer on a non-UTF8 Windows
  locale, in a project whose central selling points include "Windows-safe" behavior and
  "PowerShell escaping resilience".
- Worse than a crash: engines that parse child output (`along_commit` reading git output,
  `along_history_sync` reading `git log`, `along_dep_scan` reading a subproject scanner)
  can silently receive `None` and take the wrong branch, because most of these calls are
  wrapped in `except Exception: pass`.
- `test_06` masks its own root cause: the reported failure is a `TypeError` on `None`,
  which looks like a dashboard bug rather than an encoding bug.

## Secondary defect in the same test

`tests/test_skills_and_scripts.py:177` has a typo in the uv fallback:

```python
cmd = ["uv", "run", "--with", "fastapi", ..., "--with", "httpx2", ...]
```

`httpx2` is not a real package; the intended dependency is `httpx`. The fallback path
therefore fails if it is ever taken. It also invokes `uv` unconditionally, raising
`FileNotFoundError` rather than skipping when `uv` is absent.

## Requirements

- REQ-1: Every `subprocess.run` / `Popen` that captures text output must pass
  `encoding="utf-8", errors="replace"` (or `text=False` plus explicit decoding).
- REQ-2: Child processes must be told to emit UTF-8: set `PYTHONIOENCODING=utf-8` in the
  environment passed to child Python interpreters.
- REQ-3: Callers must not assume `stdout` is a string. Where output is parsed, guard for
  `None` and empty output with an explicit error, not a silent branch.
- REQ-4: Fix the `httpx2` typo and make the `uv` fallback conditional on `shutil.which("uv")`.
- REQ-5: A regression test must assert that a child process emitting non-ASCII output is
  decoded without raising, independently of the host locale.
- REQ-6: Add a single shared helper (for example `run_capture()`) in the shared library
  extracted by `[debt--extract-shared-python-library]` so this cannot regress per file.

## Acceptance Criteria

- [ ] `python -m unittest discover tests -q` passes on a cp1251 (or other non-UTF8) locale.
- [ ] Grep shows zero `subprocess.run` with `text=True` and no `encoding=`.
- [ ] `test_06` failure mode, if any, reports the real cause rather than a `NoneType` error.
- [ ] Regression test covers non-ASCII child output.
