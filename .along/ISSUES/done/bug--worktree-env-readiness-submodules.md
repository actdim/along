---
protocol: along
protocol_version: "4.6.0"
slug: worktree-env-readiness-submodules
type: bug
status: done
completed: 2026-11-06
plan_status: approved
priority: medium
created: 2026-11-04
updated: 2026-11-06
agent: antigravity
tags: []
blocked_by: []
related: []
---

# worktree-env-readiness misfires on git submodules and blocks recovery

The worktree-env-readiness gate incorrectly treats git submodules as git worktrees because submodules also carry a .git file starting with gitdir:. In addition, the gate evaluates against the session cwd rather than the target file path, fails to recognize dependency resolution across ancestor monorepo/workspace roots, blocks Along recovery commands such as along gates ack and plain cd, and produces misleading remediation messages.

## Requirements
- REQ-1: `worktree-env-readiness` gate and `is_worktree` predicate MUST distinguish Git worktrees from Git submodules using Git metadata (`worktrees/` directory segment in gitdir target, `commondir` pointer). Submodules MUST NOT trigger worktree environment readiness denials.
- REQ-2: `worktree-env-readiness` gate MUST evaluate target paths for file modification tools and effective working directory after leading directory changes (e.g., `cd`) for shell commands, rather than solely inspecting session cwd.
- REQ-3: `worktree-env-readiness` gate MUST NEVER deny Along recovery, diagnostic, and governance commands (`along gates ack`, `along gates stats`, `along gates denials`, `along doctor`, `along plan status`, `along status`, `along gates check`) or directory navigation commands (`cd`, `pwd`), preventing deadlocks with `unresolved-gate-denial`.
- REQ-4: For nested Along subprojects or workspaces, `worktree-env-readiness` MUST treat `node_modules` as satisfied if present in the subproject itself or in an ancestor workspace root (e.g., `pnpm-workspace.yaml`, `package.json` workspaces).
- REQ-5: When a readiness violation occurs, the diagnostic message MUST specify the detected Git worktree path, gitdir target, primary repository, and actionable fix.

## Acceptance Criteria
- [x] Git submodules with `gitdir: .../modules/...` are not classified as worktrees and never denied by `worktree-env-readiness`.
- [x] Editing files outside an unlinked worktree (e.g., superproject `.along/` issues) is allowed regardless of session cwd.
- [x] Shell commands with leading `cd` are evaluated against the target directory.
- [x] Along recovery commands (`along gates ack`, `along doctor`, `along gates stats`, `along plan status`) and `cd` are never blocked by `worktree-env-readiness`.
- [x] Dependencies in parent workspace roots satisfy readiness for nested subprojects.
- [x] Worktree violation message identifies the worktree, primary repo, and actionable remediation.
- [x] Comprehensive hermetic test suite passes with all new test cases.
