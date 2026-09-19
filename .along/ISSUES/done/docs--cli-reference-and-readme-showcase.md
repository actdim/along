---
protocol: along
slug: cli-reference-and-readme-showcase
type: docs
status: done
priority: medium
created: 2026-09-14
updated: 2026-09-14
completed: 2026-09-14
agent: antigravity
tags: [cli, docs, readme, worktree, hooks, gates]
milestone: v4.0.0-runtime-gates-and-worktree-isolation
blocked_by: []
related: [feat--runtime-worktree-isolation, feat--declarative-gates-and-protocol-traceability]
---

# Unified CLI Reference and README Capabilities Showcase

## 1. Problem Statement & Context
Along provides a canonical developer CLI (`along <command>` routed via `scripts/along_exec.py`), but documentation across `docs/` is fragmented:
- `docs/topic--skills-reference.md` focuses on agent slash commands (`/along-*`) rather than developer terminal syntax, arguments, and exit codes.
- Multiple native CLI commands (`along doctor`, `along status`, `along budget`, `along patch`, `along scratch`, `along rules`) have zero documentation in topic articles and are discoverable only through `along --help` and tests.
- `README.md` does not yet highlight Along v4.0.0's two major architectural differentiators:
  1. Runtime Git Worktree Workspace Isolation with the 3-part Environment Readiness Contract (NTFS junctions / symlinks for dependencies, `.env` propagation, shared session blackboards).
  2. Runtime Mechanical Prose Enforcement (lifecycle hook adapters intercepting `PreToolUse` and `Stop` to turn soft prompt guidelines into hard runtime errors with bi-directional gate traceability).

## 2. Scope & Requirements
1. **Canonical CLI Reference (`docs/topic--cli-reference.md`)**:
   - Full command dictionary covering all 3 sub-families: Lifecycle Hooks, Entity & Protocol Management, and Protocol Tool Engines.
   - Comprehensive argument matrices, options, exit codes, and invocation fallback paths.
2. **KB Cross-Linking & Gap Closure**:
   - Register `topic--cli-reference.md` in `docs/INDEX.md`.
   - Cross-link `doctor`, `status`, `budget`, and `worktree` in `docs/topic--setup-and-workflow.md` and `docs/topic--architecture.md`.
3. **README Showcase**:
   - Expand "Why Along?" problem statement with workspace contamination and unanchored soft prompt hallucinations.
   - Add "Runtime Worktree Workspace Isolation" and "Runtime Mechanical Prose Enforcement" pillars to the Core Value Proposition table.
   - Update repository drop-in blurb and Knowledge Base index table.
4. **Verification**:
   - Verify link integrity and section taxonomy via `along kb sync`.
   - Verify zero forbidden typography via `along sanitize`.
   - Verify gate traceability via `along hook verify --strict`.
   - Run hermetic test suite via `along test`.
