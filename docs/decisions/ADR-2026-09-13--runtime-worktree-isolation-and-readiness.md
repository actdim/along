---
protocol: along
slug: runtime-worktree-isolation-and-readiness
type: decision
title: "Runtime-Native Git Worktree Workspace Isolation and Environment Readiness"
date: 2026-09-13
status: accepted
tags: [adr, architecture, decision, worktree, isolation, along-team]
---

# ADR-2026-09-13--runtime-worktree-isolation-and-readiness - Runtime-Native Git Worktree Workspace Isolation and Environment Readiness

- Date: 2026-09-13
- Status: accepted
- Context: Executing complex engineering tasks or autonomous goals (via /along-team or /goal) directly inside the developer active working tree introduces major operational hazards: uncommitted local work-in-progress (WIP) files risk contamination or accidental deletion, background language servers and file watchers face contention, and aborted runs leave half-applied patches. Switching branches in-place (git checkout -b) mutates open editor buffers and restarts dev servers. Conversely, bare Git worktrees (git worktree add) lack gitignored dependencies (node_modules, .venv) and local configuration (.env), causing test runners and linters to crash immediately.
- Decision: Establish a comprehensive Git worktree workspace isolation standard and lifecycle engine (alongkit.worktree and along worktree CLI) governed by the following core architectural rules:
  1. Universal Entity Scope: Workspace isolation applies to all entity types (feat, bug, debt, task, docs) and autonomous /goal execution runs.
  2. Invocation and Semantic Intent: Activated explicitly via the --worktree flag (/along-team <slug> --worktree, /goal --worktree, or config workspace: worktree) or resolved automatically from unambiguous natural language intent ("in an isolated worktree", "isolate this task"). Standard prompts lacking explicit isolation intent default to workspace: inherit to prevent unnecessary environment provisioning overhead.
  3. Environment Readiness Contract: Before worker execution begins, the orchestrator must satisfy three prerequisites:
     a. Dependency Linking: Share heavy package directories (node_modules, .venv, venv) from the primary repository using NTFS directory junctions on Windows (cmd /c mklink /J) and symbolic links on POSIX (os.symlink) without duplicating gigabytes of files.
     b. Configuration Propagation: Copy untracked configuration (.env, .env.local, local.settings.json) into the worktree so that runtime secrets are accessible but isolated from modification.
     c. Protocol State Preservation: Share the ephemeral session blackboard (.along/.session/<slug>/) or execute a pre-teardown flush to guarantee that failure logs, retry counters, and session history survive worktree teardown.
  4. Strict Fail-Fast Policy: In Phase 0 (Supervisor), the agent evaluates host runtime and filesystem capabilities. If worktree isolation was requested but environment readiness cannot be satisfied (unsupported filesystem, uncommitted merge conflicts in parent, broken junctions), the agent MUST IMMEDIATELY HALT WITH AN ERROR. Silent degradation to the primary working tree is strictly forbidden.
  5. Dependency Safety Boundaries: Mutating package operations (npm install, pip install) within an isolated worktree alter shared parent dependencies through junctions and are forbidden without explicit operator confirmation.
  6. Windows File Handle Lock Resilience: To prevent ERROR_ACCESS_DENIED during git worktree remove on Windows, teardown enforces:
     a. Junction Pre-Unlink: Directory junctions are explicitly unlinked using os.rmdir (never shutil.rmtree, which would delete parent repository packages).
     b. CWD Reset: The runner process and child processes reset their working directory to the primary repository root (os.chdir(repo_root)).
     c. Retry Backoff: Worktree deletion runs an exponential backoff retry loop (4 attempts, 0.5s intervals) to allow transient indexer or antivirus locks to release.
     d. Deferred Garbage Collection: Persistent locks trigger worktree unlinking in Git followed by directory quarantine to .along/worktrees/.trash_<timestamp> recorded in .along/.pending_worktrees.json for cleanup by subsequent along worktree gc invocations.
  7. Gate Execution Manifest Logging: The selected workspace mode (workspace: worktree or workspace: inherit) and environment readiness status must be explicitly recorded in Phase 0 and logged in the Gate Execution Manifest.
- Consequences: Autonomous multi-agent pipelines and human-requested tasks can execute in hermetic, isolated filesystem directories without disrupting developer editors or contaminating working trees. Guarantees immediate test readiness without redundant package installations. Prevents loss of debugging forensics on task failure. Eliminates Windows file-handle deletion crashes through deterministic junction unlinking and deferred garbage collection.
