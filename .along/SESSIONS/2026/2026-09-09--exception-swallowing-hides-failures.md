---
protocol: along
protocol_version: "2.2.26"
slug: exception-swallowing-hides-failures
date: 2026-09-09
agent: antigravity
summary: "Eliminated broad exception swallowing, added centralized diagnostics incident tracking, enforced subprocess exit codes, and built AST exception handling gate"
milestone: v3.0.0-global-quality-revision
issues_advanced: []
issues_completed: [debt--exception-swallowing-hides-failures]
decisions: [ADR-2026-09-09--error-handling-and-failure-visibility]
risks_logged: []
spikes_conducted: []
---

# Session Log: 2026-09-09 - Exception Swallowing & Failure Visibility Remediation

## 1. Objectives & Context

Remediation of `[debt--exception-swallowing-hides-failures]` under the `v3.0.0-global-quality-revision` milestone:
- Eliminate `except Exception: pass` across all Along engines and dashboard code.
- Prevent silent partial success where engines report `[OK]` despite underlying errors.
- Expose centralized diagnostic telemetry without circular dependencies.
- Enforce child process exit codes across all migration and lifecycle commands.
- Implement an automated AST lint gate prohibiting bare `except:` and swallowed generic `except Exception: pass`.
- Provide uniform `-v` / `--verbose` / `--debug` CLI visibility for tracebacks.

## 2. Key Decisions & Architecture

- Recorded **`ADR-2026-09-09--error-handling-and-failure-visibility`** in `.along/DECISIONS.md`:
  * Explicitly bans bare `except:` and swallowed generic `except Exception: pass`.
  * Mandates narrow exception catching, visible warnings with file/operation/cause details, non-zero exit codes on partial failures, and traceback exposure via `--verbose` / `--debug`.
- Recompiled active architectural constraints in `.along/CONSTRAINTS.md`.

## 3. Implementation Details

1. **Centralized Incident Telemetry (`alongkit.diagnostics`)**:
   - Extracted diagnostics recording and store into `scripts/alongkit/diagnostics.py` (`try_record_incident`, `DiagnosticsStore`, `Redactor`, `ConfigManager`).
   - Integrated into `scripts/along_exec.py` and `scripts/along_feedback.py` (with backwards-compatible module wrapper).
   - Allows all engines and collectors to safely log failure incidents without circular imports.
2. **Subprocess Return Code Enforcement & Verbose Flags**:
   - `scripts/along_update.py`: Added `-v`/`--verbose`/`--debug`, checked return codes for subproject migrations and post-update synchronizers, propagating non-zero exits on failure.
   - `scripts/alongkit/migration.py`: Added error accumulation (`self.errors`, `record_error`) surfaced in summary reports.
   - `scripts/migrate_protocol.py`: Added `-v`/`--verbose`/`--debug`, verified return codes on file migrations, and exited with non-zero code on failures.
3. **Collector Skip Reporting & Narrow Exception Handling**:
   - `scripts/along_kb_search.py`: Replaced 7 `except Exception:` blocks with narrow exceptions (`OSError`, `ValueError`, `AttributeError`, `TypeError`, `FrontmatterError`). Added `_record_skip()` reporting skip counts on stderr and via `try_record_incident("collector_skip")`.
   - `dashboard/core/collector.py`: Added `self.skipped_entities` recording unreadable files; replaced 8 `except Exception:` blocks with narrow types.
   - `dashboard/app.py`: Replaced 3 broad exception blocks with narrow types (`OSError`, `webbrowser.Error`).
   - `scripts/along_dep_scan.py`: Replaced 14 `except Exception:` blocks with narrow `OSError`, `(OSError, UnicodeDecodeError)`, `(OSError, json.JSONDecodeError, UnicodeDecodeError)`, and `(ET.ParseError, OSError, UnicodeDecodeError)`. Added `-v`/`--verbose`/`--debug`.
   - `scripts/along_kb_sync.py`: Replaced 16 `except Exception:` blocks with narrow types and added `-v`/`--verbose`/`--debug`.
   - `scripts/alongkit/proc.py`, `lifecycle.py`, `along_history_sync.py`, `along_exec.py`: Replaced remaining broad handlers with narrow exceptions.
4. **AST Quality Gate (`alongkit.gates`)**:
   - Built `find_exception_violations_in_code`, `check_exception_handling`, and `exception_handling_gate` in `scripts/alongkit/gates.py`.
   - Flags any bare `except:` or swallowed generic `except Exception: pass/continue` without re-raise.
   - Added unit test suite `TestExceptionHandlingGate` in `tests/test_alongkit.py`.
5. **Regression Verification**:
   - Added `TestCollectorSkipReporting` in `tests/test_kb_search.py` verifying that malformed entity files produce reported skips and do not crash searches.

## 4. Code Review & Blast Radius Assessment

- **Diff Inspection**: Inspected all diffs across `scripts/`, `dashboard/`, and `tests/`. All changes use clean ASCII (zero typographic quotes, em-dashes, or unicode ellipsis).
- **Code Review Graph**: Updated via `code-review-graph` MCP server.
- **Downstream Callers**: All callers of `try_record_incident` and `gates` remain backward-compatible.
- **Test Suite**: Automated suite increased from 310 to 321 tests, passing with zero failures.

## 5. Completed Entities

- Closed `[debt--exception-swallowing-hides-failures]` and moved to `.along/ISSUES/done/`.
