---
protocol: along
protocol_version: "3.7.0"
slug: pi-harness-support
type: feat
status: open
priority: high
created: 2026-09-18
updated: 2026-09-18
agent: antigravity
tags: [pi, providers, installer, runtime, hooks, documentation]
milestone: v5.0.0-external-harness-expansion
blocked_by: []
related: [feat--runtime-enforcement-of-prose-rules, feat--deepseek-harness-bridge]
---

# Pi Coding Agent Runtime & Skill Integration

## Problem
The Pi coding agent (`@earendil-works/pi-coding-agent`, created by Mario Zechner and maintained by Earendil Works) has established itself as an open-source, hackable agent harness. While Pi natively searches for `AGENTS.md` and supports the Agent Skills specification (`SKILL.md`), Along does not yet recognize Pi as a supported provider:
1. Installer and manifest gaps:
   - `scripts/alongkit/install.py` does not include `pi` in `PROVIDERS` or `FOLDER_PROVIDERS`.
   - `install.ps1` and `install.sh` do not install skills into Pi's global directory (`~/.pi/skills/` or equivalent).
   - `scripts/install_manifest.py` does not track Pi skill files, preventing transactional verification and clean uninstallation.
2. Hook and mechanical gate integration:
   - Pi uses in-process TypeScript hooks and extensions rather than the shell-based `hooks.json` format used by Claude Code and Codex.
   - Along's mechanical gates (`TypographyGate`, `ProjectionProtectionGate`, `CliSafetyGate`) need a verified execution path in Pi (such as running sessions via `along run pi` or designing a lightweight TypeScript bridge extension).
3. Documentation gaps:
   - Pi is not documented in `docs/topic--runtime-hooks-and-gates.md`, `docs/topic--cli-reference.md`, or `README.md`.

## Requirements
1. Provider and Installer Registration:
   - Define `Homes.pi` pointing to `~/.pi` (or user override) in `scripts/alongkit/install.py`.
   - Register `pi` in `alongkit.install.PROVIDERS` and `alongkit.install.FOLDER_PROVIDERS`.
   - Update `install.ps1` and `install.sh` to support `-Target pi` (and include `pi` in `all`).
   - Ensure `scripts/install_manifest.py` records installed Pi skill files in `install-manifest.json`.
   - Add installer parity tests in `tests/test_installers.py`.
2. Runtime Gate & Workflow Design:
   - Verify native `AGENTS.md` discovery in Pi project sessions.
   - Document and test gate enforcement via Along CLI execution (`along run pi`).
   - Define specification for an optional TypeScript bridge extension to intercept Pi tool calls and evaluate them against `along_hook.py`.
3. Documentation & Knowledge Base:
   - Document Pi setup, skill discovery, and gate enforcement in `docs/topic--runtime-hooks-and-gates.md` and `docs/topic--setup-and-workflow.md`.
   - Update `docs/INDEX.md` and `README.md`.

## Acceptance Criteria
- [ ] `pi` is registered in `alongkit.install.PROVIDERS` and `FOLDER_PROVIDERS`.
- [ ] `install.ps1 -Target pi` and `install.sh --target pi` successfully deploy `along-*` skills to Pi's skill path.
- [ ] `install-manifest.json` tracks Pi artifacts and supports clean `--uninstall`.
- [ ] Tests in `tests/test_installers.py` pass with zero parity drift.
- [ ] Pi workflow and gate enforcement paths are documented in `docs/`.
- [ ] `python scripts/along_kb_sync.py --check` passes without broken links.
