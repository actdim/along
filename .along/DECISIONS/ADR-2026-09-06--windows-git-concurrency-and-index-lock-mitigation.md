---
protocol: along
slug: windows-git-concurrency-and-index-lock-mitigation
title: "Windows Git Concurrency Hardening: Disabling Optional Locks and Preload Races"
date: 2026-09-06
status: superseded
superseded_by: revert-git-stat-cache-workarounds
tags: [adr, architecture, decision]
---

# ADR-2026-09-06--windows-git-concurrency-and-index-lock-mitigation - Windows Git Concurrency Hardening: Disabling Optional Locks and Preload Races

- Date: 2026-09-06
- Status: superseded by ADR-2026-09-07--revert-git-stat-cache-workarounds
- Context: Low-latency LLM agents (such as Gemini 3.8 Flash) execute file modifications and commands at high frequency (< 500ms intervals). On Windows NTFS, atomic file replacement (`ReplaceFileW`) conflicts with background watchers (VS Code `vscode.git`, GitExtensions) running `git status` or `git diff`. By default, Git attempts to update cached stat data in `.git/index` by creating `.git/index.lock` and invoking `ReplaceFileW`. On NTFS, if another process holds `.git/index` open without `FILE_SHARE_DELETE`, `ReplaceFileW` fails or is interrupted, leaving `.git/index` truncated to 0 bytes (`fatal: .git/index: index file smaller than expected`).
- Decision:
  1. **Disable Optional Git Write Locks**: Set `GIT_OPTIONAL_LOCKS: "0"` in `alongkit.proc.UTF8_CHILD_ENV` for all subprocesses spawned by Along, and configure `GIT_OPTIONAL_LOCKS=0` at the Windows User environment level in `install.ps1`. This instructs `git status` and `git diff` to skip index stat cache refreshes and avoid acquiring write locks on `.git/index`.
  2. **Disable Index Preloading**: Configure `core.preloadindex = false` on Windows to eliminate multi-threaded stat cache lock races on NTFS.
  3. **Automatic 0-Byte Index Self-Healing**: Implement zero-byte `.git/index` detection and recovery in `alongkit.proc.git` (`git read-tree HEAD`) so that accidental index corruption is repaired automatically without human intervention.
  4. **Document User Recommendations**: Provide explicit guidance for Windows developers running AI coding agents in `docs/topic--setup-and-workflow.md`.
- Consequences: Eliminates `.git/index` 0-byte corruptions and lock collisions on Windows NTFS during rapid agent execution and batch change acceptance. Stat cache overhead is negligible (sub-millisecond) for repositories under 50,000 files. Mandatory Git write locks (`git add`, `git commit`, `git merge`, `git checkout`) remain 100% operational.
