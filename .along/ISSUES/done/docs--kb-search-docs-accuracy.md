---
protocol: along
protocol_version: "4.8.1"
slug: kb-search-docs-accuracy
type: docs
status: done
completed: 2026-11-13
priority: medium
created: 2026-11-13
updated: 2026-11-13
agent: claude-code
tags: [docs, kb-search, knowledge-base]
blocked_by: []
related: []
plan_status: approved
---

# Align KB search docs with along_kb_search.py and add authoring guidance

`docs/topic--llm-wiki-architecture.md` describes `along-kb-search` with figures that no longer match `scripts/along_kb_search.py`: it claims a 230-character / under-100-token snippet (the engine returns the best-scoring paragraph block capped at 150 words), a +15 phrase body weight (the engine adds `min(count * 15, 30)`), and both "sub-millisecond" and "under 50ms" latency (the benchmark target from ADR-2026-09-09 is under 250ms for 1,000 entities). It omits the +20 curated-docs boost, stem and prefix half-weights, AND-by-default semantics, the literal mode and the archive penalty. The KB also has no authoring guidance that explains how topic structure (title, slug, tags, headings, paragraphs) drives search ranking and snippet quality, and no explicit progressive-disclosure ladder. `docs/topic--system-comparisons.md` says Along "fully embraced" Karpathy's LLM-Wiki while the architecture topic positions itself against the naive LLM-Wiki.

## Requirements
- REQ-1: `docs/topic--llm-wiki-architecture.md` MUST state snippet size, scoring weights, query semantics and latency figures that match `scripts/along_kb_search.py` and `scripts/bench_kb_search.py`.
- REQ-2: `docs/topic--llm-wiki-architecture.md` MUST document the +20 curated-docs boost, stem/prefix weights, AND/`--any` semantics, literal mode and the archive penalty.
- REQ-3: `docs/topic--llm-wiki-architecture.md` MUST include an authoring section that maps each structure rule (one topic per file, title, slug, tags, headings, short paragraphs, backticked identifiers) to the search signal it produces.
- REQ-4: `docs/topic--llm-wiki-architecture.md` MUST describe the progressive-disclosure ladder (INDEX.md, front-matter, snippet, surrounding lines, full file).
- REQ-5: `docs/topic--system-comparisons.md` MUST describe Along's relation to Karpathy's LLM-Wiki consistently with the architecture topic.

## Acceptance Criteria
- [x] No "230-character", "< 100 tokens" or "sub-millisecond" claims remain in `docs/topic--llm-wiki-architecture.md`.
- [x] The scoring table lists every weight applied by `search_knowledge_base` in `scripts/along_kb_search.py`, with values matching the code.
- [x] An authoring section and a progressive-disclosure section exist with non-empty bodies.
- [x] `along kb-sync --strict` passes with no broken links.
- [x] `python .along/scripts/test.py` passes.
