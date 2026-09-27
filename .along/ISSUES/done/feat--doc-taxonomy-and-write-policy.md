---
protocol: along
protocol_version: "4.1.0"
slug: doc-taxonomy-and-write-policy
type: feat
status: done
priority: high
created: 2026-09-27
updated: 2026-09-27
completed: 2026-09-27
agent: antigravity
tags: [docs, taxonomy, write-policy, manual-lock, gates, llm-wiki]
milestone: v4.2.0-monorepo-subprojects
blocked_by: []
related: []
superseded_by:
duplicate_of:
---

# Topic Types Taxonomy, Write Policy Manual Lock, and Documentation Routing Tree

## Problem Statement
Currently, Knowledge Base articles in `docs/topic--*.md` that are not `architecture`, `domain-model`, or `setup-workflow` are lumped into a generic `type: topic`.
This creates ambiguity:
1. Pure technical reference contracts (grounded in codebase AST symbols) and conceptual/marketing/comparison articles (which do not define AST symbols) share the same validation bucket. Running `--check-symbols` on non-technical articles can report false ghost symbols.
2. The `curated: true` flag indicates an article is compiled/maintained, but does not prevent agents from modifying it during automated blast-radius sweeps. Conceptual, pitch, comparison, or human-authored articles risk automated mutations.
3. Agents lack a clear decision/routing tree for deciding where new documentation should be placed (`README.md`, `docs/topic--<slug>.md`, `.along/DECISIONS/`, or `.along/CONSTRAINTS.md`).

## Proposed Solution
1. **Granular Topic Types**: Expand standard taxonomy in `alongkit.kb`:
   - `reference`: Technical interface contracts, CLI commands, configuration schemas (validated with AST code symbol grounding).
   - `explanation`: Conceptual architecture, comparative trade-offs, product positioning, design philosophy (exempt from AST ghost symbol grounding).
   - `guide`: How-to walkthroughs, runbooks, and developer workflows.
   - `architecture`, `domain-model`, `setup-workflow`: Existing structured section contract types.
   - `topic`: Maintained for backward compatibility.
2. **Explicit Write Policy**: Support `write_policy: manual` (and `locked: true` alias) in front-matter:
   - In `along_graph_impact.py`, exclude files with `write_policy: manual` from automatic blast-radius candidate documentation.
   - In declarative runtime gates, introduce `[gate: doc-manual-lock]` (`check_doc_manual_lock`) blocking agent modifications to manual-policy docs unless explicitly targeted by a `docs--<slug>` issue.
   - In `along_kb_sync.py`, respect `write_policy: manual` during symbol grounding checks.
3. **Documentation Routing Tree**: Formally document the decision tree in `AGENTS.md`, `skills/along-kb-sync/SKILL.md`, and `docs/topic--llm-wiki-architecture.md`.

## Acceptance Criteria
- [ ] `alongkit.kb` defines standard topic types (`reference`, `explanation`, `guide`, `architecture`, `domain-model`, `setup-workflow`, `topic`) and distinguishes between symbol-grounded types vs conceptual types.
- [ ] `along_kb_sync.py` exempts `explanation` and `write_policy: manual` articles from ghost symbol AST checks.
- [ ] `along_graph_impact.py` skips or flags `write_policy: manual` articles during blast radius documentation mapping.
- [ ] Declarative gate `doc_manual_lock` (`[gate: doc-manual-lock]`) is defined in `default_gates.yaml` and implemented in `alongkit.hooks.predicates`.
- [ ] Traceability between `default_gates.yaml` and prose (`AGENTS.md`, `skills/along-init/protocol.md`) passes `audit_traceability`.
- [ ] Hermetic tests verify the new types, `write_policy: manual` protection, and gate enforcement.
- [ ] All existing tests pass with zero regressions.
