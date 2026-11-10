---
protocol: along
protocol_version: "4.7.0"
slug: release-v4-8-0
type: task
status: done
completed: 2026-11-10
priority: high
created: 2026-11-10
updated: 2026-11-10
agent: antigravity
tags: [release, version-bump, dx]
blocked_by: []
related: []
plan_status: approved
---

# Release v4.8.0, update global installation, and commit working tree

Execute minor version release pipeline to v4.8.0, synchronize documentation and dependency registrations, update global CLI installation, and push commits and release tags.

## Requirements
- REQ-1: Synchronize dependency registries and Knowledge Base links across docs and subprojects.
- REQ-2: Reconcile milestones: establish v4.8.0 milestone with completed tasks and shift empirical benchmarking to v4.9.0.
- REQ-3: Execute minor version bump to v4.8.0 through Along release pipeline with tests, typography, and link integrity verification.
- REQ-4: Update global agent installation across all supported runtimes via install.ps1.
- REQ-5: Commit all working tree changes and push branch and annotated release tags to remote.

## Acceptance Criteria
- [x] Dependency registry and Markdown link integrity gate passing.
- [x] Along version bump minor completes with release commit and annotated tag v4.8.0.
- [x] Global installer runs successfully for all target runtimes.
- [x] All commits and release tags pushed to origin/main.
