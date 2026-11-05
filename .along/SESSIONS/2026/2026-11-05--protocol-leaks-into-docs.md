---
protocol: along
protocol_version: "4.6.0"
date: 2026-11-05
slug: protocol-leaks-into-docs
agent: antigravity
branch: main
commit: 3b6a69e
summary: Relocate agent protocol reference from docs/ to .along/PROTOCOL.md
issues_advanced: []
issues_completed: [bug--protocol-leaks-into-docs]
decisions: []
---

# Session: Protocol leaks into docs

## Summary
Relocate agent protocol reference from docs/ to .along/PROTOCOL.md

## Decisions
- None (confirmed at wrap: no architectural decisions).

## Blackboard Record

Execution mode: role-based; plan revision 2; approved: true.

| Step | Title | Status | Retries | Review |
| --- | --- | --- | --- | --- |
| 1 | Step 1 | passed | 0 | yes |
| 2 | Step 2 | passed | 0 | yes |
| 3 | Step 3 | passed | 0 | yes |
| 4 | Step 4 | passed | 0 | yes |

Plan: kept with the issue (`plan/plan.md`, 1 revision(s)).

### Research

#### Research Findings: protocol-leaks-into-docs

##### Problem Overview
Historical context: commit `856249a` (`debt--agents-md-core-slimming`) extracted situational procedures from `AGENTS.md` into `docs/topic--along-protocol.md`.
Because this file was located inside `docs/`, `along kb-sync` unconditionally ingested it into `docs/INDEX.md`, rendering it in the public Mermaid graph and article list.
Static documentation site generators (VitePress, MkDocs, Docusaurus) compiled `INDEX.md` and the article into public project documentation websites (e.g. GitHub Pages for `@actdim/utico`, `@actdim/msgmesh`, `dynstruct`).

##### Files & Symbols Under Investigation

1. `scripts/alongkit/scaffold.py`:
   - `REFERENCE_DOC_RELPATH = ("docs", "topic--along-protocol.md")` -> must become `(".along", "PROTOCOL.md")`.
   - `REFERENCE_MARKER = "<!-- ALONG-PROTOCOL-REFERENCE (managed by along-init"` -> keeps identifying managed copies.

2. `scripts/alongkit/closeout.py`:
   - `PROJECTION_FILES`: includes `"docs/topic--along-protocol.md"` -> must become `".along/PROTOCOL.md"`.

3. `scripts/along_init.py`:
   - `scaffold_protocol_reference`: writes `os.path.join(root, *scaffold.REFERENCE_DOC_RELPATH)`. Updates logging note.

4. `scripts/along_update.py`:
   - `refresh_protocol_reference`: refreshes `os.path.join(ctx_dir, *scaffold.REFERENCE_DOC_RELPATH)`.
   - Must prune legacy `docs/topic--along-protocol.md` if present and containing `REFERENCE_MARKER`.

5. `scripts/migrate_protocol.py`:
   - Needs migration step `step_relocate_protocol_reference` ensuring legacy file in `docs/` is pruned and `.along/PROTOCOL.md` is initialized.

6. `skills/along-init/protocol.md` & `AGENTS.md`:
   - Line 5: references `docs/topic--along-protocol.md` -> must reference `.along/PROTOCOL.md`.

7. `skills/along-init/protocol-reference.md`:
   - Description text updated to name `.along/PROTOCOL.md`.

8. `scripts/along_kb_search.py`:
   - Ingests `docs/*.md`, `.along/ISSUES/`, `.along/DECISIONS/`, `.along/MILESTONES/`, `.along/SESSIONS/`.
   - Missing `.along/PROTOCOL.md`. Adding category `protocol` allows retrieval of procedure sections by agents.

9. `scripts/along_kb_sync.py`:
   - `_kb_ingest_articles`: loops over `docs_dir`. Needs explicit check to ignore `topic--along-protocol.md` or `slug == "along-protocol"` as defense-in-depth.

10. Tests to update:
    - `tests/test_docs.py`
    - `tests/test_scaffold_profiles.py`
    - `tests/test_skills_and_scripts.py`
    - `tests/test_wrap_engine_writes.py`

### Execution Trace

#### Execution Trace: protocol-leaks-into-docs
- 2026-11-05T15:02:36Z plan approved (along plan approve) approved_via: cli-unverified, plan_sha256: e97fbe496888
- 2026-11-05T15:02:57Z step 1: pending -> in-progress
- 2026-11-05T15:04:23Z step 1: in-progress -> passed
- 2026-11-05T15:04:30Z step 2: pending -> in-progress
- 2026-11-05T15:08:02Z step 2: in-progress -> passed
- 2026-11-05T15:08:09Z step 3: pending -> in-progress
- 2026-11-05T15:13:36Z step 3: in-progress -> passed
- 2026-11-05T15:13:44Z step 4: pending -> in-progress
- 2026-11-05T15:16:24Z step 4: in-progress -> passed
- 2026-11-05T15:21:52Z test pass (Wrap Quality Gate)

### Review step-1

#### Review Report: Step 1 (Core Constants & Scaffold Relocation)

##### Reviewer Rubric Audit
- Zero-Byte & File Integrity Gate: EXECUTED (PASS)
- Automated Tests: EXECUTED (PASS) [python .along/scripts/test.py tests.test_scaffold_profiles.TestReferenceAction]
- Diff & Scope Audit: EXECUTED (PASS)
  - `scripts/alongkit/scaffold.py`: updated `REFERENCE_DOC_RELPATH` to `(".along", "PROTOCOL.md")`
  - `scripts/alongkit/closeout.py`: updated `PROJECTION_FILES` to replace `docs/topic--along-protocol.md` with `.along/PROTOCOL.md`
  - `scripts/along_init.py`: docstring and path resolution cleanly aligned
