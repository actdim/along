---
protocol: along
slug: modular-decisions-and-mkdocs-integration
type: feat
status: open
priority: high
created: 2026-09-10
updated: 2026-09-10
agent: antigravity
tags: [decisions, adr, mkdocs, documentation, entities, refactor]
milestone: v3.1.0-native-ast-and-cursor-parity
blocked_by: []
related: [always-on-context-budget-exceeds-claims, agents-md-context-budget-pruning]
---

# Modular Decisions Architecture & First-Class MkDocs Publication

## 1. Problem Statement & Motivation

Currently, Architectural Decision Records (ADRs) are stored in a single monolithic file: `.along/DECISIONS.md`.
While this design originally aimed for simplicity, with 36 ADRs accumulated:
1. **Context Bloat**: The file has grown to ~85 KB (~21,000 tokens). Reading it whole in agent sessions costs significant token budget and latency.
2. **Missing Granular Link Targets**: Documentation articles (`docs/topic--architecture.md`, etc.) and code references cannot link to individual decision files. Hyperlinks point to the whole 85 KB file, forcing humans and agents to manually search for relevant headings.
3. **MkDocs Boundary Friction**: MkDocs builds documentation strictly from the `docs/` root. Because `.along/DECISIONS.md` lives outside `docs/`, links to it on the static documentation site must be rewritten to external GitHub URLs (`hooks/rewrite_links.py`) rather than rendered as first-class searchable documentation pages.
4. **Asymmetry with Issues Ecosystem**: In Along, issues are stored as discrete files (`.along/ISSUES/<type>--<slug>.md`), while `.along/ISSUES.md` serves as a lightweight compiled projection. Decisions lack this modular architecture.

## 2. Proposed Target Architecture

### A. Modular File-per-ADR Storage (`.along/DECISIONS/`)
Decisions are split into individual Markdown files inside `.along/DECISIONS/`:
```text
.along/DECISIONS/
  ADR-2026-08-15--single-file-append-only-decisions.md
  ADR-2026-09-01--typography-rule-scope.md
  ADR-2026-09-01--frontmatter-on-ruamel-yaml.md
  ...
```

Each ADR file is self-contained with structured YAML front-matter:
```markdown
---
protocol: along
slug: typography-rule-scope
date: 2026-09-01
status: accepted
tags: [typography, sanitization, gates]
---

# ADR-2026-09-01--typography-rule-scope - Scope and Enforcement Mode of the ASCII Typography Rule

- Date: 2026-09-01
- Status: accepted
- Context: ...
- Decision: ...
- Consequences: ...
```

### B. Compact Decisions Projection (`.along/DECISIONS.md`)
`.along/DECISIONS.md` becomes a derived, lightweight projection board (analogous to `.along/ISSUES.md`):
- Lists active ADRs grouped by theme or chronologically with relative links to `.along/DECISIONS/ADR-*.md`.
- Lists superseded and retired ADRs in a compact collapsed section.
- Kept strictly under 6 KB to comply with context budget limits.
- The `merge=union` Git driver is no longer required for `DECISIONS.md` (it is recompiled deterministically via `along decision sync`). Individual ADR files in `.along/DECISIONS/` never conflict when created in parallel Git branches.

### C. Active Constraints Projection (`.along/CONSTRAINTS.md`)
Continues to be compiled by `along decision sync` directly from non-superseded ADR files in `.along/DECISIONS/`, preserving ultra-lean startup context (< 4 KB) for agents.

### D. First-Class MkDocs Publication (`docs/decisions/` or `docs/adr/`)
To make decisions first-class citizens of the public documentation site:
1. **Automated KB Mirroring**: `along kb sync` / `along decision sync` exports or compiles active ADRs into `docs/decisions/`:
   ```text
   docs/decisions/
     INDEX.md
     ADR-2026-08-15--single-file-append-only-decisions.md
     ADR-2026-09-01--typography-rule-scope.md
     ...
   ```
2. **MkDocs Navigation**: Add a dedicated `Decisions` section to `mkdocs.yml`:
   ```yaml
   nav:
     - Home: INDEX.md
     - Architecture: topic--architecture.md
     - Decisions: decisions/INDEX.md
     ...
   ```
