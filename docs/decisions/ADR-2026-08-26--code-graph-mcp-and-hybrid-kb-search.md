---
protocol: along
slug: code-graph-mcp-and-hybrid-kb-search
title: "Code Graph & Hybrid Knowledge Base Search MCP Integration"
date: 2026-08-26
status: accepted
tags: [adr, architecture, decision]
---

# ADR-2026-08-26--code-graph-mcp-and-hybrid-kb-search - Code Graph & Hybrid Knowledge Base Search MCP Integration

- Date: 2026-08-26
- Status: accepted
- Context: Agents need lightweight tools to inspect call hierarchies and search project documentation without loading massive raw files.
- Decision: Integrate `code-review-graph` for AST call graph analysis and impact radius, and `wiki-llm` / native hybrid search (`/along-search-kb`, `/along-sync-kb`) for document querying. Provide `/along-check-graph` and `/along-search-kb` debugging slash commands across all agent tools (Antigravity, Claude Code, Codex, OpenCode).
- Consequences: Agents prioritize MCP graph and hybrid search calls during research and refactoring, saving token overhead.
