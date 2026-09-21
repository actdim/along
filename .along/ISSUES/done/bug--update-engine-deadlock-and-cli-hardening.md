---
protocol: along
protocol_version: "3.9.2"
slug: update-engine-deadlock-and-cli-hardening
type: bug
status: done
completed: 2026-09-21
priority: high
created: 2026-09-21
updated: 2026-09-21
agent: antigravity
tags: [update, hooks, deadlock, cli, monorepo, fail-open, windows]
milestone: v4.0.0-runtime-gates-and-worktree-isolation
blocked_by: []
related: [bug--update-hooks-and-monorepo-sync-hardening]
---

# Update Engine Deadlock, Monorepo Hook Purge, and CLI Launcher Hardening

## Problem Description
Post-mortem analysis of repository updates across consumer multi-context monorepos revealed:
1. Tool interception deadlock: PreToolUse hook failed on Windows when scripts/along_hook.py was removed or when python -c quoting broke in Go/cmd.exe, paralyzing mutating agent tools.
2. In-memory bytecode desynchronization (split-brain): along_update.py downloaded new versions to disk but continued running old in-memory bytecode, recreating purged hooks.
3. Monorepo traversal crash: invalid filesystem arguments or broken symlinks in one subproject crashed the entire update loop.
4. Hook purge was non-recursive, leaving nested subproject hooks uncleaned.
5. Direct CLI invocation lacked standard platform launcher shims (along, along.cmd, along.ps1).

## Acceptance Criteria
- [x] Use direct script invocation instead of fragile inline python -c in global hooks.
- [x] Add fail-open top-level exception handling in along_hook.py.
- [x] Recursively purge legacy hooks across all monorepo agent contexts in purge_local_along_hooks.
- [x] Pre-flight recursive hook purge at the start of along_update.py.
- [x] Re-execute process via os.execve on global toolchain update to eliminate stale bytecode.
- [x] Isolate context updates with try...except so single subproject errors do not crash the update.
- [x] Add CLI launcher shims (along, along.cmd, along.ps1) and ensure installer parity.
- [x] Update CLI reference and runtime hook documentation.
- [x] Pass all automated tests and typography gate.
