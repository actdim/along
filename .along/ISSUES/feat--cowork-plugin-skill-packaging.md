---
protocol: along
protocol_version: "4.2.0"
slug: cowork-plugin-skill-packaging
type: feat
status: open
priority: medium
created: 2026-09-27
updated: 2026-09-27
agent: cowork
tags: [cowork, plugin, skills, install]
milestone: v4.5.0-structured-state-and-blackboard-engine
blocked_by: [bug--py310-fstring-syntax-error]
related: [feat--cowork-runtime-support, feat--git-level-gate-enforcement]
---

# Package along skills as a Claude Cowork plugin

## Problem

`install.ps1` / `install.sh` register the 21 `along-*` skills in provider home directories (`~/.claude/skills`, Codex, Antigravity, OpenCode). Claude Cowork does not read those directories; its skills come from installed plugins or account skills. In Cowork the agent has to discover `skills/*/SKILL.md` in the repository by itself, and `/along-*` commands are unavailable.

## Requirements

- REQ-1: Build step `along package cowork-plugin` that produces a Cowork plugin bundle from `skills/` (one skill per directory, SKILL.md front-matter adapted to the plugin format, version from `alongkit/version.py`).
- REQ-2: Skill commands inside the plugin call the repository's own engines (`uv run --python 3.12 scripts/along_exec.py ...` resolved from the connected folder), never a global install, so the plugin works with any checkout version.
- REQ-3: Investigate whether Cowork plugins can declare lifecycle hooks; if yes, ship the Along gates as plugin hooks; if not, document git/CI enforcement (`feat--git-level-gate-enforcement`) as the Cowork baseline.
- REQ-4: Installer target `-Target cowork` / `--target=cowork` produces the bundle and prints install instructions.
- REQ-5: Contract test: every skill in `skills/` is present in the bundle with matching name and description.

## Acceptance Criteria

- [ ] Plugin installs in Cowork and `/along-*` skills appear in the skill list
- [ ] Skills run against a connected repository without a global Along install
- [ ] Automated tests passing
