---
protocol: along
protocol_version: "4.4.14"
slug: kb-integrity-and-wrap-verification
type: feat
status: done
completed: 2026-10-16
priority: high
created: 2026-10-15
updated: 2026-10-16
agent: antigravity
tags: [kb-sync, wrap, lifecycle, gates, safety]
blocked_by: []
related: []
---

# Knowledge Base Integrity, Zombie Stub Detection, Prune Amnesty, and Wrap Checklist Verification

## Problem Statement

Along's lifecycle verification and documentation synchronization mechanisms suffer from systemic gaps:
1. `along wrap` marks tasks done (`[OK]`) without checking whether acceptance criteria checkboxes (`- [ ]`) in the issue body or `plan.md` are completed.
2. `along wrap` invokes `along_kb_sync.py` without `--prune-intent`, causing silent sync failures when obsolete docs are removed during cleanup/refactoring.
3. `along kb-sync` lacks context-awareness: agents deleting dead text in `type: docs` or `cleanup` tasks are blocked by exit code 2 unless `--prune-intent` is manually passed.
4. `along-init` scaffolds empty 14-17 line boilerplate articles, which linger as zombie stubs and trigger duplicate slug warnings.
5. `along doctor` lacks detection for abandoned or empty zombie stubs in `docs/`.
6. Monorepo subprojects can have uncoordinated slug collisions across sibling/parent documentation without namespacing or collision detection.

## Requirements

- REQ-1: Mechanical Checklist Verification in `along wrap`
  `lifecycle.execute_wrap` must scan the closing issue body and `.along/.session/<slug>/plan.md`. If uncompleted checkboxes (`- [ ]`) remain, wrap must abort with exit code 2 unless `--force-reason` is provided.
- REQ-2: Wrap KB-Sync Prune Authorization
  `lifecycle.execute_wrap` must automatically pass `--prune-intent "Issue wrap: <slug>"` when closing an issue of `type: docs` or carrying `cleanup`/`refactor`/`prune` tags.
- REQ-3: Context-Aware Pruning in `along_kb_sync.py`
  `along_kb_sync.py` must inspect active session state: if an active issue has `type: docs` or `cleanup`/`refactor` tags, content reduction is authorized automatically with an audit notice.
- REQ-4: Zombie Stub Detector & Clean Scaffolding
  `along doctor` must detect docs with empty boilerplate or < 3 content lines older than 7 days (`[WARN: zombie-stub]`). `along-init` must not scaffold empty topic files without user content.
- REQ-5: Cross-Project Slug Namespacing & Collision Detection
  `along_kb_sync.py` in monorepos must support namespaced slugs (`<subproject>:<slug>`) and fail in `--strict` mode when sibling subprojects define identical un-namespaced non-standard slugs.

## Acceptance Criteria

- [x] `along wrap` rejects issues with uncompleted `- [ ]` checkboxes unless `--force-reason` is supplied.
- [x] `along wrap` passes `--prune-intent` when closing cleanup or docs issues.
- [x] `along kb-sync` auto-authorizes content reduction when bound to an active docs/cleanup issue.
- [x] `along doctor` flags zombie stubs and `along init` stops generating empty topic stubs.
- [x] `along kb-sync --strict` reports cross-project slug collisions.
- [x] Hermetic tests verify all new gates and behavior with zero failures.
- [x] Clean ASCII check (`along sanitize`) passes.

