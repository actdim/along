---
protocol: along
protocol_version: "3.8.0"
slug: update-hooks-and-monorepo-sync-hardening
type: bug
status: done
completed: 2026-09-21
priority: high
created: 2026-09-21
updated: 2026-09-21
agent: antigravity
tags: [hooks, antigravity, update, monorepo, textio, windows]
milestone: v4.0.0-runtime-gates-and-worktree-isolation
blocked_by: []
related: []
---

# Update Hooks Dispatch and Monorepo Sync Hardening

## Problem Description

During repository update via `/along-update` across consumer multi-context monorepos, four interconnected issues were identified:

1. **Tool Execution Blocking due to Missing `scripts/along_hook.py`**:
   - `install_antigravity_hooks()` generates `.agents/hooks.json` specifying `"command": "python ../scripts/along_hook.py --runtime antigravity --event PreToolUse"`.
   - Consumer repositories do not contain `scripts/along_hook.py`. In Antigravity, failing hooks with exit status 2 completely block agent tool execution (`write_to_file`, `replace_file_content`, `run_command`).
   - Hooks must not hardcode non-existent local script paths and should route safely through a portable proxy/dispatcher with fail-open behavior when unconfigured.

2. **Transient Lock Failure on Windows during `along issue sync`**:
   - `along_exec.py issue sync` uses direct unbuffered `with open(issues_board, "w")` bypassing `alongkit.entities.sync_issues_board()` and `alongkit.textio.write_text()`.
   - On Windows, file locks held by IDEs or antivirus trigger `OSError: [Errno 22] Invalid argument` or `[Errno 13] Permission denied`, failing the update run.
   - File writes must use atomic writes with transient retry/backoff on Windows.

3. **Crash/Warning on Empty Constraints Projection**:
   - In subprojects without active decisions, `entities.sync_constraints()` returns an empty string `""`.
   - `along_update.py` calls `os.path.relpath(out_path, ctx_dir)`, which raises `ValueError: no path specified` on empty strings, generating unnecessary warning logs.

4. **False-Positive Dangling Link Warnings in Monorepos**:
   - `migrate_protocol.py` DAG validation only indexes entities within the immediate `ctx_dir/.along/` directory.
   - In multi-context monorepos, subprojects legitimately reference `parent`, `blocked_by`, or `related` tasks located in the root context or ancestor contexts. These references are incorrectly flagged as dangling links.

## Acceptance Criteria

- [x] Provide portable, safe hook dispatching for Antigravity, Claude, and Codex that does not hardcode non-existent `scripts/along_hook.py` in consumer repositories and degrades gracefully (fails open) if Along is not locally installed.
- [x] Route `along issue sync` through `entities.sync_issues_board()` and add retry/backoff for transient `OSError` in `alongkit.textio.write_text()`.
- [x] Guard `entities.sync_constraints()` return value in `along_update.py` before calling `os.path.relpath`.
- [x] Expand entity key resolution in `migrate_protocol.py` to include ancestor contexts up to repository root, eliminating false-positive dangling link warnings for cross-context links.
- [x] All unit tests pass cleanly.
