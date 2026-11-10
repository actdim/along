---
protocol: along
protocol_version: "4.7.0"
slug: worktree-lifecycle-hardening
type: feat
status: open
priority: medium
created: 2026-11-07
updated: 2026-11-07
agent: antigravity
tags: [worktree, lifecycle, git, safety, cleanup]
blocked_by: []
related: [feat--team-worktree-lifecycle]
---

# Harden Git Worktree Lifecycle: Wrap Guards, Doctor Audits, and Commit Checks

Ensure that isolated development worktrees provisioned under `.along/worktrees/<slug>` are verified, safeguarded against data loss, and cleaned up automatically across core Along lifecycle commands.

## Context and Problem Statement

Along supports provisioning isolated Git worktrees via `along worktree create` and `along start <slug> --worktree`. These worktrees allow developers and agents to run heavy builds, tests, and code modifications in an isolated workspace without polluting the main repository working directory.

However, the lifecycle integration currently has critical gaps:
1. When a user or agent finalizes an issue via `along wrap <slug>`, the wrap engine does not inspect `.along/worktrees/<slug>`. If uncommitted or unmerged changes exist in the worktree, wrapping the issue can abandon those changes on an orphaned branch.
2. Even when changes are merged, the worktree directory and associated NTFS junctions/symlinks remain on disk indefinitely unless manually removed via `along worktree remove <slug>`. Over time, dangling worktrees consume substantial disk space and retain file locks.
3. `along doctor` does not audit worktrees for "zombie" states (worktrees associated with already closed issues or deleted branches).
4. `along commit` does not warn if a developer commits directly in the primary working directory while an active worktree is provisioned for the current issue, leading to divergence between the root and worktree branches.

## Requirements

- REQ-1 (Wrap Unmerged Changes Guard): `along wrap <slug>` MUST inspect `.along/worktrees/<slug>`. If the worktree contains uncommitted changes or branch commits that have not been merged into the parent branch, wrap MUST abort with an error unless an explicit force option (`--force-reason`) is supplied.
- REQ-2 (Wrap Automated Teardown): Upon successful wrap of an issue, `along wrap` MUST automatically tear down the clean worktree via `alongkit.worktree.remove_worktree` (or schedule deferred pruning if file locks are temporarily active).
- REQ-3 (Doctor Dangling Worktree Audit): `along doctor` MUST audit all registered Git worktrees against project issue states. Any worktree whose corresponding issue is in `ISSUES/done/` or whose branch is already merged MUST be reported as a dangling zombie worktree, with a direct recommendation to run `along worktree gc`.
- REQ-4 (Commit Divergence Check): `along commit` SHOULD warn if the active bound issue has an open worktree, preventing inadvertent parallel edits in the main repository tree.
- REQ-5 (ASCII Typography and Testing): All changes must maintain strict ASCII typography and pass hermetic unit tests verifying teardown, unmerged guards, and doctor audits.

## Acceptance Criteria

- [ ] `along wrap` detects unmerged worktrees and prevents accidental closeout without data migration.
- [ ] `along wrap` automatically removes clean worktrees and unlinks dependency junctions.
- [ ] `along doctor` detects and reports orphaned worktrees with actionable remediation commands.
- [ ] `along commit` warns on root-vs-worktree branch divergence for active issues.
- [ ] Hermetic tests verify wrap guards, teardown, and doctor reporting.
- [ ] Passes `python scripts/sanitize_typography.py --check` with 0 banned characters.
