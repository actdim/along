---
protocol: along
protocol_version: "4.0.1"
slug: readme-wiki-unified-search
type: docs
status: done
completed: 2026-09-23
priority: medium
created: 2026-09-23
updated: 2026-09-23
agent: antigravity
tags: [docs, readme, llm-wiki, retrieval]
milestone:
blocked_by: []
related: [feat--progressive-disclosure-and-context-scaling]
---

# Enhance README with Dual-Tier Memory and Zero-Vector Intelligence

## Problem

The current `README.md` mentions the LLM-Wiki and `along-kb-search` briefly, but fails to clearly articulate the core value proposition:
1. It does not explain the critical architectural distinction between evergreen documentation (`docs/`) and transactional workflow memory (`.along/`).
2. It does not highlight the zero-vector, in-repo unified retrieval engine that links code wiki, constraints, issues, and session history in under 50ms without external databases or daemon processes.
3. It lacks explicit metrics on context token reduction (85-95% token savings via bounded snippets).

## Requirements

1. Update `README.md` to introduce the Dual-Tier Memory Architecture:
   - **Evergreen Architecture Wiki (`docs/`)**: Living system consensus, AST symbol grounding, source provenance (SHA-256), deterministic `llms.txt`.
   - **Transactional Living Memory (`.along/`)**: Machine-parseable DAG issue board, append-only ADR logs, constraints projection, and session history.
2. Highlight **Zero-Vector In-Repo Intelligence & Unified Multi-Scope Retrieval**:
   - Single fast query across 4 layers (docs, ADRs, active issues, sessions).
   - Word-boundary aligned snippets (< 150 tokens) eliminating full-file loading.
   - 85-95% context token savings without external vector DBs or background daemons.
3. Verify all links comply with the Stable Entry Point Rule (no direct links into `.along/`).
4. Ensure clean ASCII typography via `along sanitize`.

## Acceptance Criteria

- [ ] `README.md` updated with Dual-Tier Memory Architecture and Zero-Vector Unified Retrieval.
- [ ] No links from `README.md` into `.along/` (Stable Entry Point Rule preserved).
- [ ] Typography check passes with zero violations via `along sanitize`.
