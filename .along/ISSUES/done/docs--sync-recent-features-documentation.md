---
protocol: along
protocol_version: "4.4.16"
slug: sync-recent-features-documentation
type: docs
status: done
completed: 2026-10-16
priority: high
created: 2026-10-16
updated: 2026-10-16
agent: antigravity
tags: [documentation, cli-reference, session-lifecycle, conflict-check, auto-commit, gates, doctor]
blocked_by: []
related: [test-gated-code-merge-pipeline, atomic-wrap-commit-and-start-guard, issue-stub-validation-and-lifecycle-gates, kb-integrity-and-wrap-verification]
---

# Sync Recent Features Documentation Across CLI Reference and Lifecycle Guides

## Problem

Over the last 10 days, several key runtime capabilities, quality gates, and CLI commands were implemented or updated across the core Along engine, but were omitted or remained outdated in the Knowledge Base documentation (`docs/topic--cli-reference.md`, `docs/topic--session-lifecycle.md`, `docs/topic--setup-and-workflow.md`, `docs/topic--runtime-hooks-and-gates.md`, and `docs/topic--troubleshooting.md`). Specifically:
1. `along conflict-check` (`along_conflict_check.py`) is completely absent from `docs/`.
2. `along resolve` only describes docs resolution, missing `--code` mode, `--no-tests`, and test-gated code resolution.
3. `along wrap` documentation still describes uncommitted file warnings rather than default atomic auto-commit (`--no-commit`).
4. `along start` documentation omits the Clean Start Guard and `--allow-dirty`.
5. `along doctor` options omit `issues` (`--issues`) and `docs` (`--docs`), and stub blocking during start and plan approval is undocumented.
6. Acceptance criteria checklist items completion check (`- [ ]`) during wrap is undocumented in session lifecycle.
7. `along dev-env` is completely absent from `docs/`.
8. `--profile` option is omitted in CLI reference for `along start` and `along init`.
9. CLI Black-Box Invariance rule is present in `AGENTS.md` but missing in topic documentation.

## Requirements

- REQ-1: Document `along conflict-check` in `docs/topic--cli-reference.md`.
- REQ-2: Update `along resolve` in `docs/topic--cli-reference.md` to document `--code`, `--no-tests`, and test-gated code conflict auto-resolution.
- REQ-3: Update `along wrap` documentation in `docs/topic--cli-reference.md` and `docs/topic--session-lifecycle.md` to describe default atomic auto-commit of attributed work and metadata, and document `--no-commit`.
- REQ-4: Document Clean Start Guard and `--allow-dirty` flag for `along start` in `docs/topic--cli-reference.md`.
- REQ-5: Document `along doctor issues` (`--issues`), `along doctor docs` (`--docs`), and issue stub validation in `docs/topic--cli-reference.md` and `docs/topic--domain-model.md`.
- REQ-6: Document wrap checklist verification (mandatory completion of `- [ ]` in issue Acceptance Criteria and living plan) in `docs/topic--session-lifecycle.md` and `docs/topic--cli-reference.md`.
- REQ-7: Document `along dev-env` in `docs/topic--cli-reference.md` and `docs/topic--setup-and-workflow.md`.
- REQ-8: Document `--profile <strict|standard|light>` option for `along start` and `along init` in `docs/topic--cli-reference.md`.
- REQ-9: Document CLI Black-Box Invariance rule in `docs/topic--runtime-hooks-and-gates.md` and `docs/topic--troubleshooting.md`.
- REQ-10: Verify link integrity (`python scripts/along_kb_sync.py --check`), clean ASCII typography (`python scripts/sanitize_typography.py`), and run test suite (`python .along/scripts/test.py`).

## Acceptance Criteria

- [x] `docs/topic--cli-reference.md` includes dedicated section and examples for `along conflict-check`.
- [x] `docs/topic--cli-reference.md` documents `along resolve --code` and `--no-tests`.
- [x] `docs/topic--cli-reference.md` and `docs/topic--session-lifecycle.md` document atomic wrap auto-commit and `--no-commit`.
- [x] `docs/topic--cli-reference.md` documents Clean Start Guard and `--allow-dirty` for `along start`.
- [x] `docs/topic--cli-reference.md` documents `along doctor issues` and `along doctor docs`.
- [x] `docs/topic--session-lifecycle.md` documents wrap checklist verification.
- [x] `docs/topic--cli-reference.md` and `docs/topic--setup-and-workflow.md` document `along dev-env`.
- [x] `docs/topic--cli-reference.md` documents `--profile` for `along start` and `along init`.
- [x] `docs/topic--runtime-hooks-and-gates.md` and `docs/topic--troubleshooting.md` document CLI Black-Box Invariance rule.
- [x] `python scripts/along_kb_sync.py --check` passes with zero broken links.
- [x] `python scripts/sanitize_typography.py` passes with zero typography violations.
- [x] Automated tests pass cleanly.
