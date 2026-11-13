---
protocol: along
protocol_version: "4.8.1"
slug: dita-topics-and-drift
type: docs
status: open
priority: medium
created: 2026-11-13
updated: 2026-11-13
agent: claude-code
tags: [docs, knowledge-base, provenance, dita]
blocked_by: []
related: [docs--kb-search-docs-accuracy, feat--provenance-drift-gate]
---

# Explain DITA self-contained topics and review the 11 stale provenance hashes

## Problem
Two gaps remain in the Knowledge Base after docs--kb-search-docs-accuracy.

1. **DITA topic granularity is not stated.** `docs/topic--llm-wiki-architecture.md` names IBM DITA and "one topic per file", but never says that a DITA topic is a complete, self-contained article on one subject, readable without the others, and not a small fragment. Readers who hear "wiki" assume a site chopped into tiny pages, and the doc does not correct that.

2. **11 provenance hashes are stale.** `along kb-sync --check` on 2026-11-13 reports `[DRIFT]` for these topic/source pairs:
   - `docs/topic--architecture.md`: `README.md`, `dashboard/app.py`
   - `docs/topic--domain-model.md`: `AGENTS.md`
   - `docs/topic--llm-wiki-architecture.md`: `skills/along-kb-sync/SKILL.md`, `scripts/along_kb_sync.py`
   - `docs/topic--migrations.md`: `scripts/migrate_protocol.py`
   - `docs/topic--setup-and-workflow.md`: `README.md`, `AGENTS.md`
   - `docs/topic--skills-reference.md`: `skills/along-init/SKILL.md`, `skills/along-kb-sync/SKILL.md`, `skills/along-update/SKILL.md`

   Each pair needs the topic checked against what changed in the source since the hash was recorded, the text corrected where facts changed, and the hash updated. feat--provenance-drift-gate adds `along kb-sync --drift-diff` and `--accept-drift`. Doing this after it lands avoids hand-computed hashes, but it is not a hard dependency.

## Requirements
- REQ-1: `docs/topic--llm-wiki-architecture.md` MUST contain a paragraph stating that a DITA topic is a complete, self-contained article on one subject, readable without other topics, and not a fragment.
- REQ-2: For each of the 11 listed topic/source pairs, the topic text MUST be checked against the source changes since the recorded hash and corrected where a described fact changed.
- REQ-3: After review, each of the 11 pairs MUST record the current source hash, so that `along kb-sync --check` reports no `[DRIFT]` for them.

## Acceptance Criteria
- [ ] The DITA paragraph exists in `docs/topic--llm-wiki-architecture.md` and is found by `along kb-search "self-contained topic"`.
- [ ] The session log lists, for each of the 11 pairs, whether the topic text changed or the source change had no doc impact.
- [ ] `along kb-sync --check` shows no `[DRIFT]` for the 11 listed pairs.
- [ ] `along kb-sync --strict` passes.
- [ ] `python .along/scripts/test.py` passes.
