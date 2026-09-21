# Session Log: 2026-09-21 Update Engine Deadlock, Monorepo Hook Purge, and CLI Hardening

**Date**: 2026-09-21
**Agent**: antigravity
**Status**: Completed
**Active Issue**: [bug--update-engine-deadlock-and-cli-hardening](../../ISSUES/done/bug--update-engine-deadlock-and-cli-hardening.md)

## Summary of Accomplishments

1. **Global Lifecycle Hooks Robustness & Fail-Open Resilience**:
   - Replaced fragile inline `python -c` hook commands in `scripts/alongkit/hooks/config.py` with direct script invocations (`python "<path>/along_hook.py"`), eliminating Go/cmd.exe quote escaping corruption on Windows.
   - Added top-level fail-open error handling in `scripts/along_hook.py` catching unexpected exceptions and exiting 0 to prevent tool paralysis in agent runtimes.
   - Extended `purge_local_along_hooks` with `recursive=True` to recursively discover and purge legacy hooks and workaround scripts across all nested agent contexts in monorepos.

2. **Update Engine Fault-Tolerance & In-Memory Desynchronization Fix**:
   - Added pre-flight recursive hook purge at the start of `along_update.py`.
   - Added process restart (`os.execve`) when global tools are updated (`--global`) to eliminate stale in-memory bytecode.
   - Added per-context exception isolation (`try...except`) in `along_update.py` so a filesystem or symlink error in one subproject does not crash the entire multi-context update loop.
   - Hardened `apply_migration_to_context`: normalized paths and added broken symlink/directory checks before opening `AGENTS.md`.

3. **Unified CLI Launcher Shims & Installation Parity**:
   - Created native launcher shims: `scripts/along` (Bash), `scripts/along.cmd` (Windows CMD), and `scripts/along.ps1` (PowerShell).
   - Updated `scripts/alongkit/install.py` to include launcher shims in `engine_files()`, aligning `planned_files()` with disk layout.
   - Updated `install.ps1` and `install.sh` to install shims into `~/.along/bin/` with parity across platforms.

4. **Documentation & CLI Reference**:
   - Updated `docs/topic--cli-reference.md` with in-band vs out-of-band execution guidelines, launcher shims, and disaster recovery commands.
   - Updated `docs/topic--runtime-hooks-and-gates.md` with fail-open and recursive purge invariants.

5. **Verification & Testing**:
   - Added comprehensive tests in `tests/test_update_and_hooks_hardening.py` covering direct script hook commands, recursive subproject purge, and context exception isolation.
   - All 508 tests passed via `.along/scripts/test.py` (507 passed, 1 skipped on Windows WSL, 0 failures).
   - Typography cleanliness verified (486 files scanned, 0 banned characters).
