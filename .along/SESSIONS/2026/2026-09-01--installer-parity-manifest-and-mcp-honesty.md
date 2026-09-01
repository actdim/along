---
protocol: along
date: 2026-09-01
slug: installer-parity-manifest-and-mcp-honesty
agent: claude-code
branch: main
commit: pending
summary: "Installers copy, engines decide, a manifest remembers: parity by artifact, no directory deletion, MCP written only where verified, and an uninstall"
milestone: v3.0.0-global-quality-revision
issues_advanced: [protocol-quality-audit-remediation]
issues_completed: [installer-parity-and-destructive-rules-overwrite]
decisions: ["ADR-2026-09-01--installers-never-delete-what-they-did-not-write"]
risks_logged: []
spikes_conducted: []
---

# Session: Installer parity, the install manifest, and MCP honesty

## Summary

Closed `[bug--installer-parity-and-destructive-rules-overwrite]`, the fourth and last of
the destructive engines in step 2 of the audit epic. The installers keep doing the file
copying, because they have to work on a machine with no Python, and every decision they
used to make inline is now an engine over `alongkit.install`.

## Work Completed

- **`scripts/alongkit/install.py`** (new): the installed layout (`planned_files`), the
  install manifest (`sync_manifest`, `uninstall`, content hashes, link-aware recording),
  and the per-provider MCP contracts (`mcp_target`, `register_mcp`).
- **`scripts/configure_mcp.py`** (new engine): replaces the 24-line Python program both
  installers carried inside a shell string passed to `python -c`. Registers only where the
  contract is verified (Claude Code's `mcpServers` in `~/.claude.json`), reports the other
  three with their real path and snippet, and refuses to rewrite a file it cannot parse.
- **`scripts/install_manifest.py`** (new engine): `sync`, `show`, `uninstall` over
  `~/.along/install-manifest.json`.
- **`install.ps1`**: no longer deletes `~/.claude/rules`; `mklink /J` quoted once rather
  than twice; `-AlongHome`, `-Uninstall`, `-IncludeUnverifiedMcp`; a Python probe that
  rejects the Microsoft Store stub; MCP and manifest delegated to the engines.
- **`install.sh`**: `--along-home=`, `--uninstall`, `--include-unverified-mcp`, the same
  delegation and the same Python probe; no `mapfile` (macOS ships bash 3.2).
- **`tests/test_installers.py`** (new, 17 tests): runs both real installers against a
  throwaway checkout whose path contains a space, into throwaway homes, and asserts disk
  equals `planned_files` in both directions; plants a user rule file and proves it
  survives an install and an uninstall; covers manifest pruning scope, MCP contracts, and
  a linked install that must not be followed on uninstall.
- **`tests/hermetic.py`**: `make_installer_checkout()` / `installer_checkout()`.
- Docs: `docs/topic--setup-and-workflow.md` (what an install writes, uninstall, MCP
  honesty, and the `./install.sh all` syntax error), `docs/topic--architecture.md`,
  `README.md`, `AGENTS.md`, `install.bat`, `pyproject.toml` engine manifest.

## Code Review & Impact

- **Blast radius**: `along_update.py` invokes both installers with default arguments and
  is unaffected; `along_version_bump.py` no longer invokes them at all. The two new
  engines are additive. `alongkit.install` is imported by nothing else. The `code-review-graph`
  MCP server was unavailable this session (connection closed), so the impact radius was
  established by grep over `install.ps1` / `install.sh` / `mcp_config` references rather
  than by AST graph.
- **Defect found while implementing**: `os.path.islink` reports False for a Windows
  junction, which is what the symlink fallback creates. Recording the files behind it
  would have made an uninstall delete the source checkout through the link. Fixed by
  `install.is_link` (reparse-point attribute) and covered by a test that counts the
  checkout's files after uninstalling a linked install.
- **Second defect**: the previous MCP writer started from `{}` whenever the existing JSON
  failed to parse, and then wrote the file - a path that could replace a user's whole
  `~/.claude.json`. It now refuses and reports.
- **Deliberate deviations from the issue text**, both recorded in the issue's
  implementation table: rules stay at `<home>/rules/` rather than moving to a namespaced
  subdirectory (the manifest already removes the need, and relocating breaks every
  existing reference), and a second install rewrites identical bytes rather than skipping
  them (hash-comparing in both shells would put the layout logic in three places), with
  "unchanged" proven by content and by the report.
- **Suite**: 209 -> 226 tests, all passing under `uv run python -m unittest discover
  tests -q`. `tests/test_zz_hermetic_suite.py` confirms the working tree stayed clean.
