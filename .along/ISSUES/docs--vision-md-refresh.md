---
protocol: along
protocol_version: "4.2.0"
slug: vision-md-refresh
type: docs
status: open
priority: low
created: 2026-09-27
updated: 2026-09-27
agent: cowork
tags: [docs, drift, vision]
milestone: v4.4.0-multi-user-merge-automation
blocked_by: []
related: [debt--constraints-superseded-adr-filtering, debt--along-core-extras-split]
---

# Refresh stale VISION.md scope and roadmap

## Problem

`.along/VISION.md` still describes the pre-v2 system: knowledge base in `.along/KB/`, compact entry point `CONTEXT.md` (deprecated), old skill names (`init-agents`, `wrap-session`, `/along-search-kb`, `/along-check-graph`), and leaves Phase 4 (dashboard) unchecked although the dashboard shipped. The file an agent reads for scope and non-goals contradicts the current architecture, in a product whose purpose is preventing documentation drift.

## Requirements

- REQ-1: Rewrite scope, non-goals and roadmap for v4.x using current names (`docs/` LLM-Wiki, `along kb-search`, 21 skills).
- REQ-2: Add explicit non-goals that bound the scope (see `debt--along-core-extras-split`).
- REQ-3: Add `sources:` provenance to VISION.md so `along kb-sync` drift detection covers it, or a check that every skill name mentioned exists in `skills/`.

## Acceptance Criteria

- [ ] No reference to `.along/KB/`, `CONTEXT.md` or pre-v2 skill names remains
- [ ] Automated tests passing
