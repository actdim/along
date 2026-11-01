---
protocol: along
protocol_version: "4.5.4"
slug: team-worktree-lifecycle
type: feat
status: open
priority: medium
created: 2026-10-30
updated: 2026-10-30
agent: antigravity
tags: [team, worktree, git, lifecycle]
milestone: v5.1.0-language-ecosystem-expansion
blocked_by: [feat--team-worktree-concurrency-rules]
related: []
---

# Automated per-subagent git worktree lifecycle and integration management

Integrate automated Git worktree allocation, containment, and test-gated merge workflows directly into `along-team` step execution loops.

## Context and Problem Statement
While Along provides raw worktree commands (`along worktree create`, `along worktree merge`), multi-agent teams running under `along-team` frequently execute inside a single shared working directory. When implementation tasks are parallelized across multiple coder subagents or runtimes, uncommitted changes, AST indexers, and local test runners collide.

Automating the full worktree lifecycle ensures that every coding subagent receives an isolated, pristine worktree, with changes reconciled back through a formal integration gate.

## Requirements
- REQ-1: Automatic Provisioning: Entering an `along-team` implementation step MUST automatically create an isolated git worktree anchored at `.along/worktrees/<slug>-<step>` based on the active issue branch.
- REQ-2: Execution Containment: All tool invocations, code modifications, and intermediate test runs for that step MUST execute strictly within the designated worktree path.
- REQ-3: Test-Gated Integration: Before merging back to the primary branch, the integration owner (Supervisor) MUST execute `along conflict-check` and run project test suites to verify integration cleanliness.
- REQ-4: Lifecycle Cleanup: Upon successful integration and step wrap, the worktree and ephemeral branch MUST be cleaned up automatically via `along worktree gc`.

## Acceptance Criteria
- [ ] Automated worktree creation and path binding implemented in `scripts/along_team.py`
- [ ] Isolation checks preventing cross-worktree writes by active subagents
- [ ] Integration gate running automated tests before worktree squash/merge
- [ ] Automatic worktree teardown and garbage collection upon completion
- [ ] Integration test verifying worktree isolation during parallel subagent execution
