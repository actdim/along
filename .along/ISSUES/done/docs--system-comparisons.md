---
protocol: along
protocol_version: "4.4.10"
slug: system-comparisons
type: docs
status: done
completed: 2026-11-13
priority: medium
created: 2026-10-12
updated: 2026-11-13
agent: antigravity
tags: [docs, comparisons]
blocked_by: []
related: [docs--kb-search-docs-accuracy]
---

# Add neutral tool comparison table to system comparisons

Original scope (done 2026-10-12): add a neutral tool comparison table to `docs/topic--system-comparisons.md`.

Reopened 2026-11-13 as the `doc-manual-lock` key for `docs/topic--system-comparisons.md` (`write_policy: manual`), to carry the comparison-topic part of docs--kb-search-docs-accuracy. Two statements contradict the rest of the KB:
- The "LLM-Wiki Paradigm" bullet says Along "fully embraced" Karpathy's LLM-Wiki, while `docs/topic--llm-wiki-architecture.md` rejects the naive LLM-Wiki model in favor of authored, topic-based docs.
- The neural System-1 critique calls ~1 s per search unacceptably slow, while a cold `along kb-search` call measures about the same (corpus load ~0.8 s plus ~0.25 s query, `scripts/bench_kb_search.py`).

## Requirements
- REQ-1: `docs/topic--system-comparisons.md` MUST describe Along's relation to Karpathy's LLM-Wiki consistently with `docs/topic--llm-wiki-architecture.md` and link to it.
- REQ-2: `docs/topic--system-comparisons.md` MUST NOT claim a latency advantage over ~1 s neural retrieval that the kb-search benchmark does not support.

## Acceptance Criteria
- [x] Neutral tool comparison table present (original scope, 2026-10-12).
- [x] The LLM-Wiki bullet states adoption of the idea as deterministic topic-based docs and links the architecture topic.
- [x] The latency argument rests on determinism and no model inference, citing `scripts/bench_kb_search.py`.
- [x] `along kb-sync --strict` passes.
