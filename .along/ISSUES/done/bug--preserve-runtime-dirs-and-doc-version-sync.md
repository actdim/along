---
protocol: along
protocol_version: "3.9.4"
slug: preserve-runtime-dirs-and-doc-version-sync
title: "Preserve Agent Runtime Dirs on Hook Purge and Sync Doc Versions on Release"
type: bug
status: done
completed: 2026-09-21
priority: high
created: 2026-09-21
updated: 2026-09-21
agent: antigravity
tags: [hooks, purge, runtime, docs, version-bump]
milestone: v4.0.0-runtime-gates-and-worktree-isolation
blocked_by: []
related: [bug--update-hooks-and-monorepo-sync-hardening]
---

# Preserve Agent Runtime Dirs on Hook Purge and Sync Doc Versions on Release

## Problem
1. `purge_local_along_hooks` in `scripts/alongkit/hooks/config.py` deletes `.agents/` (and `.claude/`, `.codex/`, `.cursor/`) directories when empty after purging hook manifests. If an active agent session (e.g. Antigravity) is currently running, its in-memory hook configuration binds `cwd` to `.agents`. Deleting the directory causes immediate OS-level `chdir` failures on subsequent tool executions (`run_command`, `write_to_file`).
2. `docs/topic--setup-and-workflow.md` held hardcoded `ALONG-PROTOCOL v3.7.0` on line 168. When `along-kb-sync` compiles documentation, it overwrote `llms-full.txt` back to `v3.7.0`. Furthermore, `scripts/along_version_bump.py` did not include `docs/` in its version bump targets.

## Proposed Changes
1. Modify `purge_local_along_hooks` in `scripts/alongkit/hooks/config.py`: remove `os.rmdir` on agent runtime directories (`.agents`, `.claude`, `.codex`, `.cursor`), preserving the directories so active agent processes never fail with `chdir` errors.
2. Update tests in `tests/test_update_and_hooks_hardening.py` to assert that agent directories are preserved.
3. Update `docs/topic--setup-and-workflow.md` line 168 to `v3.9.1`.
4. Update `scripts/along_version_bump.py` to include `docs/topic--setup-and-workflow.md` in `bump_along_dev_repo`.
