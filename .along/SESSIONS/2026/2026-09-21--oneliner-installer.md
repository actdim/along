---
protocol: along
slug: oneliner-installer
date: 2026-09-21
agent: antigravity
summary: "Implemented cross-platform one-liner self-bootstrapping installer, archive fallback, update harmonization, and hermetic tests"
milestone: v4.0.0-runtime-gates-and-worktree-isolation
issues_advanced: []
issues_completed: [feat--oneliner-installer]
decisions: [ADR-2026-09-21--oneliner-installer-bootstrap-over-binary-dist]
risks_logged: []
spikes_conducted: []
branch: main
commit: unknown
---

# Session Log: 2026-09-21 - Cross-Platform One-Liner Installer & Update Harmonization

## 1. Objectives & Context

Implementation of `[feat--oneliner-installer]` under milestone `v4.0.0-runtime-gates-and-worktree-isolation`:
- Remove the requirement for manual `git clone` during initial installation.
- Implement cross-platform one-liner commands for Windows (`irm ... | iex`) and Linux/macOS (`curl ... | bash`).
- Provide automated repository bootstrapping into `~/.cache/actdim-along/repo` with archive fallback (zip/tar.gz) if `git` is absent.
- Harmonize installation cache and fallback logic with `scripts/along_update.py`.
- Add hermetic automated test coverage in `tests/test_installers.py`.
- Record architectural decision in `ADR-2026-09-21--oneliner-installer-bootstrap-over-binary-dist.md`.
- Update Quickstart documentation across `README.md` and `docs/topic--setup-and-workflow.md`.

## 2. Key Architecture & Changes

1. **PowerShell Self-Bootstrapping (`install.ps1`, `install.bat`)**:
   - Added `-CacheDir` parameter defaulting to `$HOME/.cache/actdim-along/repo`.
   - Added local checkout detection (`skills/` and `scripts/`).
   - If local skills are absent, automatically clones or fetches the shallow repository via `git`.
   - If `git` is absent or clone fails, downloads the GitHub zip archive via `Invoke-WebRequest` and extracts it into the cache directory.
   - Forwards all user parameters (`-Target`, `-Symlink`, home overrides) to the bootstrapped script and safely propagates exit codes.
   - Enhanced `install.bat` to fallback to the one-liner command if `install.ps1` is missing.

2. **Bash Self-Bootstrapping (`install.sh`)**:
   - Added `--cache-dir` parameter and matching `ALONG_CACHE_DIR` environment override.
   - Detects standalone or piped execution (`curl ... | bash`).
   - Clones shallow repository into `$HOME/.cache/actdim-along/repo` or downloads the tar.gz archive via `curl`/`tar`.
   - Delegates execution to the cached script via `exec bash "$TARGET_SCRIPT" "$@"` with argument forwarding.

3. **Update Harmonization (`scripts/along_update.py`)**:
   - Added `_download_and_extract_archive` fallback in `update_global_from_git` using Python's standard `urllib.request` and `zipfile` modules.
   - Ensures Along updates succeed even in restricted environments without `git`.

4. **Hermetic Test Suite (`tests/test_installers.py`)**:
   - Added `TestInstallerSelfBootstrap` class.
   - Verified that running standalone `install.ps1` and `install.sh` in isolated directories without `skills/` correctly bootstraps and installs all planned files.

5. **Documentation**:
   - Updated `README.md` Quickstart with the official one-liner commands.
   - Updated `docs/topic--setup-and-workflow.md` with standalone bootstrap details.

## 3. Verification & Invariants

- Ran full test suite via `python .along/scripts/test.py`: 512 tests passed, 0 failures.
- Ran typography check via `python scripts/along_exec.py sanitize --check`: 497 files clean, 0 banned characters.
- Recompiled projections: `ISSUES.md`, `DECISIONS.md`, `CONSTRAINTS.md`, `docs/INDEX.md`.
