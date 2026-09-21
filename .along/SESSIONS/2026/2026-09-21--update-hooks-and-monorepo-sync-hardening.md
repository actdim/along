# Session Log: 2026-09-21 Update Hooks Dispatch and Monorepo Sync Hardening

**Date**: 2026-09-21
**Agent**: antigravity
**Status**: Completed
**Active Issue**: [bug--update-hooks-and-monorepo-sync-hardening](../../ISSUES/done/bug--update-hooks-and-monorepo-sync-hardening.md)

## Summary of Accomplishments

1. **Global Lifecycle Hooks & Fail-Open Dispatching**:
   - Refactored runtime lifecycle hooks for Antigravity, Claude, Codex, and Cursor to install globally in user agent homes (`~/.gemini/config/hooks.json`, `~/.claude/settings.json`, `~/.codex/hooks.json`, `~/.cursor/hooks.json`), never in consumer repositories.
   - Replaced fragile relative script calls with a shell-independent Python one-liner that tests for `~/.along/bin/along_hook.py` before invoking, completely eliminating `[Errno 2] No such file or directory` blocking in non-Along repositories.
   - Added fail-open logic to `scripts/along_hook.py`: exits 0 cleanly when the workspace does not contain Along context (`.along/`, `.agents/`, or `AGENTS.md`).

2. **Automatic Purging of Legacy Local Hooks & Workaround Scripts**:
   - Implemented `purge_local_along_hooks(repo_root, dry_run=False)` in `scripts/alongkit/hooks/config.py`.
   - Purges spurious `.agents/hooks.json`, Along hooks in `.claude/settings.json`, `.codex/hooks.json`, `.cursor/hooks.json`, and workaround scripts `scripts/along_hook.py` and `.along/scripts/along_hook.py` in consumer repositories while preserving non-Along user configurations.
   - Integrated purging into both `/along-update` (`scripts/along_update.py`) and protocol migration (`scripts/migrate_protocol.py`, Step 12).
   - Ensured migration executes Step 12 even if the protocol version was already marked as current.

3. **Windows File Contention Hardening**:
   - Added retry loop with exponential backoff (up to 5 attempts across 50ms-400ms) in `scripts/alongkit/textio.py` for Win32 sharing violations (`OSError` Errno 13, 22).
   - Routed `along issue create`, `along issue done`, and `along issue sync` through `entities.sync_issues_board()`.

4. **Monorepo Cross-Context Resolution & Empty Constraints Guard**:
   - Expanded entity key resolution in `scripts/migrate_protocol.py` to index ancestor contexts up to repository root, eliminating false-positive dangling link warnings for cross-context links (`parent`, `blocked_by`, `related`).
   - Guarded `entities.sync_constraints()` in `scripts/along_update.py` to prevent `ValueError: no path specified` when subprojects have no active decisions.

5. **Verification & Testing**:
   - Updated `test_34_along_update_purges_local_runtime_hooks` in `tests/test_skills_and_scripts.py`.
   - Created dedicated test suite `tests/test_update_and_hooks_hardening.py`.
   - Ran all 506 tests via `python .along/scripts/test.py` with zero failures.
