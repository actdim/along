---
protocol: along
protocol_version: "3.6.0"
slug: python-error-handling-and-io-consistency
type: debt
status: done
completed: 2026-09-21
priority: high
created: 2026-09-16
updated: 2026-09-21
agent: antigravity
tags: [error-handling, cli, io, paths, semver, consistency]
milestone: v4.0.0-runtime-gates-and-worktree-isolation
blocked_by: []
related: [debt--python-monolithic-functions-and-boilerplate]
---

# Python Error Handling Hardening, CLI Parsing, and IO Standardization

## Problem
Inconsistencies and silent failure modes in the Python codebase hinder reliability and diagnostics:
1. Silent error swallowing:
   - `along_exec.py:834-838, 873-876, 884-888`: `int(args[i+1])` inside `try...except ValueError: pass` silently drops invalid flag arguments (e.g. `--steps abc` results in `None` without user feedback).
   - Silent swallowing of `import along_kb_sync` in `along_exec.py:580,637` and `migrate_protocol.py:1270` with `except (ImportError, AttributeError): pass` hides decision synchronization failures.
   - Deceptive UTF-8 BOM message in `along_exec.py:341-347` vs `:381`: prints `Normalized a UTF-8 BOM`, but `block.bom` is preserved and written back to disk on line 382.
2. Fragile hand-rolled argument parsing:
   - 8 sites in `along_exec.py` use manual `while i < len(args)` loops instead of structured `argparse` subparsers or validation.
3. Path and I/O layer divergence:
   - 20 sites perform manual `.replace('\\', '/')` instead of calling `alongkit.repo.normalize_posix`.
   - 14 sites in `along_exec.py` use raw `open(..., encoding="utf-8")` calls instead of `alongkit.textio.read_text` / `write_text`.
4. Logic quirks and duplicated constants:
   - `along_dep_scan.py:570`: `sorted(versions)[-1]` performs lexicographical string sorting instead of semver/version-aware sorting (`"1.9.0" > "1.10.0"`).
   - Gate configuration constants duplicated across `alongkit/hooks/predicates.py:22-32` and `alongkit/hooks/gates.py:34-149`.
   - Protocol version comparison tuples `(2, 2, 9)` and `(3, 0, 0)` repeated across 7 migration steps in `migrate_protocol.py`.

## Requirements
- Replace silent exception swallowing with explicit error logging or validation failures for invalid CLI arguments.
- Reconcile UTF-8 BOM stripping logic in `along_exec.py` so the file is genuinely written without BOM when normalized.
- Migrate manual CLI argument loops in `along_exec.py` to structured parsing with validation.
- Standardize path normalization on `alongkit.repo.normalize_posix`.
- Unify file I/O on `alongkit.textio` functions.
- Fix version sorting in `along_dep_scan.py` to use version comparison instead of lexicographical sort.
- Deduplicate gate constants and protocol version threshold constants into shared definitions.

## Acceptance Criteria
- [x] Invalid numeric CLI arguments produce helpful stderr error messages with non-zero exit codes.
- [x] BOM normalization in `along_exec.py` genuinely strips BOM bytes on output.
- [x] Manual string path replacements replaced by `repo.normalize_posix`.
- [x] Version selection in `along_dep_scan.py` correctly ranks semantic versions (e.g. 1.10.0 > 1.9.0).
- [x] All unit tests pass: `python .along/scripts/test.py`.
