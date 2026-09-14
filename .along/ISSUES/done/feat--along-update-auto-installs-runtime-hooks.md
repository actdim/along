---
protocol: along
slug: along-update-auto-installs-runtime-hooks
type: feat
status: done
priority: high
created: 2026-09-14
updated: 2026-09-14
completed: 2026-09-14
agent: antigravity
tags: [hooks, update, runtime, automation, gates]
milestone: v4.0.0-runtime-gates-and-worktree-isolation
blocked_by: []
related: [docs--cli-reference-and-readme-showcase, feat--runtime-hooks-claude-code, feat--runtime-hooks-codex]
---

# Automatically Install and Update Runtime Hooks in Along Update

## 1. Problem Statement & Background
While Along v4.0.0 provides runtime lifecycle hook interception (`alongkit.hooks`, `along_hook.py`) across Claude Code, Antigravity, and OpenAI Codex, these hooks previously required a manual, out-of-band installation step via `along hook install --runtime all`.

When developers or agents executed `/along-update` (or `along update`), the protocol block in `AGENTS.md` and skill files was updated, but the runtime hook configuration files (`.claude/settings.json`, `.codex/hooks.json`, `.agents/hooks.json`) were not installed or updated. Consequently, agents continued running without active mechanical runtime gate enforcement unless the developer knew about the separate hook command.

## 2. Requirements & Invariants
1. **Default Automation**: During `along update` (and `apply_migration_to_context()`), the updater must automatically invoke the hook installer functions:
   - `install_antigravity_hooks(ctx_dir, dry_run=dry_run)`
   - `install_claude_hooks(ctx_dir, dry_run=dry_run)`
   - `install_codex_hooks(ctx_dir, dry_run=dry_run)`
2. **Simulation Safety**: When `--dry-run` or `--check-only` is passed, hook installation must strictly simulate without modifying files on disk.
3. **Opt-Out**: Provide a `--no-hooks` flag to bypass hook reconciliation if explicitly desired.
4. **Non-Destructive Merge**: Preserve existing user preferences and third-party hooks in `.claude/settings.json` and `.codex/hooks.json`.
5. **Documentation & Skills**: Update `skills/along-update/SKILL.md`, `skills/along-init/SKILL.md`, `docs/topic--skills-reference.md`, and `docs/topic--cli-reference.md`.
6. **Hermetic Test Coverage**: Verify automatic hook installation, dry-run safety, and `--no-hooks` opt-out in `tests/test_skills_and_scripts.py`.
