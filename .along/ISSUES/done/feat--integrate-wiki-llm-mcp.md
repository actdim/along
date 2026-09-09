---
protocol: along
slug: integrate-wiki-llm-mcp
type: feat
status: cancelled
priority: high
created: 2026-08-26
updated: 2026-08-26
completed: 2026-08-26
agent: antigravity
tags: [mcp]
milestone: v1.3.0-knowledge-base-and-graph
blocked_by: []
related: []
---

# Integrate WikiLLM MCP Server for Hybrid MD Documentation Search

> [!NOTE]
> Cancelled / Abandoned in favor of Along's native LLM-Wiki pipeline (`along-kb-sync` + `along-kb-search` over `docs/`).

## Goal
Integrate the [`NexusLayerEU/wiki-llm`](https://github.com/NexusLayerEU/wiki-llm) MCP server into the `Along` suite to provide agents with hybrid semantic search.

## Status
Cancelled / Superseded: third-party `wiki-llm` MCP integration was evaluated and discarded. Knowledge Base search is handled natively by `along_kb_search.py` without external MCP dependencies.

## Acceptance Criteria
- [x] Evaluated third-party wiki-llm MCP integration.
- [x] Decided against external MCP dependency in favor of native along-kb-search.
- [x] Removed ghost wiki_query references from AGENTS.md and protocol.

