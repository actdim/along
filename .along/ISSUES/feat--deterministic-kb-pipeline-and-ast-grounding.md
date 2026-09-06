---
protocol: along
protocol_version: "2.2.21"
slug: deterministic-kb-pipeline-and-ast-grounding
type: feat
status: open
priority: high
created: 2026-09-06
updated: 2026-09-06
agent: antigravity
tags: [llm-wiki, kb, deterministic, ast-grounding, cross-link, quality-gate]
milestone: v3.0.0-global-quality-revision
blocked_by: []
related: []
---

# Deterministic KB Pipeline: AST Grounding, Auto-Crosslinking, and Structured Synthesis Contracts

## Problem Statement

The current Along LLM-Wiki implementation (`along-kb-sync` and `docs/topic--*.md`) provides deterministic guarantees for indexing (`INDEX.md`), context exports (`llms.txt`, `llms-full.txt`), dead-link detection (404 checks), and provenance hashing. However, the authoring and maintenance phases remain overly reliant on non-deterministic LLM discretion, creating three critical quality defects:

1. **Passive Link Verification vs Zero Active Cross-Linking**:
   - `along_kb_sync.py` only reports broken links (404 errors).
   - Linking between related topics is left entirely to the model's memory. Concepts mentioned in one article often fail to reference existing canonical documentation files, fragmenting the knowledge graph.
2. **Ungrounded Code Documentation (Ghost Symbols)**:
   - Documentation articles in `docs/topic--*.md` frequently reference functions, classes, CLI flags, or file paths that have been refactored, renamed, or deleted in the codebase.
   - No automated deterministic gate checks whether symbols documented in backticks or tables actually exist in the repository AST.
3. **Unbounded Free-Form Synthesis (Hallucination Risk)**:
   - Topic creation and updates depend on open-ended prompt instructions in `SKILL.md`.
   - Without a structured extraction schema, models cut corners, omit critical interface invariants, or produce vague descriptive summaries instead of concrete technical specifications.

## Proposed Architectural Solutions

### 1. Deterministic Cross-Link Engine (`along_kb_sync.py --crosslink`)
- **Entity and Concept Dictionary**:
  - Build a deterministic in-memory dictionary of all known topic titles, slugs, and explicit `tags` from front-matter across `docs/topic--*.md`.
- **Lexical Scan and Candidate Matching**:
  - Scan article prose (outside code fences and existing links) for exact or stemmed matches against the topic dictionary.
- **Modes**:
  - `--crosslink-check`: Audit mode that lists missed cross-linking opportunities across existing documentation.
  - `--crosslink-apply`: Safe deterministic insertion of relative Markdown links (`[Concept](./topic--slug.md)`), strictly bounded to first occurrence per section to prevent link stuffing.

### 2. AST and Symbol Grounding Gate (`along_kb_sync.py --check-symbols`)
- **Code Symbol Inventory**:
  - Extract public symbols (classes, functions, exported constants, CLI subcommands) from codebase files using pure Python AST (and regex/treesitter fallback for non-Python packages).
- **Symbol Verification in Documentation**:
  - Extract code backticks (e.g. `` `resolve_llm_targets` ``) from `docs/topic--*.md`.
  - Check whether referenced codebase symbols physically resolve to live symbols in the codebase.
  - Emit clear drift warnings when documented symbols no longer exist in code (`[GHOST SYMBOL] docs/topic--architecture.md references non-existent function resolve_llm_targets`).

### 3. Structured Synthesis Contracts & Section Linting
- **Mandatory Section Taxonomy for Standard Topics**:
  - Define minimum required structural headings per topic type in `scripts/alongkit/kb.py`:
    - `architecture`: Overview, Core Components, Data Flow, Invariants & Failure Modes.
    - `domain-model`: Entity Taxonomy, Front-matter Schemas, Graph Relationships.
    - `setup-workflow`: Prerequisites, Runner Commands, Quality Gates.
- **Section Completeness Gate**:
  - `--strict` mode verifies that required sections are populated with non-trivial text (blocking empty stubs or generic template placeholders).

## Acceptance Criteria

- [ ] `along_kb_sync.py` includes a deterministic dictionary-based cross-link scanner (`--crosslink-check` and `--crosslink-apply`).
- [ ] `along_kb_sync.py` includes an AST-based symbol verification pass (`--check-symbols`) that flags deleted or renamed code entities.
- [ ] Topic templates and section schemas are enforced during `--strict` compilation.
- [ ] Behavioral unit tests added in `tests/test_kb_sync.py` verifying cross-linking, symbol grounding, and section validation on hermetic fixtures.
- [ ] Zero non-ASCII typography or forbidden characters in code, documentation, and issue entities.

