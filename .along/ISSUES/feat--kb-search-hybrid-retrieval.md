---
protocol: along
protocol_version: "4.5.4"
slug: kb-search-hybrid-retrieval
type: feat
status: open
priority: medium
created: 2026-10-30
updated: 2026-10-30
agent: antigravity
tags: [kb-search, retrieval, temporal, ast]
milestone: v5.1.0-language-ecosystem-expansion
blocked_by: []
related: []
---

# Temporal filtering and hybrid AST-lexical retrieval for along kb-search

Upgrade `along kb-search` with temporal recency weighting, milestone scoping, and 1-hop AST symbol graph expansion to enable multi-strategy retrieval without heavy vector databases.

## Context and Problem Statement
Currently, `along kb-search` searches across `docs/` and `.along/` primarily using keyword matching and frontmatter index lookups. While fast and lightweight, it faces two significant limitations:
1. **Lack of temporal awareness**: An outdated ADR or historical session from two years ago ranks with the same weight as an active architectural decision or recent implementation session, causing agents to retrieve deprecated patterns.
2. **Disconnected structural context**: Searching for a code symbol, interface, or error code requires separate manual steps to discover which ADRs, issues, or blast-radius callers are associated with that symbol.

By adopting Hindsight's principles of temporal filtering and multi-strategy retrieval, but implementing them purely through local files, ripgrep, and existing AST code graphs, Along achieves high-precision retrieval without external PostgreSQL or vector database infrastructure.

## Requirements
- REQ-1: Temporal Filtering: `along kb-search` MUST support `--since <window>` (e.g., `30d`, `6m`, `YYYY-MM-DD`) to restrict results to sessions, decisions, and issues updated within the specified time window.
- REQ-2: Recency Weighting: Support a `--recent` flag that applies a time-decay ranking multiplier, prioritizing newer ADRs and recent session traces over older ones when keyword relevance scores are comparable.
- REQ-3: Milestone Scoping: Support a `--milestone <slug>` parameter to constrain entity search to issues, sessions, and decisions attached to a designated milestone.
- REQ-4: Hybrid AST-Symbol Expansion: When a query matches a known code symbol (function, class, module), `along kb-search` MUST optionally traverse 1-hop relationships to surface connected ADRs, owning issues, and primary callers from the local code graph.
- REQ-5: Zero External Dependencies: All temporal calculation, keyword indexing, and graph traversal MUST execute strictly in-process using local filesystem artifacts and existing sqlite caches, requiring no external daemons or vector services.

## Acceptance Criteria
- [ ] `--since`, `--recent`, and `--milestone` options implemented in `scripts/along_kb_search.py` and CLI router
- [ ] Time-decay ranking algorithm integrated and tested against test fixtures
- [ ] 1-hop AST symbol expansion integrated using `alongkit.graph`
- [ ] `bench_kb_search.py` updated to verify retrieval latency remains within SLA (<150ms)
- [ ] Comprehensive unit tests added in `tests/test_alongkit.py`
