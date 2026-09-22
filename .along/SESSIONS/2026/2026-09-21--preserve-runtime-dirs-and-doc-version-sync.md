---
protocol: along
slug: preserve-runtime-dirs-and-doc-version-sync
date: 2026-09-21
agent: antigravity
summary: "Preserved agent runtime directories on hook purge and synchronized protocol version mentions in documentation"
milestone: v4.0.0-runtime-gates-and-worktree-isolation
issues_advanced: []
issues_completed: [bug--preserve-runtime-dirs-and-doc-version-sync]
decisions: []
risks_logged: []
spikes_conducted: []
branch: main
commit: unknown
---

# Session Log: 2026-09-21 Preserve Runtime Dirs and Doc Version Sync

**Date**: 2026-09-21
**Agent**: antigravity
**Status**: Completed
**Active Issue**: [bug--preserve-runtime-dirs-and-doc-version-sync](../../ISSUES/done/bug--preserve-runtime-dirs-and-doc-version-sync.md)

## Summary of Accomplishments

1. **Preserve Agent Runtime Dirs on Hook Purge**:
   - Fixed `purge_local_along_hooks()` in `scripts/alongkit/hooks/config.py` to remove `os.rmdir` on agent runtime directories (`.agents`, `.claude`, `.codex`, `.cursor`).
   - Prevents OS-level `chdir` failures in active agent processes whose in-memory hook configurations bind `cwd` to `<workspace>/.agents` (or `.claude`, etc.).
   - Updated test assertions in `tests/test_update_and_hooks_hardening.py` to verify that agent configuration directories are preserved during hook purge.

2. **Synchronize Protocol Version Mentions in Documentation**:
   - Updated hardcoded `ALONG-PROTOCOL v3.7.0` to `v3.9.1` in `docs/topic--setup-and-workflow.md`.
   - Updated `bump_along_dev_repo()` in `scripts/along_version_bump.py` to scan `docs/topic--*.md` and update protocol version mentions during releases, eliminating future documentation version drift.

3. **Verification**:
   - Recompiled Knowledge Base via `along kb-sync`.
   - Executed full test suite via `.along/scripts/test.py` (506 tests passing, 0 failures).
