---
protocol: along
slug: llm-wiki-docs-architecture-and-singular-skills-refactoring
title: "LLM-Wiki Knowledge Base Architecture in docs/, .archive/ Isolation & Singular Domain-First Skills Refactoring"
date: 2026-08-30
status: accepted
tags: [adr, architecture, decision]
---

# ADR-2026-08-30--llm-wiki-docs-architecture-and-singular-skills-refactoring - LLM-Wiki Knowledge Base Architecture in docs/, .archive/ Isolation & Singular Domain-First Skills Refactoring

- Date: 2026-08-30
- Status: Accepted
- Context:
  1. Previously, structured documentation was placed in `.along/KB/` and raw source notes often polluted documentation directories.
  2. Multi-part skill names like `along-sync-issues`, `along-sync-decisions`, and `along-bump-version` lacked uniform domain hierarchy and plural/singular consistency.
  3. LLM agents needed a token-efficient retrieval engine based on `nvk/llm-wiki` principles to query documentation snippets before reading full documents into context.
- Decision:
  1. **Top-Level `docs/` Knowledge Base**: Move all active project documentation and Wiki articles into top-level `docs/` with standard relative Markdown links (`[Title](./target.md)`).
  2. **Raw Source Isolation (`.archive/`)**: Move raw, unmanaged notes and source documents into a hidden `.archive/` directory so developers can inspect and safely delete them later without polluting active KB searches.
  3. **Singular Domain-First Skill Hierarchy**: Standardize all 3-part skill names to `along-<singular_entity>-<action>`:
     - `along-kb-sync` (single idempotent compiler/linter)
     - `along-kb-search` (token-efficient snippet retrieval)
     - `along-issue-sync`
     - `along-context-sync`
     - `along-decision-sync`
     - `along-history-sync`
     - `along-graph-check`
     - `along-dep-scan`
     - `along-version-bump`
  4. **Targeted Agent Fast Retrieval**: Protocol requires agents to query `along-kb-search` before reading full documentation files into context.
  5. **Strict Nearest Subproject & Submodule Localization**: When working in submodules, nested packages, or symlinked component libraries, all entity creation and updates (`ISSUES`, `SESSIONS`, `CONTEXT`, `DECISIONS`, `HISTORY`) MUST strictly occur in the **nearest `.along/`** corresponding to the modified files, preventing workspace root pollution.
- Consequences: Cleaner repository layout, universal Markdown rendering on GitHub/npm, reduced agent token usage via targeted retrieval, a consistent domain-first skill naming convention across all providers, and strict project boundary isolation for submodules and multi-package workspaces.
