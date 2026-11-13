# Living Plan: system-comparisons

## Revision 1 (2026-11-13T16:36:59Z, ExitPlanMode (carried))

# Plan: docs--kb-search-docs-accuracy

Execution Mode: Direct (2 doc files, no code changes)

## Context
`docs/topic--llm-wiki-architecture.md` describes `along-kb-search` with numbers that no longer match the code. It also lacks two things: guidance on how topic structure drives search, and the progressive-disclosure ladder. `docs/topic--system-comparisons.md` contradicts the architecture topic on Karpathy's LLM-Wiki. Facts verified this session against `scripts/along_kb_search.py` and a fresh `scripts/bench_kb_search.py` run:

- Snippet: the best-scoring paragraph block (blank-line / heading delimited, front-matter skipped, fences kept whole), capped at 150 words (`extract_passage_location_and_snippet`). Not 230 chars / <100 tokens.
- Ranking (`search_knowledge_base`): title 15 x IDF (stem 7.5, prefix 6); slug 12 x IDF (stem 6, prefix 5); tags 10 x IDF (exact only); body min(TF x IDF, 25); quoted phrase +30 title / +20 slug / min(15 x count, 30) body; +2 active status; **+20 for `docs/` topics and `PROTOCOL.md`**; -10 archived. AND by default, `--any` = OR, `--prefix`. Literal mode: base 100, +50 slug, +30 title, min(10 x count, 30) body, +20 kb.
- IDF: smoothed `ln((N+1)/(df+1)) + 1` over title + slug + tags + body, stems counted too (`compute_idf`). Stemmer is English-only (`light_stem`).
- Latency on this repo: 837 entities, corpus load ~0.8 s, in-memory query p50 ~245 ms. 1,000-entity fixture p95 ~168 ms against the <250 ms target from ADR-2026-09-09. Token savings: 95-98% against the matched documents, >99% against the whole corpus. So "sub-millisecond" and "under 50ms" are wrong.

## Changes

### 1. `docs/topic--llm-wiki-architecture.md`
- Front-matter: bump `updated`, add tags `progressive-disclosure`, `authoring`; add `scripts/along_kb_search.py` to `sources` (kb-sync fills the hash).
- Section 1 bullet (line 47) and mermaid node (line 78): replace "Sub-Millisecond", "230-character", "< 100 Tokens" with "best paragraph, <= 150 words".
- Section 3: fix the "Zero Native Dependencies & Zero Latency" timing claim. Rewrite the scoring table with the weights above, including stem/prefix tiers, the +20 curated boost and the -10 archive penalty. Add short sub-blocks for query semantics (AND / `--any` / `--prefix` / quoted phrase / literal mode), the IDF formula, how the snippet is chosen, and benchmark numbers that cite `scripts/bench_kb_search.py`. Make savings figures say what they are measured against.
- New section "Authoring Topics for Retrieval". A table that maps each structure rule to the search signal it produces: one topic per file -> clean df / high IDF; title / slug -> strongest weights; tags -> exact-match synonyms (single-word tags; multi-word tags only match whole); `##` headings + short paragraphs -> snippet = one paragraph, with section and line range; backticked exact identifiers -> exact lexical match; English body text -> stemming works. Plus a short checklist for authors.
- New section "Progressive Disclosure Ladder": INDEX.md -> front-matter -> snippet -> surrounding lines -> full file. Expand the existing one-line bullet in section 3 into a pointer to it.
- Renumber the following sections (References becomes the last).

### 2. `docs/topic--system-comparisons.md` (`write_policy: manual`, allowed under this `docs--` issue)
- Line 83: reword to "adopted the interlinked, human-readable repository wiki idea from Karpathy's LLM-Wiki, but as authored, deterministic topic-based docs rather than an LLM-recompiled wiki", linking to the architecture topic.
- Line 63: keep the critique of neural memory drift, but drop the claim that ~1 s per search is unacceptable versus "local deterministic indexes". Our own CLI call is ~1 s cold (0.8 s load + 0.25 s query). Restate it as determinism and no model inference rather than raw speed.

## Verification
- `along kb-sync --strict` (links, INDEX.md, source hashes) and `--check-symbols` for the edited topics.
- `along lint` / `along sanitize` for ASCII typography.
- `python .along/scripts/test.py`.
- grep: no `230-char`, `< 100 Tokens`, `Sub-Millisecond` left in `docs/topic--llm-wiki-architecture.md`.
- `along kb-search "curated boost"` returns the new section.
- Then `along wrap kb-search-docs-accuracy --summary ... --no-decisions`. No commit unless asked.
