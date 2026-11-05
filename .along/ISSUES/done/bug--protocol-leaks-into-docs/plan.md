# Living Plan: protocol-leaks-into-docs

## Revision 1 (2026-11-05, Planning)

Execution Mode: Role-Based (along-team) - executed via along-team blackboard across 4 verified steps.

## Context

`along init` and `along update` historically scaffolded `docs/topic--along-protocol.md` inside `docs/` (`debt--agents-md-core-slimming`).
`along kb-sync` indexed all `topic--*.md` files into `docs/INDEX.md` and `llms.txt`, leaking internal agent orchestration rules (gates, blackboards, sessions, commit conventions) to public GitHub Pages portals of libraries using Along (e.g. `@actdim/utico`, `@actdim/dynstruct`, `@actdim/msgmesh`, `mempart`).

The solution implements Option 1 (relocating protocol reference to `.along/PROTOCOL.md`) combined with Option 2 defense-in-depth (excluding internal protocol topics during `kb-sync`).

## Steps

1. **Scaffold & Projection Constants**:
   - In `scripts/alongkit/scaffold.py`: update `REFERENCE_DOC_RELPATH = (".along", "PROTOCOL.md")`.
   - In `scripts/alongkit/closeout.py`: update `PROJECTION_FILES` replacing `"docs/topic--along-protocol.md"` with `".along/PROTOCOL.md"`.

2. **Scaffold & Update Engines**:
   - In `scripts/along_init.py`: write protocol reference to `.along/PROTOCOL.md` using `scaffold.REFERENCE_DOC_RELPATH`.
   - In `scripts/along_update.py`: refresh `.along/PROTOCOL.md`; prune legacy `docs/topic--along-protocol.md` when carrying `REFERENCE_MARKER`.
   - In `scripts/migrate_protocol.py`: add healing step `step_relocate_protocol_reference` removing legacy `docs/topic--along-protocol.md` and ensuring `.along/PROTOCOL.md` exists.

3. **Protocol Core and Reference**:
   - In `skills/along-init/protocol.md`: update pointer from `docs/topic--along-protocol.md` to `.along/PROTOCOL.md`.
   - In `skills/along-init/protocol-reference.md`: update descriptive references to `.along/PROTOCOL.md`.
   - Regenerate managed block in root `AGENTS.md`.

4. **Knowledge Retrieval (`along-kb-search`)**:
   - In `scripts/along_kb_search.py`: add index collector for `.along/PROTOCOL.md` (category: `protocol`, category_label: `Protocol`, curated documentation score boost). Add `protocol` to `--category` CLI arguments.

5. **Knowledge Base Synchronization (`along-kb-sync`)**:
   - In `scripts/along_kb_sync.py`: in `_kb_ingest_articles`, explicitly skip any article file matching `topic--along-protocol.md` or slug `along-protocol` as defense-in-depth against unmigrated repositories.
   - Recompile `docs/INDEX.md`, `llms.txt`, and `llms-full.txt`.

6. **Repository Cleanliness in `actdim-along`**:
   - Remove legacy `docs/topic--along-protocol.md`.
   - Create `.along/PROTOCOL.md`.
   - Update doc references in `docs/topic--*.md`.

7. **Verification & Regression Tests**:
   - Update `tests/test_docs.py` (`REFERENCE_PATHS`).
   - Update `tests/test_scaffold_profiles.py` (check `.along/PROTOCOL.md`).
   - Update `tests/test_skills_and_scripts.py` (`test_03b2_protocol_reference_matches_its_source`, line 2452).
   - Update `tests/test_wrap_engine_writes.py`.
   - Run full test suite via `python .along/scripts/test.py`.
