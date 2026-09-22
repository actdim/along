---
protocol: along
protocol_version: "3.9.3"
slug: code-review-graph-user-skills
type: feat
status: open
priority: high
created: 2026-09-21
updated: 2026-09-21
agent: antigravity
tags: [code-review-graph, mcp, skills, blast-radius, architecture]
milestone: v4.1.0-code-intelligence-and-mcp-ecosystem
blocked_by: []
related: [feat--kb-search-mcp-tool-and-skill-hardening, bug--code-review-graph-resilience-and-windows-mcp-optimization]
---

# User-Facing Skills and Lifecycle Integration for code-review-graph MCP

## Problem Description

The repository integrates the `code-review-graph` MCP server (providing ~28 tools such as `get_impact_radius_tool`, `get_affected_flows_tool`, `get_architecture_overview_tool`, `get_hub_nodes_tool`, `get_bridge_nodes_tool`). However, currently only two maintenance skills exist:
- `along-graph-check`: Diagnoses server health and ignore filters.
- `along-graph-sync`: Builds or incrementally updates the AST graph.

There are no user-facing skills or slash commands that expose code intelligence to developers or enforce its usage during agent workflows. As a result:
1. **Zero User Discoverability**: Users cannot easily trigger graph analysis (e.g. asking "what breaks if I change this function?" or "show architecture hotspots") without constructing complex manual prompts.
2. **Agent Evasion & Naive Grep**: AI agents routinely bypass lazy-loaded MCP tools and fall back to naive text search (`grep_search`), missing transitive caller hierarchies, indirect interface implementations, and affected execution flows.
3. **Missing Lifecycle Enforcement**: Blast radius analysis is loosely documented in prose but lacks automated enforcement before closing issues or refactoring core engines.

## Required Changes

### 1. `along-graph-impact` Skill (`skills/along-graph-impact/SKILL.md`)
- **Command**: `/along-graph-impact <symbol|file>` or `along graph-impact <symbol|file>`
- **Intent**: Determine exact semantic blast radius before making modifications or completing work stages.
- **MCP Integration**:
  - Primary: Calls `get_impact_radius_tool` and `get_affected_flows_tool`.
  - Fallback: If MCP server is offline, falls back to static grep search with an explicit `[DEGRADED]` warning.
- **Output Report**:
  - Direct callers and callees.
  - Affected user flows and execution paths.
  - Candidate test files to run.
  - Affected documentation articles in `docs/topic--*.md`.

### 2. `along-graph-arch` Skill (`skills/along-graph-arch/SKILL.md`)
- **Command**: `/along-graph-arch` or `along graph-arch`
- **Intent**: High-level architectural overview, coupling hotspot detection, and dependency structure analysis.
- **MCP Integration**:
  - Calls `get_architecture_overview_tool` (structural communities and module layering).
  - Calls `get_hub_nodes_tool` (high-fan-in / high-fan-out symbols representing architectural coupling risks).
  - Calls `get_bridge_nodes_tool` (critical bottlenecks connecting disparate subsystems).
- **Output Report**:
  - Architectural community summary.
  - Top 5-10 hub nodes and refactoring recommendations.
  - Bridge nodes that represent single points of failure.

### 3. Lifecycle Hook Enforcement (`along-team` & `along-wrap`)
- Update `skills/along-team/SKILL.md` (Architect and Review phases) to require invoking `along-graph-impact` on all modified symbols.
- Update `skills/along-wrap/SKILL.md` (Step 3: Code Review) to mandate evaluating blast radius via `code-review-graph` before issue closure.

### 4. CLI Routing & Installer Parity
- Register `graph-impact` and `graph-arch` subcommands in `scripts/along_exec.py`.
- Include the new skills in `scripts/alongkit/install.py` manifest to ensure installation across all supported runtimes.

### 5. Automated Tests
- Contract tests in `tests/test_graph_skills.py` verifying:
  - Skill manifests adhere to YAML frontmatter schema.
  - CLI argument parsing and dispatching in `along_exec.py`.
  - Graceful degradation when `code-review-graph` is offline.

## Acceptance Criteria
- Developers can run `/along-graph-impact` and `/along-graph-arch` directly from agent chat.
- `along-team` and `along-wrap` systematically use the code graph for blast radius analysis.
- All tests pass with zero regressions under `python .along/scripts/test.py`.
