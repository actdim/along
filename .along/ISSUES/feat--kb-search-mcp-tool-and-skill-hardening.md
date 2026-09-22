---
protocol: along
protocol_version: "3.9.3"
slug: kb-search-mcp-tool-and-skill-hardening
type: feat
status: open
priority: high
created: 2026-09-21
updated: 2026-09-21
agent: antigravity
tags: [kb-search, mcp, skills, performance, token-hygiene]
milestone: v4.1.0-code-intelligence-and-mcp-ecosystem
blocked_by: []
related: [debt--kb-search-ranking-and-snippet-quality, feat--code-review-graph-user-skills]
---

# Hardening along-kb-search Skill and Exporting KB Search as Native MCP Tool

## Problem Description

When users or subagents invoke `/along-kb-search` in target repositories, LLM agents frequently experience severe execution latency (15-30+ seconds), characterized by lengthy reasoning loops where the agent opens, reads, and greps individual Markdown files across `docs/` and `.along/` manually.

This occurs because:
1. **Ambiguous Skill Directives**: The instruction in `skills/along-kb-search/SKILL.md` explains the concept ("agents invoke /along-kb-search to retrieve concise snippets") but lacks strict negative constraints forbidding agents from manually inspecting files when fulfilling search queries.
2. **Missing Native MCP Tool**: Currently, Along's KB search is only accessible via shell CLI (`along kb-search "<query>"` or `python scripts/along_kb_search.py`). In agent environments where shell execution is constrained, slow, or requires user confirmation, agents fall back to autonomous file reading.
3. **Execution Path Friction**: The in-memory Python search engine (`scripts/along_kb_search.py`) takes only 40-70ms to execute, but agents do not reliably treat it as a mandatory single-shot command.

## Required Changes

### 1. Skill Contract Hardening (`skills/along-kb-search/SKILL.md`)
- **Explicit Anti-Inspection Gate**: Add an unequivocal rule: "Agents MUST NOT use file-reading tools (`view_file`, `grep_search`, `find_by_name`, `list_dir`) to search knowledge base or issues manually. They MUST execute the deterministic search tool in a single command."
- **Deterministic Invocation**: Specify the exact command invocation:
  ```bash
  along kb-search "<query>" [--category <cat>] [--limit <N>] [--any] [--prefix]
  ```
  With fallback to direct Python execution if `along` is not in `PATH`:
  ```bash
  python ~/.along/bin/along_exec.py kb-search "<query>"
  ```
- **Direct Output Relay**: Require the agent to output the CLI result verbatim or concisely formatted without multi-step speculative thinking.

### 2. Native MCP Tool Implementation (`along_kb_search`)
- Implement an MCP tool endpoint in Along's MCP infrastructure (`scripts/along_mcp_server.py` or equivalent):
  - **Tool Name**: `along_kb_search`
  - **Description**: Fast, deterministic full-text and entity retrieval across `docs/` and `.along/` memory artifacts (<100ms).
  - **Schema**:
    - `query` (string, required): Search query or quoted phrase.
    - `category` (string, optional, enum: `["all", "kb", "issue", "decision", "milestone", "risk", "spike", "session"]`): Filter by scope.
    - `limit` (integer, optional, default: 8): Maximum matching passages to return.
    - `tag` (string, optional): Filter by tag.
    - `any` (boolean, optional): Match ANY query term (OR semantics, default is AND).
    - `prefix` (boolean, optional): Match word prefixes.
    - `repo_root` (string, optional): Target repository root path.
- Enable direct JSON-RPC invocation without spawning shell subshells.

### 3. Installer & Configuration Integration
- Update `scripts/configure_mcp.py` and `scripts/alongkit/install.py` to register the Along MCP server/tools alongside `code-review-graph` across all supported runtimes (Antigravity, Claude Code, OpenAI Codex, OpenCode).

### 4. Automated Tests & Quality Gates
- Add contract tests in `tests/test_kb_search.py` verifying:
  - Tool schema validity and JSON-RPC execution.
  - Sub-100ms response latency on the full repository corpus.
  - Zero filesystem side effects during retrieval.

## Acceptance Criteria
- `/along-kb-search` executes in a single round-trip without intermediate LLM file reads.
- Agents with MCP support call `along_kb_search` directly via RPC.
- All tests pass cleanly under `python .along/scripts/test.py`.
