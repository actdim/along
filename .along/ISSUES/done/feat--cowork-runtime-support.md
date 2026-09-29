---
protocol: along
protocol_version: "4.2.0"
slug: cowork-runtime-support
type: feat
status: done
completed: 2026-09-27
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

- [x] Entities created from Cowork carry `agent: cowork` without explicit flags
- [x] Capability matrix published in docs and linked from README
- [x] `along doctor` prints the runtime enforcement level
- [x] Automated tests passing

## Resolution

- REQ-1: new `alongkit/runtime.py`; `runtime.is_cowork_env()` recognises `ALONG_RUNTIME=cowork` or `CLAUDE_CODE_HOST_HTTP_PROXY_PORT` with a `/sessions/` home (markers observed in the Cowork VM on 2026-09-27; heuristic, overridable). `entities.detect_agent()` checks it before the Claude Code markers and returns `cowork`.
- REQ-2: `docs/topic--runtime-hooks-and-gates.md` section 5 "Runtime Capability Matrix" (skills, runtime hooks, enforcement per runtime) and "Working from Claude Cowork"; README knowledge-base table links to it.
- REQ-3: one rule added to the protocol (`skills/along-init/protocol.md` and the managed block in `AGENTS.md`): in runtimes without Along hooks the agent self-applies gate-tagged rules and uses the `along` CLI.
- REQ-4: `along doctor` gained a Runtime section (`_doctor_runtime_checks`): runtime, enforcement level (mechanical only when Along hooks are registered for that runtime), Python floor, stale `.git/index.lock` (the Cowork no-delete symptom), cross-OS/VM mount (`/proc/mounts` fs type or `core.symlinks=false`). Delete permission is not probed with a temp file, because a probe that cannot be deleted would itself be left behind.
- REQ-5: the Cowork setup guide is part of the docs section above.
- Not changed, by decision: `tests/test_zz_hermetic_suite.py` still runs a plain `git status`, which leaves `index.lock` in a no-delete Cowork mount. Adding `--no-optional-locks` would contradict `ADR-2026-09-07--revert-git-stat-cache-workarounds` (false dirty states); the doctor warning and the setup guide cover it.
- Tests: `tests/test_runtime_detection.py` (9 tests). Verified live in the Cowork VM: `along doctor` reports `Runtime: cowork`, `advisory`, and the fuse mount. Full suite on Python 3.10.12, 698 tests OK (3 skipped).
- Follow-up found: `docs/topic--runtime-hooks-and-gates.md` invariant 1 ("Zero Git Hooks") conflicts with `feat--git-level-gate-enforcement`; that issue needs an ADR before implementation.
