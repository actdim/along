---
protocol: along
slug: modular-decisions-and-mkdocs-integration
date: 2026-09-11
agent: antigravity
summary: "Migrated monolithic DECISIONS.md to modular .along/DECISIONS/ records, compiled lean projection boards (< 6 KB), exported ADRs to docs/decisions/ for MkDocs, updated Along CLI and doctor, and verified full test suite"
milestone: v3.1.0-native-ast-and-cursor-parity
issues_advanced: []
issues_completed: [feat--modular-decisions-and-mkdocs-integration]
decisions: []
risks_logged: []
spikes_conducted: []
branch: main
commit: unknown
---

# Session Log: 2026-09-11 - Modular Decisions Architecture & MkDocs Integration

## 1. Objectives & Context

Completion of `[feat--modular-decisions-and-mkdocs-integration]` under milestone `v3.1.0-native-ast-and-cursor-parity`:
- Break down monolithic `.along/DECISIONS.md` (~85 KB, ~21,000 tokens) into modular file-per-ADR records in `.along/DECISIONS/ADR-YYYY-MM-DD--<slug>.md`.
- Produce a compact compiled `.along/DECISIONS.md` projection board (< 6 KB) preserving Git branch isolation and bounded session-start context budget.
- Export modular ADRs to `docs/decisions/` with an `INDEX.md` catalog, integrating them into the MkDocs navigation and search index.
- Update `along decision create` and `along decision sync` CLI commands, doctor diagnostics, search engine, dashboard, and protocol migration engine.
- Maintain full backward compatibility with single-file append-only `DECISIONS.md` for older repositories.
- Add comprehensive unit tests in `tests/test_modular_decisions.py` and ensure 100% test pass rate across all suites.

## 2. Key Architecture & Changes

1. **Core Entity Implementation (`scripts/alongkit/entities.py`)**:
   - Registered `"decision": "DECISIONS"` in `ENTITY_DIRS`, defined `DECISION_STATUSES` and `ACTIVE_DECISION_STATUSES`.
   - Added `scan_decisions(repo_root)` supporting both modular `.along/DECISIONS/*.md` and monolithic `DECISIONS.md` fallback, extracting frontmatter, context, decision, consequences, and superseded links.
   - Added `compile_decisions_board(repo_root)` producing lean `.along/DECISIONS.md` projection board (6,068 bytes, < 6 KB).
   - Added `create_decision_file(...)` creating structured modular ADR files with YAML front-matter (`type: decision`).
   - Updated `sync_constraints(repo_root)` to compile active constraints from `.along/DECISIONS/`.
   - Updated `validate_entities(repo_root)` to validate `.along/DECISIONS/*.md` schemas, mandatory fields, dates, statuses, and `superseded_by` references.

2. **CLI & Diagnostics Integration (`scripts/along_exec.py`)**:
   - Updated `handle_decision_command`: `along decision create` writes modular records and triggers projections compilation; `along decision sync` recompiles `DECISIONS.md`, `CONSTRAINTS.md`, and exports to `docs/decisions/`.
   - Updated `handle_doctor_command`: validates `.along/DECISIONS/` modular directory (36 records confirmed).

3. **Static Documentation & MkDocs Integration (`hooks/rewrite_links.py`, `mkdocs.yml`, `scripts/along_kb_sync.py`)**:
   - Added `sync_decisions_to_docs(repo_root)` publishing 36 ADR pages and `INDEX.md` catalog into `docs/decisions/`.
   - Updated `mkdocs.yml` adding `Decisions: decisions/INDEX.md` to navigation.
   - Updated `hooks/rewrite_links.py` Zone 1 to resolve internal doc links relative to `current_dir` rather than docs root, fixing nested directory links.
   - Rewrote outbound links in `docs/topic--architecture.md`, `docs/topic--setup-and-workflow.md`, `docs/topic--skills-reference.md`, and `docs/INDEX.md` to point to `./decisions/ADR-*.md`.

4. **Search Engine & Dashboard Updates (`scripts/along_kb_search.py`, `dashboard/`)**:
   - Updated `along_kb_search.py` to scan `.along/DECISIONS/*.md` with fallback to `DECISIONS.md`.
   - Updated `dashboard/schemas/entities.py` and `dashboard/core/collector.py` to read modular decision files and extract metadata.

5. **Migration Engine (`scripts/migrate_protocol.py`)**:
   - Implemented Step 11 (`step_migrate_v3_1_modular_decisions`) with dry-run and backup support.
   - Migrated all 36 historical ADRs into `.along/DECISIONS/ADR-*.md`.
   - Fixed `step_migrate_v1_5_entity_ecosystem` to preserve valid terminal statuses (`superseded`, `cancelled`, `duplicate`) in `ISSUES/done/`.

6. **Unit Tests & Verification (`tests/test_modular_decisions.py`)**:
   - Added test suite covering modular scan, fallback scan, compilation, context budget compliance (< 7 KB), file creation, CLI execution, and entity validation.
   - Removed banned ghost tool references (`wiki_query`) from historical ADR.
   - All 374 repository unit tests pass with zero errors and zero failures.

## 3. Quality & Verification Manifest

- Unit Tests: `python .along/scripts/test.py` -> 374 passed, 0 failed, 1 skipped.
- Context Budget: `along context-budget --check` -> ALL PASSED (`DECISIONS.md` 6,068 B < 7,168 B ceiling).
- Doctor Diagnostics: `along doctor` -> 0 errors, 0 warnings.
- Entity Doctor: `along doctor --entities` -> 227 entities valid, 0 errors, 0 warnings.
- MkDocs Strict Build: `uv run mkdocs build --strict` -> Exited 0, documentation built cleanly.
- Typography: `along sanitize` -> 405 files scanned, zero banned characters.
