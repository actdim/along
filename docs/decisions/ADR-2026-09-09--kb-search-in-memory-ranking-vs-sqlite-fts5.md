---
protocol: along
slug: kb-search-in-memory-ranking-vs-sqlite-fts5
title: "In-Memory Word-Boundary Token Indexing and Ranking over SQLite FTS5"
date: 2026-09-09
status: accepted
tags: [adr, architecture, decision]
---

# ADR-2026-09-09--kb-search-in-memory-ranking-vs-sqlite-fts5 - In-Memory Word-Boundary Token Indexing and Ranking over SQLite FTS5

- Date: 2026-09-09
- Status: accepted
- Context:
  1. `[debt--kb-search-ranking-and-snippet-quality]` identified that substring matching and uniform TF scoring produced noisy retrieval, and requested evaluating an on-disk index (such as SQLite FTS5) vs in-memory scanning.
  2. Prior documentation loosely claimed indexing was present, while the implementation actually performed a fresh filesystem walk on each query.
  3. We measured the search latency and memory footprint across the real repository (~210 entities, ~160k tokens of prose):
     - Corpus scan and in-memory tokenization + smoothed IDF scoring executes in 40-70ms on standard developer hardware.
     - SQLite FTS5 would require persistent database files (`.along/.search.db`), database schema migrations, cache invalidation on Git branch switches or external file edits, and file-locking overhead on Windows NTFS.
- Decision:
  1. **Adopt In-Memory Word-Boundary Tokenization & Smoothed IDF Ranking**:
     - Tokenize on word boundaries, case-fold, and apply lightweight English suffix stemming without external dependencies.
     - Implement smoothed inverse document frequency (`math.log((N + 1) / (df + 1)) + 1.0`) so discriminative terms dominate.
     - Enforce AND semantics by default, with `--any` for OR queries.
     - Support quoted exact-phrase queries (`"..."`) with word-boundary adjacency.
     - Align snippet extraction to word boundaries centered on matched query terms.
     - Provide `--stats` flag for verifiable token efficiency reporting.
  2. **Defer SQLite FTS5**:
     - Maintain zero-dependency in-memory search for repositories up to 1,000 entities (< 250ms).
     - Defer SQLite FTS5 until corpus size exceeds 1,000 documents or query latency exceeds 500ms, avoiding on-disk state invalidation and Windows NTFS database locking risks.
- Consequences:
  - Eliminates false positives from substring matching (e.g. `cat` matching `concatenate`).
  - Zero on-disk cache invalidation or locking issues across Git branches.
  - Sub-100ms retrieval latency with measurable 99%+ token reduction when extracting targeted snippets.
