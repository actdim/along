---
protocol: along
protocol_version: "4.3.0"
slug: suppress-ai-coauthor-attribution
type: feat
status: done
priority: high
created: 2026-09-29
updated: 2026-09-29
completed: 2026-09-29
agent: claude-code
tags: [gates, git, runtime-config, attribution]
milestone: v4.4.0-multi-user-merge-automation
blocked_by: []
related: [feat--git-level-gate-enforcement]
---

# Suppress AI co-author attribution in commits made by agent runtimes

## Problem

Agent runtimes append `Co-Authored-By:` trailers to the commits they create (Claude Code: `Co-Authored-By: Claude ... <noreply@anthropic.com>`, Antigravity: `Co-Authored-By: Antigravity (Gemini) <noreply@google.com>`). GitHub resolves the trailer email to an account and lists the AI vendor as a repository contributor. On this repository 10 commits carried such trailers; removing them required a full history rewrite (`git filter-repo`) and a force-push of `main` and all tags on 2026-09-29.

## Requirements

- REQ-1: `along hook install --runtime claude` (called by the installers and `/along-init`) also writes the Claude Code attribution settings into `settings.json`: `attribution.commit = ""` and the legacy `includeCoAuthoredBy = false` (read only when `attribution` is absent). `attribution.pr` and other keys are preserved. `--runtime cursor --global` sets `attribution.attributeCommitsToAgent = false` in `~/.cursor/cli-config.json`. Codex and Antigravity document no such key.
- REQ-2: Runtime-agnostic PreToolUse gate `commit_no_ai_coauthor` blocks `git commit` commands whose message carries an AI co-author trailer. Human co-authors stay allowed.
- REQ-3: `/along-commit` strips AI co-author trailers from the final message before committing.
- REQ-4: Opt-out: `.along/config.json` `{"commits": {"allow_ai_coauthor": true}}` disables REQ-1 writes, the REQ-2 gate and REQ-3 stripping.
- REQ-6: Reconcile on every install and update: `reconcile_attribution` (CLI `along hook attribution`) writes only the attribution keys for runtime homes that already exist. `install.ps1` / `install.sh` call it for Cursor (new `-CursorHome` / `--cursor-home`); `/along-update` calls it on every run, also when the install is up to date (`--no-hooks` skips it).
- REQ-5: Protocol rule with `[gate: commit-no-ai-coauthor]` anchor in `AGENTS.md` managed block and `skills/along-init/protocol.md`; `docs/topic--runtime-hooks-and-gates.md` documents the gate and the settings.

## Execution Mode

Direct. Additive change inside one subsystem (hooks config, gate catalogue, commit engine); no core engine refactor.

## Acceptance Criteria

- [x] `install_claude_hooks` writes attribution keys idempotently and keeps foreign keys
- [x] Gate denies `git commit -m "... Co-Authored-By: Claude <noreply@anthropic.com>"` and allows a human co-author
- [x] `/along-commit` strips AI co-author trailers before `format_commit_message`
- [x] `/along-update` and the installers apply the settings even when Along is already up to date
- [x] Automated tests passing (`tests/test_ai_coauthor_attribution.py`, full suite 723 OK)
