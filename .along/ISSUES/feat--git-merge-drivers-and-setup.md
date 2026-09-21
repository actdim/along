---
protocol: along
protocol_version: "3.8.0"
slug: git-merge-drivers-and-setup
type: feat
status: open
priority: high
created: 2026-09-21
updated: 2026-09-21
agent: antigravity
tags: [git, merge, drivers, concurrency, projections, frontmatter, cli]
milestone: v4.5.0-multi-user-merge-automation
blocked_by: []
blocks: [feat--docs-semantic-conflict-resolution]
related: [concurrency-projections-and-context-deprecation]
---

# Deterministic Custom Git Merge Drivers for Projections & Front-Matter Metadata

## Summary

In multi-user or multi-agent environments, concurrent Git branches often collide on derived projections (`.along/ISSUES.md`, `docs/INDEX.md`, `.along/CONSTRAINTS.md`) and atomic front-matter metadata files (`.along/ISSUES/*.md`, `.along/DECISIONS/*.md`).
While Along already specifies the "Zero-Manual-Merge Rule", Git default 3-way merge interrupts `git pull` or `git merge` when projection line numbers conflict.

This issue implements deterministic Custom Git Merge Drivers:
1. `along-projection-driver`: Always accepts either side and triggers immediate recompilation (`along issue sync`, `along kb sync`, `along decision sync`), guaranteeing 100% conflict-free Git pulls on projection files.
2. `along-frontmatter-driver`: Performs semantic 3-way YAML dictionary merge for atomic entity files, reconciling non-overlapping properties and selecting the latest state for scalars.
3. `along git setup` CLI command: Automatically configures `.git/config` merge driver definitions and registers corresponding file patterns in `.gitattributes`.
4. Installer integration: Embeds automatic `along git setup` into `along-init` and `along update`.

## Detailed Implementation Plan

### Stage 1.1: Merge Driver Engines (`scripts/alongkit/merge.py` & `scripts/along_merge_driver.py`)
- Implement `ProjectionMergeDriver`:
  - Receives `%O` (ancestor), `%A` (current/ours), `%B` (other/theirs), `%P` (pathname).
  - Copies `%A` to `%A` as baseline.
  - Identifies target projection type from pathname (`ISSUES.md` -> `entities.recompile_issues_board`, `INDEX.md` -> `along_kb_sync`, `CONSTRAINTS.md` -> `decision sync`).
  - Executes in-process projection sync directly on `%A`.
  - Exits with returncode 0.
- Implement `FrontmatterMergeDriver`:
  - Parses YAML front-matter of `%O`, `%A`, `%B` using `alongkit.frontmatter`.
  - Merges dictionary keys:
    - Lists (`tags`, `depends_on`, `related`): Set union preserving order.
    - Status/Priority: Resolves to most advanced lifecycle state (`done` > `in-progress` > `backlog`/`open`).
    - Scalar updates: Resolves towards `%B` if updated timestamp is newer, else retains `%A`.
  - Merges markdown bodies using clean 3-way text merge or section concatenation.
  - Writes resolved content to `%A` and exits with returncode 0.

### Stage 1.2: Repository Configuration Command (`along git setup`)
- Add `git setup` subcommand to `scripts/along_exec.py` and `alongkit/cli.py`:
  - Inspects repo `.git/config` using `alongkit.proc`.
  - Registers driver commands:
    - `git config merge.along-projection.name "Along projection recompiler merge driver"`
    - `git config merge.along-projection.driver "python scripts/along_merge_driver.py projection %O %A %B %P"`
    - `git config merge.along-frontmatter.name "Along YAML frontmatter 3-way merge driver"`
    - `git config merge.along-frontmatter.driver "python scripts/along_merge_driver.py frontmatter %O %A %B %P"`
  - Ensures `.gitattributes` contains bindings:
    - `.along/ISSUES.md merge=along-projection`
    - `docs/INDEX.md merge=along-projection`
    - `.along/CONSTRAINTS.md merge=along-projection`
    - `.along/DECISIONS.md merge=along-projection`
    - `.along/ISSUES/**/*.md merge=along-frontmatter`
    - `.along/DECISIONS/**/*.md merge=along-frontmatter`
- Provide `--uninstall` flag to cleanly remove driver registrations.

### Stage 1.3: Integration with `along-init` and `along-update`
- Update `scripts/along_update.py` and `skills/along-init/protocol.md` to trigger `along git setup` during initialization or protocol upgrade.
- Verify idempotency: repeated runs should not duplicate entries in `.git/config` or `.gitattributes`.

### Stage 1.4: Hermetic Test Suite (`tests/test_merge_driver.py`)
- Test projection driver on synthetic concurrent branches with conflicting `ISSUES.md`.
- Test front-matter driver with non-overlapping and overlapping YAML property mutations.
- Verify fallback behavior when external dependencies are missing.

## Acceptance Criteria
- [ ] `scripts/along_merge_driver.py` implemented and supports `projection` and `frontmatter` modes.
- [ ] `along git setup` registers merge drivers in `.git/config` and updates `.gitattributes`.
- [ ] Parallel branch merges modifying `.along/ISSUES.md` resolve automatically with zero Git conflict markers.
- [ ] Front-matter 3-way merge successfully resolves concurrent tag additions and status updates.
- [ ] Hermetic unit tests in `tests/test_merge_driver.py` pass cleanly.
