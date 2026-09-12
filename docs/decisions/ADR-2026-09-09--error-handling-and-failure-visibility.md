---
protocol: along
slug: error-handling-and-failure-visibility
title: "Explicit Error Handling, Failure Visibility, and Centralized Diagnostics"
date: 2026-09-09
status: accepted
tags: [adr, architecture, decision]
---

# ADR-2026-09-09--error-handling-and-failure-visibility - Explicit Error Handling, Failure Visibility, and Centralized Diagnostics

- Date: 2026-09-09
- Status: accepted
- Context:
  1. Across twelve Along engines there were roughly 70 try blocks and over 50 broad except clauses, with 32 silent `except Exception: pass` blocks hiding failures from users and diagnostics (`[debt--exception-swallowing-hides-failures]`).
  2. Silent exception swallowing caused severe real-world defects: a NameError on missing json import broke commit test detection invisibly, collector loops dropped malformed entities without notification, and child process failures were ignored while engines printed [OK].
  3. The diagnostics subsystem (`along_feedback.py`) existed but was accessible only via dynamic import from `along_exec.py`, leaving engines with no clean way to report caught exceptions.
- Decision:
  1. **Strict Exception Policy**:
     - `except Exception: pass` and bare `except:` are strictly forbidden across `scripts/` and `dashboard/`.
     - Handlers must catch the narrowest applicable exception type (`(OSError, json.JSONDecodeError, ValueError, KeyError, frontmatter.FrontmatterError)`).
     - Every caught-and-continued exception must either emit a warning to `sys.stderr` naming the target, operation, and cause, or be tracked in an explicit skip counter.
  2. **Centralized Diagnostics Library**:
     - `DiagnosticsStore`, `Redactor`, and `try_record_incident()` are consolidated in `alongkit.diagnostics`, importable by all engines with zero circular dependencies.
     - Caught-and-continued errors are recorded as diagnostic incidents with appropriate event types (`collector_skip`, `warning`, `script_crash`).
  3. **Subprocess Failure Propagation**:
     - Child process exit codes must be checked. No engine may output `[OK]` after a failed child process.
  4. **AST Lint Gate Enforcement**:
     - Add an automated AST lint gate (`alongkit.gates.check_exception_handling`) enforced in CI tests to fail if any `except Exception: pass` or bare `except:` is introduced.
- Consequences:
  - Eliminates silent partial failures and invisible data dropping across all Along engines.
  - Telemetry and diagnostics in `~/.along/diagnostics/` reflect actual engine execution and failures.
  - Subprocess errors correctly propagate non-zero exit codes to callers and CI.
