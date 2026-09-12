---
protocol: along
slug: revert-git-stat-cache-workarounds
title: "Revert GIT_OPTIONAL_LOCKS and diff.autoRefreshIndex to Preserve Git Stat-Cache Integrity"
date: 2026-09-07
status: accepted
tags: [adr, architecture, decision]
---

# ADR-2026-09-07--revert-git-stat-cache-workarounds - Revert GIT_OPTIONAL_LOCKS and diff.autoRefreshIndex to Preserve Git Stat-Cache Integrity

- Date: 2026-09-07
- Status: accepted
- Context:
  1. ADR-2026-09-06--windows-git-concurrency-and-index-lock-mitigation introduced `GIT_OPTIONAL_LOCKS: "0"` in `alongkit.proc` and recommended setting `diff.autoRefreshIndex false` and global `GIT_OPTIONAL_LOCKS=0`.
  2. In practice, `GIT_OPTIONAL_LOCKS=0` directly disables Git's stat-cache index refresh on Windows. Because Git is forbidden from acquiring optional index locks during `git status` or `git diff`, any file whose disk `mtime` changes cannot update the index stat cache. Git therefore flags clean files as modified (`" M"`), causing hermetic test suites and working tree snapshots to fail with false dirty states.
  3. Furthermore, disabling optional read locks did not prevent index corruption (`fatal: .git/index: index file smaller than expected`), because index truncations are caused by external processes (Windows Defender, search indexers) locking `.git/index` during mandatory write operations (`git add`, `git commit`, `git checkout`).
- Decision:
  1. **Revert Child Environment Injection**: Remove `"GIT_OPTIONAL_LOCKS": "0"` from `scripts/alongkit/proc.py` `UTF8_CHILD_ENV`.
  2. **Remove User and Global Config Recommendations**: Remove recommendations for `GIT_OPTIONAL_LOCKS=0` and `diff.autoRefreshIndex false` from `install.ps1`, `skills/along-init/SKILL.md`, and `docs/topic--setup-and-workflow.md`.
  3. **Reset Editor Overrides**: Clear `terminal.integrated.env.windows` from `.vscode/settings.json`.
  4. **Preserve Root-Cause Mitigations**: Retain the 0-byte index self-healing logic (`git read-tree HEAD`) in `alongkit.proc` for automatic recovery, and document antivirus/search indexing exclusions as the genuine preventative measure on Windows NTFS.
- Consequences: Restores standard Git stat-cache behavior on Windows. Clean repositories remain clean without phantom `" M"` diffs. Subprocesses and developer shell commands operate with native Git performance and accurate index metadata.
