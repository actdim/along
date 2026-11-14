---
protocol: along
protocol_version: "4.8.1"
slug: git-automerge-protection-and-semantic-merge
type: feat
status: in-progress
priority: high
created: 2026-11-14
updated: 2026-11-14
agent: antigravity
tags: [git, merge, gitattributes, resolve, update, concurrency, markdown]
milestone: v4.9.0-stop-gate-resilience-and-runtime-stabilization
blocked_by: []
related: [git-merge-drivers-and-setup, docs-semantic-conflict-resolution]
plan_status: approved
---

# Preventive Git Auto-Merge Protection, Update Propagation, and Stage-Aware Semantic Conflict Resolution

## Problem

When multiple agents or developers collaborate across Git branches, Git's default 3-way line-based merge engine (`git merge-file`) silently mangles Markdown files, documentation, and Along metadata whenever concurrent edits touch non-overlapping lines.
Specifically:
1. **Silent Mangling Risk**: Standard Git merge line-heuristics easily corrupt YAML front-matter, Markdown tables, task checklists, and architectural docs without triggering a conflict if the lines did not overlap.
2. **Missing Safety Net on Unconfigured Clones**: The existing `along-projection` and `along-frontmatter` custom drivers rely on local `.git/config` registration via `along git setup`. When a repository is freshly cloned or an agent executes `git pull` without local drivers registered, Git silently falls back to standard 3-way line merge.
3. **Docs and Instructions Unprotected**: `docs/`, `AGENTS.md`, `CLAUDE.md`, and `.along/rules/` currently have no merge protection (`*.md text eol=lf`), allowing silent auto-merge or messy conflict markers.
4. **Existing Resolve Engine is Marker-Centric**: `along resolve` currently requires textual conflict markers (`<<<<<<< HEAD`) inside working tree files. When Git stops merge on `-merge` (binary merge attribute), it leaves clean index stages (`:1:`, `:2:`, `:3:`) and leaves `ours` in the working tree without text markers.
5. **Propagation Gap Across Repositories**: Existing repositories upgraded via `along update` need to automatically receive these protective `.gitattributes` and merge configurations without manual intervention.

## Requirements

- REQ-1: **Preventive Git Auto-Merge Lock (`.gitattributes`)**:
  - `scripts/alongkit/merge.py` MUST configure `text -merge` on sensitive markdown paths (`**/.along/**/*.md`, `**/docs/**/*.md`, `AGENTS.md`, `CLAUDE.md`, `.along/PROTOCOL.md`) so Git refuses automatic line-based merge on any concurrent modifications.
  - Projections (`ISSUES.md`, `CONSTRAINTS.md`, `INDEX.md`, `DECISIONS.md`) MUST continue using `merge=along-projection` when registered, with `-merge` as baseline fallback.
- REQ-2: **Automatic Rollout in `along update` and `along init`**:
  - `scripts/along_update.py` and `scripts/along_init.py` MUST apply updated `.gitattributes` and `.git/config` merge settings automatically to target repositories.
  - `along doctor` MUST verify that sensitive markdown paths are covered by `-merge` protection and warn if `.gitattributes` or driver registrations are missing or stale.
- REQ-3: **Stage-Aware Conflict Resolution (`along resolve`)**:
  - `scripts/alongkit/resolve.py` and `along resolve` MUST support resolving unmerged files directly from Git index stages (`:1:` base, `:2:` ours, `:3:` theirs) when files have no textual conflict markers due to `-merge`.
  - For front-matter: parse and reconcile structured fields (status rank, latest timestamps, set union of lists).
  - For markdown body: structural reconciliation of sections, checklists, and tables, with fallback/delegation to agent harness when ambiguous.
- REQ-4: **Safe Git Sync / Merge Workflow**:
  - CLI workflow (e.g. `along git sync` / `along git resolve`) MUST handle post-merge reconciliation: deterministic projection recompilation for derived boards, semantic resolution for entities/docs, and quality gate verification (`along lint`, `along sanitize`).

## Acceptance Criteria

- [ ] `along git setup` renders managed `.gitattributes` with `text -merge` protection for `.along/`, `docs/`, and root instruction files.
- [ ] Concurrent edits to protected markdown files on separate branches result in clean Git stop (`CONFLICT (content)`) without silent line merges and without corrupting working tree files with text markers.
- [ ] `along update` automatically applies and updates the managed `.gitattributes` block in existing repositories.
- [ ] `along doctor` reports `[OK]` when `-merge` protection is active and `[WARN]` when missing.
- [ ] `along resolve` cleanly detects unmerged files from Git index stages (`:1:`, `:2:`, `:3:`) and produces valid resolved markdown matching Along formatting and typography rules.
- [ ] Automated tests cover `.gitattributes` rendering, `along update` git setup execution, stage extraction, and conflict resolution.
