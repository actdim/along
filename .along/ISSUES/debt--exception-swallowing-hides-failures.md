---
protocol: along
protocol_version: 2.2.8
slug: exception-swallowing-hides-failures
type: debt
status: open
priority: medium
created: 2026-09-01
updated: 2026-09-01
agent: claude-code
tags: [error-handling, diagnostics, silent-failure, observability]
milestone: v3.0.0-global-quality-revision
blocked_by: []
related: [subprocess-encoding-breaks-on-non-utf8-locale, commit-stages-all-and-dead-test-detection]
parent: protocol-quality-audit-remediation
---

# Broad exception swallowing hides engine failures from users and from diagnostics

## Problem

Across twelve engines there are roughly 70 `try` blocks and about 55 `except Exception`
handlers, a large share of them `pass` with no logging:

```text
scripts/along_dep_scan.py        15 try / 14 except Exception
scripts/along_feedback.py        10 try / 10 except Exception
scripts/along_update.py          10 try /  7 except Exception
scripts/along_kb_search.py        7 try /  7 except Exception
scripts/migrate_protocol.py       7 try /  7 except Exception
scripts/along_kb_sync.py          6 try /  6 except Exception
scripts/along_version_bump.py     6 try /  4 except Exception
```

Concrete consequences already identified elsewhere in this epic:

1. `along_commit.py:44-51` - a `NameError` from the missing `json` import is swallowed, so
   Node test detection has never worked and never reported anything
   (`[bug--commit-stages-all-and-dead-test-detection]`).
2. `along_kb_search.py` - every collector stage is wrapped in `except Exception: pass`, so a
   malformed entity file is skipped invisibly and search results are silently incomplete.
3. `migrate_protocol.py:340-345` - `os.remove` failures on `CONTEXT.md` are ignored, so the
   migration reports success after a partial operation.
4. `along_kb_sync.py:630-636` - deletion failures ignored, same class.
5. `along_version_bump.py:401,454,488` - `capture_output=True` with no return-code check, so
   the sanitizer, dashboard regeneration, and global install can all fail while success is
   printed (`[bug--release-engine-mutates-before-tests-and-reinstalls-globals]`).

## The diagnostics subsystem exists and is barely wired in

`scripts/along_feedback.py` implements a diagnostics store, and `along_exec.py:92-110`
provides `try_record_incident()` for exactly this purpose. It is called from the command
router only. None of the swallowed exceptions inside the engines are recorded, so
`/along-feedback` has almost nothing real to report and the "self-diagnostics" capability is
mostly theoretical.

## Impact

The dominant failure mode of this codebase is silent partial success: an engine prints an
"[OK]" line while a step did nothing. That is the hardest failure mode for an agent to
detect, because the agent trusts the tool output it is given.

## Requirements

- REQ-1: Establish an error-handling policy and record it as an ADR:
  - never `except Exception: pass`;
  - catch the narrowest applicable exception;
  - every caught exception either aborts with a clear message or is reported as a warning
    that names file, operation, and cause;
  - exit codes must reflect partial failure.
- REQ-2: Route every caught-but-continued exception through `try_record_incident()` so
  `/along-feedback` reflects reality.
- REQ-3: Add a `--verbose` / `--debug` flag to each engine that prints tracebacks instead of
  summaries.
- REQ-4: Every `subprocess.run` must have its return code checked; no success message may be
  printed after a failed child process (shared with
  `[bug--subprocess-encoding-breaks-on-non-utf8-locale]` REQ-3 via the shared
  `run_capture()` helper).
- REQ-5: Collectors that skip an unparseable entity must count and report the skips in their
  summary output, so incomplete results are visible.
- REQ-6: Add a lint gate (AST scan) that fails on `except Exception: pass` and on bare
  `except:` in `scripts/` and `dashboard/`.
- REQ-7: Tests: a malformed entity file produces a reported skip rather than a silent one; a
  failing child process yields a non-zero exit and no success message.

## Acceptance Criteria

- [ ] Zero `except Exception: pass` in `scripts/` and `dashboard/`, enforced by lint gate.
- [ ] Skipped entities counted and reported.
- [ ] Child-process failures always surfaced with non-zero exit codes.
- [ ] Continued-after-error paths recorded in diagnostics.
- [ ] ADR recorded.
