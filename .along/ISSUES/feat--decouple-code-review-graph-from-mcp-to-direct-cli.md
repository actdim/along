---
protocol: along
slug: decouple-code-review-graph-from-mcp-to-direct-cli
type: feat
status: in-progress
priority: high
created: 2026-09-27
updated: 2026-09-27
agent: antigravity
tags: [code-intelligence, ast, code-review-graph, mcp-decoupling, cli, documentation]
milestone: v4.1.0-code-intelligence-and-mcp-ecosystem
blocked_by: []
related: [feat--code-review-graph-user-skills, feat--native-ast-blast-radius-analyzer]
---

# Decouple code-review-graph from MCP to Direct CLI Execution and Overhaul Documentation

## 1. Context and Problem Statement

`code-review-graph` provides Tree-sitter AST analysis, blast radius calculation, caller tracing, and community cluster detection. Originally, it was registered as an external MCP server across agent providers (Claude, Codex, Antigravity, OpenCode).

In practical agentic workflows, especially within Antigravity IDE and on Windows systems, this MCP architecture creates major friction:
1. **Interactive Security Interruption**: Even when running in autonomous / YOLO mode, the IDE treats `call_mcp_tool` as an external RPC call, spawning confirmation dialogs on each invocation and breaking the agent feedback loop.
2. **Lazy Loading Overhead**: Registering 30 tools as `Lazy` forces the agent to read JSON schemas before each tool invocation (`view_file` -> `call_mcp_tool`), discouraging models from utilizing code-graph intelligence.
3. **IPC Instability**: Stdio pipes on Windows frequently stall or timeout under heavy AST serialization.

Meanwhile, the Python engine itself (`code_review_graph` via `uvx`) performs quickly and reliably when executed as a direct CLI subcommand. Furthermore, `along` already implemented standalone CLI dispatchers (`along graph-impact`, `along graph-arch`, `along graph-sync`, `along graph-check`) with automatic fallback to static search (`degraded_static`).

## 2. Objectives and Scope

1. **Decouple from MCP Server Layer**:
   - Cease registering `code-review-graph` in `mcp_config.json` and installer manifests.
   - Clean up active IDE `mcp_config.json` to eliminate modal approval popups and purge 30 dead lazy tools from the agent prompt.
2. **Standardize on Direct CLI / Native Tool Execution**:
   - Agents invoke code intelligence via the native `run_command` tool running `along graph-impact`, `along graph-arch`, `along graph-sync`, and `along graph-check`.
   - Retain full Python/Tree-sitter capabilities via `uvx` while preserving resilient static fallbacks.
3. **Comprehensive Documentation Overhaul**:
   - Retain clear descriptions of the Tree-sitter AST architecture and capabilities, while completely replacing MCP server references with direct CLI / native tool execution instructions.
   - Update `docs/topic--architecture.md`, `docs/topic--skills-reference.md`, `docs/topic--llm-wiki-architecture.md`, `docs/topic--cli-reference.md`, `docs/topic--setup-and-workflow.md`, `README.md`, and `llms-full.txt`.
4. **Skills and Protocol Standardization**:
   - Update `skills/along-graph-impact/SKILL.md`, `skills/along-graph-arch/SKILL.md`, `skills/along-graph-check/SKILL.md`, and `skills/along-graph-sync/SKILL.md`.
   - Update `AGENTS.md` and `skills/along-init/protocol.md` review checklist to mandate `along graph-impact` via `run_command`.

## 3. Requirements

- REQ-1: Deprecate `code-review-graph` MCP server registration in `scripts/alongkit/install.py` and `scripts/configure_mcp.py`.
- REQ-2: Update `AGENTS.md` and `skills/along-init/protocol.md` review checklist from "evaluate blast radius via code-review-graph MCP" to "evaluate blast radius via along graph-impact (or static search fallback)".
- REQ-3: Rewrite all references in `docs/topic--*.md` that describe `code-review-graph` as an MCP server, establishing it as a CLI-driven AST intelligence engine executed via `along graph-*`.
- REQ-4: Update skills (`along-graph-impact`, `along-graph-arch`, `along-graph-check`, `along-graph-sync`) to reflect direct execution without MCP phrasing.
- REQ-5: Verify that all tests pass (`python .along/scripts/test.py`) and typography remains strictly clean ASCII (`along sanitize`).

## 4. Acceptance Criteria

- [ ] ADR `ADR-2026-09-27--decouple-code-review-graph-from-mcp-to-direct-cli.md` recorded and synced.
- [ ] Active issue registered and compiled in `.along/ISSUES.md`.
- [ ] No modal prompts when running graph impact or sync.
- [ ] Documentation clearly explains that `code-review-graph` is powered by Python/Tree-sitter/uvx directly via CLI.
- [ ] Full regression suite passes with 0 failures.
