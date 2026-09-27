---
protocol: along
protocol_version: "4.2.0"
slug: cowork-runtime-support
type: feat
status: open
priority: medium
created: 2026-09-27
updated: 2026-09-27
agent: cowork
tags: [cowork, runtime, agent-detection, docs]
milestone: v4.3.0-developer-experience-and-runtime-resilience
blocked_by: []
related: [feat--cowork-plugin-skill-packaging, feat--git-level-gate-enforcement, bug--worktree-cross-os-mount-guard, feat--agent-runtime-adapters-claude-codex-opencode]
---

# Claude Cowork runtime support and runtime capability matrix

## Problem

Claude Cowork (Claude desktop app, agent in a cloud container plus a Linux VM on the user's machine with connected folders mounted under `$HOME/mnt/<folder>`) can follow the Along protocol by reading `AGENTS.md` and calling the engines directly, but:

- it does not load `~/.claude/skills` or `~/.claude/settings.json` from the user's machine, so `/along-*` skills are not registered and PreToolUse/Stop hooks never run;
- `entities.detect_agent()` knows no Cowork markers, so entities are stamped `agent: unknown` unless `--agent` is passed;
- the VM ships Python 3.10 by default (see `bug--py310-fstring-syntax-error`);
- the connected folder forbids deletes by default, so any git write (`status` refreshing the index, `add`, `commit`) leaves a stale `.git/index.lock` unless the user grants delete permission for the folder;
- the protocol and README do not say which runtimes provide which guarantees.

## Requirements

- REQ-1: `detect_agent()` recognises Cowork (environment markers of the Cowork VM / session; fall back to `ALONG_AGENT`) and returns `cowork`.
- REQ-2: New section in `docs/topic--runtime-hooks-and-gates.md`: runtime capability matrix (Claude Code, Cowork, Antigravity, Codex, OpenCode, Cursor, human) x (skills auto-registered, runtime hooks, git hooks, CI) with the resulting enforcement level (mechanical / git-only / advisory).
- REQ-3: `AGENTS.md` protocol block gets one line: when the runtime has no Along hooks, the agent MUST self-apply gates and use the `along` CLI instead of raw tools for tests, commits and entity changes.
- REQ-4: `along doctor` detects the runtime and reports the enforcement level, Python version compatibility, missing delete permission (stale `index.lock` risk) and a cross-OS mount.
- REQ-5: Setup guide for Cowork: connect the repo folder, grant delete permission before commits, run the CLI through `uv run --python 3.12` until the 3.10 fix ships.

## Acceptance Criteria

- [ ] Entities created from Cowork carry `agent: cowork` without explicit flags
- [ ] Capability matrix published in docs and linked from README
- [ ] `along doctor` prints the runtime enforcement level
- [ ] Automated tests passing
