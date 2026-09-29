---
protocol: along
protocol_version: "4.3.0"
date: 2026-09-29
slug: ai-coauthor-history-rewrite-and-gate
agent: claude-code
branch: main
commit: c4d149c
summary: Removed AI Co-Authored-By trailers from the whole history (filter-repo, force-push main + tags); added runtime attribution settings, commit_no_ai_coauthor gate and /along-commit stripping
issues_advanced: []
issues_completed: [feat--suppress-ai-coauthor-attribution]
decisions: []
risks_logged: []
spikes_conducted: []
milestone: v2.0.0-along-transition
---

# Session: AI co-author history rewrite and gate

## Summary
GitHub listed Claude Code as a repository contributor because 9 commits (2026-09-01) carried `Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>`; one more carried an Antigravity (Gemini) trailer. History was rewritten to drop every `Co-Authored-By:` trailer, and Along now keeps AI trailers out of new commits.

## Work Completed
- History rewrite: backup bundle first, then `git filter-repo --message-callback` removing `Co-Authored-By:` lines. Verified before pushing: all 236 commits keep identical trees, authors, committers and dates; all 44 tags point at the same trees; 0 trailers left. Force-pushed `main` (`--force-with-lease` on `c9a1da3`) and all tags. 109 commits before `e9cca29` kept their hashes; 127 got new ones.
- Remapped 7 stale commit-hash references in `.along/SESSIONS/` and `.along/ISSUES/done/` using `.git/filter-repo/commit-map`.
- `feat--suppress-ai-coauthor-attribution`: new `scripts/alongkit/attribution.py`; `install_claude_hooks` writes `attribution.commit = ""` + legacy `includeCoAuthoredBy = false`; global Cursor install writes `attribution.attributeCommitsToAgent = false` to `cli-config.json`; gate `commit_no_ai_coauthor` (`predicates.check_ai_coauthor`, command line and `-F` file); `/along-commit` strips AI trailers; opt-out `.along/config.json` `commits.allow_ai_coauthor`.
- Follow-up (REQ-6): `reconcile_attribution` + `along hook attribution`; `/along-update` reconciles on every run (was: only when a newer release got installed); installers reconcile Cursor via new `-CursorHome` / `--cursor-home`.
- Protocol rule `[gate: commit-no-ai-coauthor]` in `AGENTS.md` and `skills/along-init/protocol.md`; docs updated (runtime hooks 2.7, declarative gate list).

## Code Review & Blast Radius
- Tests: `python .along/scripts/test.py` - 723 tests OK; real `~/.claude/settings.json` and `~/.cursor/cli-config.json` untouched by the suite. `along hook verify`: PASSED. Typography: 631 files, no banned characters. KB sync: 385 links verified.
- Blast radius: `install_claude_hooks` / `install_cursor_hooks` gain additive key writes only (foreign keys preserved, opt-out respected). The new gate fires only on `git commit` commands with an AI trailer. `along_commit.main` strips before formatting.
- Codex and Antigravity document no attribution key; for them the gate and `/along-commit` are the only layers.

## Follow-ups
- Existing clones of `actdim/along` must `git fetch && git reset --hard origin/main` after the force-push.
- User-level Claude/Cursor settings pick up the attribution keys on the next install or `/along-update` (or `along hook attribution`).
