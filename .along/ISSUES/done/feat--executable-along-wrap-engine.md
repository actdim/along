---
protocol: along
slug: executable-along-wrap-engine
type: feat
status: done
completed: 2026-09-10
priority: high
created: 2026-09-09
updated: 2026-09-10
agent: antigravity
tags: [lifecycle, cli, along-wrap, automation, transactions]
milestone: v3.0.0-global-quality-revision
blocked_by: []
related: [feat--unified-wrap-lifecycle-and-commit-skills]
---

# Executable `along wrap` CLI Engine

## 1. Problem Statement

The `along-wrap` skill (`skills/along-wrap/SKILL.md`) currently functions purely as a prose checklist of 9 manual steps. `along_exec.py` and `alongkit.cli` have zero programmatic awareness of `wrap`.

As a consequence of relying on prose-only instructions:
1. Agents routinely skip late steps in the checklist (e.g. failing to append to `.along/HISTORY.md`, omitting `along kb-sync`, or forgetting `along scratch purge`).
2. Moving completed issue files into `.along/ISSUES/done/` and updating YAML front-matter (`status: done`, `completed: YYYY-MM-DD`) is performed through error-prone manual edits.
3. Errors during wrap-up leave the repository in a half-synchronized state.

## 2. Proposed Architecture

Implement a transactional command `along wrap <slug>` (alias: `along session wrap <slug>`) inside `alongkit/lifecycle.py` and register it in `TOOL_MAPPINGS` in `scripts/along_exec.py`:

```text
along wrap <slug> [--status done|superseded] [--summary "..."] [--dry-run]
```

### Automated Execution Sequence:
1. **Pre-Flight Test Gate**: Automatically runs project lifecycle tests (`along test`). If tests fail, halts immediately before any mutations occur.
2. **Git Status & Working Tree Audit**: Verifies that modified files have non-zero size (`getsize > 0`) and that no unexpected untracked artifacts exist.
3. **Issue Lifecycle Finalization**:
   - Updates target issue front-matter (`status: done` or specified terminal state, `completed: YYYY-MM-DD`, `updated: YYYY-MM-DD`).
   - Atomically moves the issue file from `.along/ISSUES/<type>--<slug>.md` into `.along/ISSUES/done/<type>--<slug>.md`.
4. **Projection Recompilation**:
   - Executes `along issue sync` to refresh `.along/ISSUES.md`.
   - Executes `along kb sync` to compile Knowledge Base links and index.
5. **Session Blackboard Purge**:
   - Purges ephemeral session directory `.along/.session/<slug>/` via `alongkit.session.purge_scratch()`.
6. **History Append (Optional Flag)**:
   - Appends a formatted line to nearest `.along/HISTORY.md` when `--summary` is provided.

Cognitive steps (critical diff review and drafting the markdown session log in `.along/SESSIONS/`) remain with the agent, while all mechanical state synchronization is handled by the single command.

## 3. Requirements

- REQ-1: Implement `alongkit/lifecycle.py` with `execute_wrap(repo_root, slug, status, summary, dry_run)`.
- REQ-2: Register `wrap` in `TOOL_MAPPINGS` in `along_exec.py` and `alongkit.cli`.
- REQ-3: Wrap all file modifications in `alongkit.transaction.Snapshot` so that any failure during test execution or sync rolls back cleanly.
- REQ-4: Update `skills/along-wrap/SKILL.md` to document `along wrap <slug>` as the primary automated finalization command.
- REQ-5: Add behavioral tests in `tests/test_lifecycle_wrap.py` verifying issue relocation, front-matter updates, board syncing, and rollback on test failure.

## 4. Acceptance Criteria

- [x] `along wrap <slug>` executable from CLI in source and consumer repositories.
- [x] Tests run prior to issue relocation; failure halts wrap-up without modifying issue status.
- [x] Issue front-matter updated and file moved to `done/`.
- [x] `ISSUES.md` and Knowledge Base projections recompiled automatically.
- [x] Ephemeral session scratch directory purged.
- [x] Behavioral tests cover successful wrap and failure rollback.
