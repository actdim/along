---
protocol: along
slug: decouple-code-review-graph-from-mcp-to-direct-cli
title: "Decouple code-review-graph from MCP to Direct CLI Execution"
date: 2026-09-27
status: accepted
tags: [adr, architecture, decision, code-intelligence, mcp]
supersedes: [code-graph-mcp-and-hybrid-kb-search]
---

# ADR-2026-09-27--decouple-code-review-graph-from-mcp-to-direct-cli - Decouple code-review-graph from MCP to Direct CLI Execution

- Date: 2026-09-27
- Status: accepted
- Supersedes: `ADR-2026-08-26--code-graph-mcp-and-hybrid-kb-search`
- Context:
  - `code-review-graph` was initially connected as an external MCP server to provide Tree-sitter AST call graph, impact radius, and community clustering analysis.
  - In real-world agent environments (particularly Antigravity IDE and Windows), invoking `code-review-graph` via the MCP JSON-RPC protocol caused severe operational friction:
    1. Security dialog interruptions: IDEs treat MCP calls as external RPC requests, triggering interactive user approval popups on every tool call even in auto-approve (YOLO) mode.
    2. Lazy-loading cognitive tax: Registering 30 tools as lazy forces the agent into a 2-step schema discovery cycle (`view_file` on JSON schema followed by `call_mcp_tool`), causing agents to avoid calling it in practice.
    3. Windows stdio IPC brittleness: Bidirectional JSON-RPC stdio pipes suffer from buffer stalls, timeout failures, and lock contention.
  - However, the underlying `code-review-graph` Python engine (executed via `uvx`) is fast, accurate, and multi-language capable.
- Decision:
  - Completely decouple `code-review-graph` from the MCP server registration layer across all providers.
  - Retain `code-review-graph` as the AST code intelligence engine, executed directly via command line through `along graph-impact`, `along graph-arch`, `along graph-sync`, and `along graph-check`.
  - The agent invokes these capabilities through the standard, auto-approved native `run_command` tool rather than `call_mcp_tool`.
  - Maintain resilient static search fallback (`degraded_static`) inside the CLI engines so that analysis never halts if `uvx` or external dependencies are missing.
  - Update all documentation across `docs/` and `skills/` to describe `code-review-graph` as a CLI-driven AST engine rather than an MCP daemon.
- Consequences:
  - Zero modal confirmation prompts during agent execution in YOLO mode.
  - Immediate single-turn execution via `run_command("along graph-impact ...")`.
  - Cleaner agent system prompt by removing 30 dead lazy MCP tool definitions.
  - Preserved multi-language Tree-sitter AST analysis without resident background daemon overhead.
