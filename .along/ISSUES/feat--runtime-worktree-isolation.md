---
protocol: along
slug: runtime-worktree-isolation
type: feat
status: open
priority: medium
created: 2026-09-06
updated: 2026-09-06
agent: antigravity
tags: [git, worktree, runtime, along-team, isolation]
milestone: v2.1.0-along
blocked_by: []
related: [debt--team-skill-state-not-persisted]
---

# Runtime-native Git worktree workspace isolation mode

## 1. Problem Statement & Background

Executing complex software development tasks or autonomous objectives (via `/along-team`, `/goal`, or CLI commands) directly inside the developer's active working directory introduces serious operational hazards:
- Uncommitted local work-in-progress (WIP) files risk contamination or accidental deletion.
- Background language servers, file watchers, test processes, and active IDE instances face contention and disruption.
- Failed autonomous execution runs leave corrupted source files or half-applied patches across the active tree.

### Fundamental Distinction: In-Place Git Branch vs Git Worktree

- **Standard In-Place Git Branch (`git checkout -b <branch>`)**: Switches branches directly in the developer's current working directory. This mutates open editor buffers, triggers language server re-indexing, restarts dev servers, and risks colliding with uncommitted local modifications.
- **Git Worktree (`git worktree add <path> <branch>`)**: Creates an independent, parallel directory on the filesystem linked to the shared `.git` repository object store. The developer's primary working tree remains completely untouched and pristine, while the agent executes its entire workflow in the dedicated directory.

## 2. Core Requirements

1. **Universal Scope Across All Entity Types**:
   - The workspace isolation mechanism must support every Along protocol entity type (`bug`, `feat`, `debt`, `task`, `docs`) as well as autonomous goal execution runs (`/goal`).

2. **Invocation Flags & Semantic Intent Routing**:
   - **Explicit Flag**: `--worktree` (e.g. `/along-team <slug> --worktree`, `/goal --worktree`, or configuration `workspace: worktree`).
   - **Semantic Activation**: The agent automatically resolves natural language intent ("in an isolated worktree", "run without touching my active workspace", "isolate this task") to the `--worktree` execution mode.
   - **False Positives Guard**: The orchestrator must never activate worktree mode on standard requests lacking explicit isolation intent ("implement feature", "fix bug") to avoid unnecessary environment provisioning overhead.

3. **Environment Readiness Contract**:
   - Creating a bare working directory via `git worktree add` is insufficient: gitignored directories and files (`node_modules`, `.venv`, `.env`, local configuration files, build caches) do not exist in newly checked out worktrees.
   - Runtime support MUST encompass environment readiness:
     - Native sharing or linking of dependency directories (`node_modules`, `.venv`) via NTFS junctions, symlinks, or Copy-on-Write (CoW) storage without duplicating gigabytes of packages.
     - Propagation of local environment variables and untracked configuration (`.env`, `.env.local`).
   - If a mechanism only yields a bare working tree without dependency access, the environment is dysfunctional because test runners and linters will immediately crash.

4. **Strict Fail-Fast on Unsupported Runtimes**:
   - During Phase 0 (Supervisor), the agent must evaluate the capabilities of the active host runtime (both directory isolation and environment readiness).
   - Applied identically to explicit flags and semantic triggers: if the active runtime does not support worktree isolation with environment readiness, the agent **MUST IMMEDIATELY HALT WITH AN ERROR**.
   - Silent degradation or unauthorized modification of the user's primary working tree while worktree mode was requested is strictly forbidden.

5. **Mandatory Logging in Gate Execution Manifest**:
   - The selected workspace mode (`workspace: worktree` or `workspace: inherit`) must be explicitly announced in Phase 0 and logged in both the Gate Execution Manifest and session log.

## 3. Host Runtime Capability Matrix

1. **Google Antigravity**:
   - The `invoke_subagent` tool natively provides a `Workspace` parameter:
     - `share`: creates a workspace sharing the underlying repository directory (similar to git worktree / hg share), enabling independent branching without duplicating storage.
     - `branch`: creates an isolated branched or cloned workspace.
     - `inherit`: executes within the parent workspace directory (default).
   - Audit required: verify how Antigravity propagates untracked dependencies (`node_modules`), temporary directory layouts, and cleanup triggers on completion.

2. **Claude Code**:
   - Offers a native `--worktree` CLI flag that provisions tasks in isolated git worktrees (`.claude/worktrees/...`).
   - Audit required: evaluate how Claude Code handles untracked files and whether programmatic activation from within skills/subtasks is supported.

3. **OpenAI Codex / OpenCode**:
   - Lack proprietary host workspace isolation APIs.
   - Audit required: determine whether an automated terminal adapter (`git worktree add` + dependency junction linking) is viable or whether strict fail-fast halt must occur on these platforms.

## 4. Engineering Risks & Trade-offs

1. **Dependency Integrity & Isolation**:
   - When sharing `node_modules` via junctions, test suites run immediately, but commands that install packages (`npm install`) mutate the shared parent folder. Clear boundary rules for package manager operations inside worktrees are required.

2. **Along Protocol State Preservation (`.along/`)**:
   - Along stores active execution state (`.along/ISSUES/`, `.along/SESSIONS/`, `.along/.session/<slug>/blackboard.md`) on disk.
   - If `.along/` is isolated inside the worktree and the worktree is destroyed on failure (`git worktree remove --force`), all session logs and failure forensics will be lost.
   - Solution: shared junction / symlink for `.along/` or an explicit pre-teardown flush to the primary repository.

3. **Windows File Handle Locks**:
   - Language servers, build daemons, and file indexers on Windows frequently hold open file handles in worktrees.
   - Teardown via `git worktree remove --force` frequently fails with `Access is denied`. Requires robust process termination and deferred cleanup strategies.

4. **Worktree Lifecycle & Integration Gate**:
   - Provisioning: `git worktree add <worktree-path> -b along/<type>--<slug>`.
   - Environment initialization: verify dependencies, virtual environments, and configuration.
   - Step execution: run tests and linters strictly scoped to `<worktree-path>`.
   - Verification & Merge: Reviewer issues `PASS`, Gate Execution Manifest is recorded, changes are squash-merged into parent branch, or branch is retained with manual PR instructions.
   - Teardown: prune worktree (`git worktree remove`) and delete temporary branches.

## Acceptance Criteria

- [ ] Audit workspace and worktree isolation capabilities across target runtimes (Google Antigravity `Workspace: 'share'|'branch'`, Claude Code `--worktree`, OpenAI Codex, OpenCode).
- [ ] Record an Architectural Decision Record in `.along/DECISIONS.md` defining the `--worktree` flag, runtime capability matrix, environment readiness contract, and fail-fast policy.
- [ ] Update `along-team` (and `/goal` specification):
  - Document `--worktree` flag and semantic intent routing rules.
  - Implement false-positive trigger protections.
  - Implement Phase 0 (Supervisor) runtime capability verification.
  - Enforce strict fail-fast halt when worktree isolation with environment readiness is unsupported.
  - Add workspace mode reporting to the Gate Execution Manifest.
- [ ] Define dependency safety boundaries (`node_modules`, `.venv`) in isolated trees.
- [ ] Implement `.along/` state preservation protocol to prevent loss of session logs during worktree teardown.
- [ ] Test complete worktree lifecycle (provisioning, environment linking, isolated test execution, merge, teardown) under Windows filesystem locking constraints.



