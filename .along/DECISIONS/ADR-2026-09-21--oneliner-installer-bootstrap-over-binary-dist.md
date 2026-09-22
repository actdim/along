---
protocol: along
slug: oneliner-installer-bootstrap-over-binary-dist
title: "One-Liner Self-Bootstrapping Installer and Update Harmonization Over Binary Distribution"
date: 2026-09-21
status: accepted
tags: [adr, architecture, decision, installer, distribution]
---

# ADR-2026-09-21--oneliner-installer-bootstrap-over-binary-dist - One-Liner Self-Bootstrapping Installer and Update Harmonization Over Binary Distribution

- Date: 2026-09-21
- Status: accepted
- Context: Prior to this decision, installing Along required users to manually clone the Git repository (`git clone https://github.com/actdim/along.git && cd along && install.ps1`). Executing `install.ps1` or `install.sh` standalone or piped (`irm ... | iex` / `curl ... | bash`) failed immediately because both scripts expected `skills/` and `scripts/` to exist relative to the script root. Proposals to package Along as a traditional compiled binary installer (`.exe` / Inno Setup / NSIS) were evaluated and rejected due to: (1) Windows SmartScreen and antivirus false positives for unsigned executables, (2) platform fragmentation (leaving Unix users on separate scripts), (3) the fact that Along is an agent skill protocol and Python engine suite rather than a standalone GUI application, meaning an exe installer does not eliminate the runtime Python environment requirements for executing skills.
- Decision:
  1. **Self-Bootstrapping Entrypoints**: Both `install.ps1` and `install.sh` now support dual execution modes. When executed inside a local repository checkout (presence of `skills/` and `scripts/`), they run in local development mode without network operations. When executed standalone or piped without local skills, they automatically bootstrap the repository into `~/.cache/actdim-along/repo`.
  2. **Shallow Clone with Archive Fallback**: The bootstrap mechanism prefers a shallow `git clone --depth 1` (or `git fetch` if `.git` exists), ensuring subsequent `/along-update` commands can pull changes efficiently. If `git` is absent or the operation fails, it falls back to downloading the repository archive from GitHub (zip on Windows via `Expand-Archive`, tar.gz on Unix via `tar`) into the cache.
  3. **Harmonized Cache with `along_update.py`**: The installer bootstrap and `scripts/along_update.py` (`update_global_from_git`) share the exact same cache path (`~/.cache/actdim-along/repo`) and fallback mechanisms.
  4. **Transparent Delegation**: Once bootstrapped, the installer delegates to the cached `install.ps1` or `install.sh` script, forwarding all user parameters (`-Target`, `-Symlink`, home directory overrides, etc.) and propagating exit codes cleanly.
  5. **Hermetic Test Coverage**: `tests/test_installers.py` verifies both local mode and standalone bootstrap mode against throwaway checkouts and homes without touching live environments.
- Consequences: Users can install Along across all providers with a single command (`irm ... | iex` on Windows, `curl ... | bash` on Unix) without needing manual git clones or facing unsigned executable security warnings. Local development workflows and hermetic testing remain completely intact.