3. **Internal Hyperlinks**: In `docs/topic--architecture.md`, rewrite outbound links from external GitHub URLs to local doc links:
   `[ADR-typography](./decisions/ADR-2026-09-01--typography-rule-scope.md)`.
4. **Hook Modernization**: Update `hooks/rewrite_links.py`: decision links are treated as native internal pages (Zone 1) with instant client-side search and full Material styling.

## 3. Implementation Plan & Migration Strategy

1. **Migration Engine Step (scripts/migrate_protocol.py)**:
   - Implement `step_migrate_v3_1_modular_decisions()` to parse existing `.along/DECISIONS.md`.
   - Atomically create individual `.along/DECISIONS/ADR-YYYY-MM-DD--<slug>.md` files for all 36 historical records.
   - Recompile `.along/DECISIONS.md` as the initial index projection.
   - Provide non-destructive dry-run and backup via `alongkit.migration`.

2. **Core Engine Refactoring (scripts/alongkit/)**:
   - `alongkit/entities.py`:
     - Refactor `parse_decision_entries()` to scan `.along/DECISIONS/` directory (with backward-compatible single-file fallback).
     - Implement `compile_decisions_board()` to generate `.along/DECISIONS.md`.
     - Update `sync_constraints()` to read from directory.
     - Update `format_adr()` and `create_decision()` to emit individual files.
   - `alongkit/kb.py` and `scripts/along_kb_sync.py`:
     - Add decision export pipeline into `docs/decisions/`.
     - Update link integrity gate and Stable Entry Point Rule to validate `docs/decisions/` cross-references.

3. **Tooling & CLI Updates**:
   - `scripts/along_exec.py`:
     - `along decision create <slug>` creates new file in `.along/DECISIONS/` and invokes sync.
     - `along decision sync` refreshes `DECISIONS.md`, `CONSTRAINTS.md`, and `docs/decisions/`.
     - `along doctor --entities` scans `.along/DECISIONS/*.md` for valid schema and statuses.
   - `scripts/along_kb_search.py`:
     - Traverse `.along/DECISIONS/*.md` instead of slicing a monolithic file.
   - `dashboard/collectors/entities.py`:
     - Load decisions from directory files for Cytoscape DAG visualization.

4. **Documentation & MkDocs Integration**:
   - Configure `mkdocs.yml` to include `Decisions` in site navigation.
   - Update `hooks/rewrite_links.py` to route decision links internally.
   - Recompile `llms-full.txt` and `docs/INDEX.md`.

5. **Test Suite Modernization**:
   - Update `tests/test_alongkit.py`, `tests/test_kb_search.py`, and `tests/test_context_budget.py`.
   - Add hermetic behavioral tests for `along decision create`, directory parsing, and projection compilation.

## 4. Requirements

- REQ-1: Migrate all 36 historical ADRs into discrete files under `.along/DECISIONS/` without loss of metadata or text.
- REQ-2: Recompile `.along/DECISIONS.md` into a lightweight projection board under 6 KB.
- REQ-3: Update `along decision create` to create individual `.md` files with valid YAML front-matter.
- REQ-4: Export/compile decisions into `docs/decisions/` during KB sync for MkDocs native publishing.
- REQ-5: Add `Decisions` navigation entry to `mkdocs.yml` and update `hooks/rewrite_links.py`.
- REQ-6: Ensure `along doctor --entities`, `along context-budget`, and `along-kb-search` fully support modular decisions.
- REQ-7: Complete test coverage verifying directory scanning, migration idempotency, and projection sync.

## 5. Acceptance Criteria

- [ ] All 36 ADRs migrated to `.along/DECISIONS/ADR-YYYY-MM-DD--<slug>.md`.
- [ ] `.along/DECISIONS.md` functions as a compiled projection under 6 KB.
- [ ] `along decision create <slug>` creates individual files and updates projections.
- [ ] `along decision sync` and `along kb sync` compile `docs/decisions/` and pass MkDocs build.
- [ ] Cross-references in `docs/topic--architecture.md` point to local `docs/decisions/*.md` files.
- [ ] `along doctor --entities` reports 0 errors across modular decisions.
- [ ] Full automated test suite passes with 0 failures.
