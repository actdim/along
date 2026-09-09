---
protocol: along
slug: installer-junction-fallback-and-dependencies
type: bug
status: done
priority: medium
created: 2026-08-26
updated: 2026-08-26
completed: 2026-08-26
agent: git-reconstructed
tags: [git-sync, installer, dependencies]
milestone: v1.3.0-knowledge-base-and-graph
blocked_by: []
related: []
---

# Installer Junction Fallback and Dependency Management

Reconstructed from Git commits `b4d2be4`, `aef901a`, and `aa701bb` by `pavel.borodaev`.

## Changes Made
- Added Windows Junction fallback for seamless non-admin symlink creation.
- Introduced `.mise.toml` configuration and `uv` dependency checking.
- Added `-InstallDeps` flag to cross-platform installer scripts.
- Added one-liner install and Git clone instructions to `README.md` and Knowledge Base.
