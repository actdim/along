---
protocol: along
protocol_version: "3.9.4"
slug: oneliner-installer
type: feat
status: done
priority: high
created: 2026-09-21
updated: 2026-09-21
completed: 2026-09-21
agent: antigravity
tags: [installer, bootstrap, powershell, bash, cli, distribution]
milestone: v4.0.0-runtime-gates-and-worktree-isolation
blocked_by: []
related: []
---

# Cross-Platform One-Liner Self-Bootstrapping Installer and Update Harmonization

## Problem
Installing Along currently requires users to manually clone the git repository (`git clone https://github.com/actdim/along.git && cd along && powershell install.ps1`). If `install.ps1` or `install.sh` is invoked standalone or piped via `irm ... | iex` / `curl ... | bash`, execution immediately fails because the scripts expect `$PSScriptRoot/skills` or `$SCRIPT_DIR/skills` to exist on the local disk.

Meanwhile, `scripts/along_update.py` (`update_global_from_git`) already caches and pulls from GitHub into `~/.cache/actdim-along/repo`.

## Requirements
- Support self-bootstrapping one-liner installations on Windows (`irm ... | iex`) and Linux/macOS (`curl ... | bash`).
- Retain local mode when executed within a repository checkout containing `skills/`.
- If `skills/` is missing, download/clone repository into `~/.cache/actdim-along/repo` and delegate installation.
- Support archive download fallback (zip/tar.gz) if `git` is not installed on the system.
- Harmonize cache paths and behavior with `scripts/along_update.py`.
- Add hermetic automated tests in `tests/test_installers.py`.
- Update Quickstart documentation in `README.md` and `docs/topic--setup-and-workflow.md`.
