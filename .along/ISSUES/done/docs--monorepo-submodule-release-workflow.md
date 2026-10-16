---
protocol: along
protocol_version: "4.4.16"
slug: monorepo-submodule-release-workflow
type: docs
status: done
completed: 2026-10-16
priority: medium
created: 2026-10-16
updated: 2026-10-16
agent: antigravity
tags: [documentation, monorepo, submodules, release, version-bump]
blocked_by: []
related: [subproject-boundary-is-git-or-explicit-init]
---

# Document Monorepo vs Submodule Release Workflows and Cascading Version Bumps

## Problem

Developers and agents often confuse Monorepo Workspaces (single Git repository with multiple packages) and Git Submodules (multiple independent Git repositories). This leads to misunderstandings about how `along commit` and `along bump` behave across subprojects, why root `along bump` does not blindly cascade commits and pushes into Git submodules by default, and how to implement coordinated lockstep releases using the project hook `.along/scripts/bump_version.py`.

## Requirements

- REQ-1: Clarify the architectural distinction between Monorepo Workspaces (single Git history, atomic multi-package commits) and Git Submodules (distributed Git repositories, independent remotes, pointers only) in `docs/topic--architecture.md`.
- REQ-2: Add a dedicated section to `docs/topic--setup-and-workflow.md` explaining release workflows for Monorepos vs Git Submodules.
- REQ-3: Document the custom project hook pattern for `.along/scripts/bump_version.py` showing how to orchestrate cascading submodule releases when unified lockstep versioning is required.
- REQ-4: Verify link integrity (`along kb sync --check`) and clean ASCII typography (`along sanitize`).

## Acceptance Criteria

- [x] `docs/topic--architecture.md` distinguishes Monorepo Workspaces from Git Submodules.
- [x] `docs/topic--setup-and-workflow.md` explains monorepo vs submodule release differences and provides the cascading `.along/scripts/bump_version.py` pattern.
- [x] Documentation passes `along kb sync --check` with 0 broken links.
- [x] Typography passes clean ASCII check.
