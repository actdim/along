---
protocol: along
protocol_version: "3.6.0"
slug: python-monolithic-functions-and-boilerplate
type: debt
status: open
priority: high
created: 2026-09-16
updated: 2026-09-16
agent: antigravity
tags: [refactoring, architecture, maintainability, dead-code, boilerplate]
milestone: v4.0.0-runtime-gates-and-worktree-isolation
blocked_by: []
related: [debt--python-error-handling-and-io-consistency]
---

# Python Monolithic Functions Refactoring and Boilerplate Standardization

## Problem
Several core engine modules suffer from monolithic function sizing and repetitive boilerplate that create maintenance friction:
1. Monolithic routines exceeding single-responsibility scope:
   - `sync_kb` in `scripts/along_kb_sync.py` (lines 980-1472, ~500 lines encompassing 9 synchronization phases).
   - Migration step functions `step_migrate_v1_5_entity_ecosystem` (lines 186-394, >200 lines), `step_migrate_v2_0` (lines 399-563, >160 lines), and `run_migrations` (172 lines) in `scripts/migrate_protocol.py`.
   - `handle_issue_command` in `scripts/along_exec.py` (lines 166-414, ~249 lines combining subcommands create, done, sync, list).
2. Repeated boilerplate across all engine entry points:
   - 17x duplicated `sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))` preamble instead of a unified bootstrap loader.
3. Dead code and orphaned helpers:
   - `scripts/migrate_protocol.py:703-713`: `candidates` resolution loop is immediately overwritten on line 715 by `repo.resolve_tool_script`.
   - `synthesize_dep_scan_hook_template` has 0 callers across the repository.
   - Unused imports in `scripts/along_exec.py:33-34` (`Path`, typing generics).
   - Dead alias `try_record_incident` in `scripts/along_exec.py:93`.

## Requirements
- Decompose `sync_kb` into discrete stage handlers (article ingestion, link integrity validation, crosslink indexing, provenance drift detection).
- Break down `step_migrate_v1_5`, `step_migrate_v2_0`, and `handle_issue_command` into cohesive helper sub-handlers.
- Standardize script entry point initialization and eliminate duplicated `sys.path` manipulation.
- Remove dead candidate resolution loops, unused imports, and unreferenced helper functions.
- Verify that all hermetic unit tests pass with zero regressions.

## Acceptance Criteria
- [ ] `sync_kb` decomposed into stage-specific helper functions with cyclomatic complexity reduced.
- [ ] `handle_issue_command` split into individual subcommand functions (`do_create`, `do_done`, `do_sync`, `do_list`).
- [ ] Dead code in `migrate_protocol.py:703-713` and unused imports in `along_exec.py` purged.
- [ ] Automated tests pass: `python .along/scripts/test.py`.
