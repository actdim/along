---
protocol: along
protocol_version: 2.2.8
slug: kb-search-ranking-and-snippet-quality
type: debt
status: open
priority: medium
created: 2026-09-01
updated: 2026-09-01
agent: claude-code
tags: [kb-search, retrieval, ranking, snippets, token-efficiency]
milestone: v3.0.0-global-quality-revision
blocked_by: []
related: [always-on-context-budget-exceeds-claims, unpinned-mcp-and-ghost-wiki-query-tool, adr-retrieval-blind-to-slug-headers]
parent: protocol-quality-audit-remediation
---

# Retrieval quality does not support the token-efficiency claim

## Problem 1: scoring is naive substring counting

```python
# scripts/along_kb_search.py:246-259
for term in query_terms:
    if term in title_lower or term in slug_lower:
        score += 10.0
    for t in tags_lower:
        if term in t:
            score += 5.0
    matches = body_lower.count(term)
    if matches > 0:
        score += min(matches * 1.0, 10.0)
```

Properties of this scheme:

- Substring, not token, matching: querying `cat` matches `concatenate`, `category`,
  `duplicate`.
- No stemming or lemmatization: `decision` does not match `decisions`, `migrate` does not
  match `migration`. For a Russian-language or mixed-language repository the miss rate is
  higher still.
- No inverse document frequency: a term appearing in every document scores the same as a
  rare, discriminating term.
- No phrase support: a multi-word query is treated as independent terms with no adjacency
  requirement.
- `term_matches` is incremented by raw body occurrence counts, so a long document with many
  incidental hits outranks a short, precisely relevant one.
- Recency is ignored, while `status in [open, in-progress, active]` gets a flat `+2.0`.

## Problem 2: snippets waste the tokens the tool exists to save

```python
# scripts/along_kb_search.py:268-276
pos = body_lower.find(query_terms[0])
start = max(0, pos - 80)
end = min(len(e["body"]), pos + 150)
snippet = e["body"][start:end].replace("\n", " ").strip()
```

- Fixed character window with no word-boundary alignment, so output routinely begins
  mid-token. Real example from this repository:
  `"--token-refresh]`), never by copying internal history. ---  ## 4. Multi-Branch..."`
- Only the first query term is located; a snippet for a two-term query may not contain the
  second term at all.
- Markdown structure is flattened to a single line, so tables and code blocks become noise.
- One snippet per result, never the best of several passages.

## Problem 3: the claim is unsubstantiated

`README.md:19` advertises "95-98% token reduction on retrieval" and
`README.md:91` promises snippet search "(<100 tokens)". Nothing measures either number, and
there is no index: every query re-reads and re-scans every entity file in the repository
(`collect_all_entries` walks `docs/`, `ISSUES/`, `DECISIONS.md`, `MILESTONES/`, `RISKS/`,
`SPIKES/`, `SESSIONS/` on every invocation). Related: a closed issue claims vector indexing
was delivered when no such code exists
(`[debt--unpinned-mcp-and-ghost-wiki-query-tool]` Problem 3).

## Impact

Retrieval quality is the mechanism behind the product's central efficiency promise. Weak
ranking means agents fall back to reading whole files, which is exactly the behavior the
skill exists to prevent, and misleading snippets can send an agent to the wrong article.

## Requirements

- REQ-1: Replace substring scoring with token-based matching: tokenize on word boundaries,
  case-fold, apply light stemming for English, and match whole tokens with a prefix option.
- REQ-2: Add IDF-style weighting so discriminating terms dominate, and require all query
  terms (AND semantics) by default with an `--any` switch for OR.
- REQ-3: Support quoted phrase queries with adjacency.
- REQ-4: Rewrite snippet extraction: align to word and sentence boundaries, prefer a passage
  containing the most query terms, allow up to two passages, preserve inline code, and cap by
  token estimate rather than character count.
- REQ-5: Add a measurement mode (`--stats`) reporting result count, estimated tokens
  returned, and the size of the corpus scanned, so the published claims become verifiable and
  regression-testable. Coordinate with
  `[debt--always-on-context-budget-exceeds-claims]` REQ-1.
- REQ-6: Evaluate an optional on-disk index (for example SQLite FTS5, stdlib-adjacent and
  dependency-light) for repositories above a size threshold, and record the decision as an
  ADR. Note that a prior issue claimed this was delivered; that record must be corrected
  first.
- REQ-7: Build a small relevance fixture (a set of queries with expected top results drawn
  from this repository) and assert ranking quality in tests, so ranking changes are
  measurable rather than anecdotal.
- REQ-8: Align `README.md` claims with measured behavior.

## Acceptance Criteria

- [ ] Token-based ranking with IDF weighting and AND-by-default semantics.
- [ ] Snippets aligned to word boundaries and containing all matched terms where possible.
- [ ] `--stats` reports returned-token estimates.
- [ ] Relevance fixture test in place and green.
- [ ] Published retrieval claims match measurements.
- [ ] ADR recorded for the indexing decision.