- Requirement Traceability: EXECUTED (PASS) [REQ-1, REQ-2]
- Clean Typography: EXECUTED (PASS)

VERDICT: PASS

Gate Execution Manifest:
- Workspace Isolation: EXECUTED (PASS) [mode: inherit]
- File Integrity: EXECUTED (PASS)
- Automated Tests: EXECUTED (PASS)
- Diff Scope Audit: EXECUTED (PASS)
- Requirement Traceability: EXECUTED (PASS) [REQ-1, REQ-2]
- Clean Typography: EXECUTED (PASS)

### Review step-2

#### Review Report: Step 2 (Update & Migration Engine Cleanup)

##### Reviewer Rubric Audit
- Zero-Byte & File Integrity Gate: EXECUTED (PASS)
- Automated Tests: EXECUTED (PASS) [test_07_migrate_protocol_execution, test_08_along_update_check_only]
- Diff & Scope Audit: EXECUTED (PASS)
  - `scripts/along_update.py`: `refresh_protocol_reference` now refreshes `.along/PROTOCOL.md` and safely prunes legacy `docs/topic--along-protocol.md` when it carries Along managed marker.
  - `scripts/migrate_protocol.py`: added `step_relocate_protocol_reference` to both standard version chain and standalone healing passes.
- Requirement Traceability: EXECUTED (PASS) [REQ-2, REQ-3]
- Clean Typography: EXECUTED (PASS)

VERDICT: PASS

Gate Execution Manifest:
- Workspace Isolation: EXECUTED (PASS) [mode: inherit]
- File Integrity: EXECUTED (PASS)
- Automated Tests: EXECUTED (PASS)
- Diff Scope Audit: EXECUTED (PASS)
- Requirement Traceability: EXECUTED (PASS) [REQ-2, REQ-3]
- Clean Typography: EXECUTED (PASS)

### Review step-3

#### Review Report: Step 3 (Protocol Reference, Search Indexing & KB Sync Filtering)

##### Reviewer Rubric Audit
- Zero-Byte & File Integrity Gate: EXECUTED (PASS)
- Automated Tests: EXECUTED (PASS) [along_kb_sync recompile, along_kb_search retrieval]
- Diff & Scope Audit: EXECUTED (PASS)
  - `skills/along-init/protocol.md` and `AGENTS.md`: updated core pointer to `.along/PROTOCOL.md`
  - `skills/along-init/SKILL.md` and `skills/along-update/SKILL.md`: updated descriptions
  - `scripts/along_kb_search.py`: indexed `.along/PROTOCOL.md` with category `protocol` and documentation boost
  - `scripts/along_kb_sync.py`: excluded `along-protocol` articles from `docs/INDEX.md`, Mermaid graphs, and `llms.txt`
  - `docs/topic--along-protocol.md`: deleted from repository
  - `.along/PROTOCOL.md`: successfully rendered and tracked in `.along/`
  - `docs/INDEX.md` & `llms.txt`: recompiled cleanly without `Along Protocol Reference`
- Requirement Traceability: EXECUTED (PASS) [REQ-4, REQ-5, REQ-6]
- Clean Typography: EXECUTED (PASS)

VERDICT: PASS

Gate Execution Manifest:
- Workspace Isolation: EXECUTED (PASS) [mode: inherit]
- File Integrity: EXECUTED (PASS)
- Automated Tests: EXECUTED (PASS)
- Diff Scope Audit: EXECUTED (PASS)
- Requirement Traceability: EXECUTED (PASS) [REQ-4, REQ-5, REQ-6]
- Clean Typography: EXECUTED (PASS)

### Review step-4

#### Review Report: Step 4 (Regression Tests & Verification)

##### Reviewer Rubric Audit
- Zero-Byte & File Integrity Gate: EXECUTED (PASS)
- Automated Tests: EXECUTED (PASS)
  - `python .along/scripts/test.py -k test_docs`: 6/6 tests passing
  - `python .along/scripts/test.py -k test_scaffold_profiles`: 14/14 tests passing
  - `python .along/scripts/test.py -k test_wrap_engine_writes`: 10/10 tests passing
  - `test_03b_managed_block_matches_its_source`: PASS
  - `test_03b2_protocol_reference_matches_its_source`: PASS
  - `test_33_programmatic_integrity_gates_and_git_guard`: PASS
- Diff & Scope Audit: EXECUTED (PASS)
  - `tests/test_docs.py`: updated reference path to `.along/PROTOCOL.md` and added leak-prevention assertion `test_along_protocol_not_leaked_into_index_or_docs`
  - `tests/test_scaffold_profiles.py`: updated assertions to check `.along/PROTOCOL.md`
  - `tests/test_skills_and_scripts.py`: updated reference checks to `.along/PROTOCOL.md`
  - `tests/test_wrap_engine_writes.py`: updated engine-write auto-commit tests
- Requirement Traceability: EXECUTED (PASS) [REQ-7]
- Clean Typography: EXECUTED (PASS) [`along sanitize` verified: 1137 files clean]

VERDICT: PASS

Gate Execution Manifest:
- Workspace Isolation: EXECUTED (PASS) [mode: inherit]
- File Integrity: EXECUTED (PASS)
- Automated Tests: EXECUTED (PASS)
- Diff Scope Audit: EXECUTED (PASS)
- Requirement Traceability: EXECUTED (PASS) [REQ-7]
- Clean Typography: EXECUTED (PASS)
