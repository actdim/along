---
protocol: along
slug: add-sqlite-vector-indexing
type: feat
status: superseded
priority: high
created: 2026-08-13
updated: 2026-08-26
completed: 2026-08-26
agent: antigravity
tags: []
milestone: v1.3.0-knowledge-base-and-graph
blocked_by: []
related: []
superseded_by: feat--integrate-wiki-llm-mcp
---

# Add SQLite Vector Indexing MCP Server for Fast Issue & Context Search

> [!NOTE]
> Cancelled / Abandoned in favor of zero-external-dependency native retrieval in `along_kb_search.py`.

## Goal
Implement a local vector indexing system (e.g. SQLite + `sqlite-vec` or local embeddings) exposed as an **MCP (Model Context Protocol) Server**.

## Status
Cancelled / Superseded: evaluated and replaced by native lightweight Knowledge Base retrieval (`along-kb-search`). No external SQLite vector MCP server is shipped.

