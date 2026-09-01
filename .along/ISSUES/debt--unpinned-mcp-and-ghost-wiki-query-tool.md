---
protocol: along
protocol_version: 2.2.8
slug: unpinned-mcp-and-ghost-wiki-query-tool
type: debt
status: open
priority: high
created: 2026-09-01
updated: 2026-09-01
agent: claude-code
tags: [mcp, dependencies, supply-chain, ghost-capability, gates]
milestone: v3.0.0-global-quality-revision
blocked_by: []
related: [installer-parity-and-destructive-rules-overwrite, team-skill-uses-provider-specific-subagent-api]
parent: protocol-quality-audit-remediation
---

# Mandatory gates depend on an unpinned third-party MCP server and on a tool that does not exist

## Problem 1: a mandatory gate rests on an unavailable external server

`AGENTS.md` makes blast-radius analysis mandatory:

> Mandatory Agentic Code Review & Blast Radius Impact: agents MUST ... Use
> `code-review-graph` MCP tools (`build_or_update_graph_tool`, `get_impact_radius_tool`,
> `get_affected_flows_tool`) ...

The same requirement is repeated in `skills/along-wrap/SKILL.md:22` and in the mandatory
reviewer rubric of `skills/along-team/SKILL.md:71`.

That server is not part of this repository. The installers register it as:

```json
{ "command": "uvx", "args": ["code-review-graph"] }
```

- No version pin, so every session may resolve a different release: a reproducibility and
  supply-chain exposure for a tool granted repository-wide read access.
- During this audit the server failed to start: `code-review-graph (CONNECTION_CLOSED)`.
  A previous session log (`2026-08-31--code-review-graph-resilience-and-windows-mcp-optimization.md`)
  documents Windows stdio deadlocks in the same component, so this is a recurring condition.

A gate that cannot be executed cannot be mandatory. Today the failure is silent: the
protocol says MUST, the tool is absent, and nothing records that the check was skipped.

## Problem 2: `wiki_query` is instructed but does not exist

`AGENTS.md` instructs agents twice:

> Agents MUST query `/along-kb-search` or `wiki_query` for concise snippets ...
> Prioritize `along-kb-search` or `wiki_query` MCP tools for targeted searches ...

Nothing in the repository provides or configures a `wiki_query` tool. The only MCP the
installers register is `code-review-graph`. Agents are told to prefer a tool that is not
available anywhere, which wastes a discovery attempt per session.

## Problem 3: a closed issue claims a capability that was never built

`.along/ISSUES/done/feat--add-sqlite-vector-indexing.md` is `status: done`, with the body
stating "Superseded and completed via `integrate-wiki-llm-mcp`". A code search finds zero
occurrences of `sqlite`, `vector`, or `embedding` anywhere in `scripts/` or `dashboard/`.
`README.md:19` nonetheless advertises "95-98% token reduction on retrieval", and
`along_kb_search.py` implements naive substring scoring with no index (see
`[debt--kb-search-ranking-and-snippet-quality]`).

The entity log therefore records a delivered capability that does not exist. Two closed
issues (`feat--add-sqlite-vector-indexing`, `feat--integrate-wiki-llm-mcp`) point at each
other while neither has an implementation. This is a memory-integrity problem: the project's
own history misleads the next session.

## Requirements

- REQ-1: Pin the MCP dependency to an exact version (`uvx code-review-graph==X.Y.Z`) and
  record the pin in a single place consumed by both installers.
- REQ-2: Add a preflight check (`/along-graph-check`, or `along_exec.py doctor`) that reports
  whether each declared MCP server actually starts, with actionable output.
- REQ-3: Downgrade the wording of gates that depend on optional external tooling from MUST
  to "when available", and require the session log to record which gates ran and which were
  skipped and why. A skipped mandatory gate must be visible, not silent.
- REQ-4: Provide a fallback blast-radius procedure that uses only built-in search
  (symbol grep, import graph) so the gate degrades instead of disappearing.
- REQ-5: Remove `wiki_query` from `AGENTS.md` and `protocol.md`, or implement/configure the
  server that provides it. If retrieval stays native, say so consistently.
- REQ-6: Correct the entity record: reopen or supersede the vector-indexing and wiki-llm
  issues with an accurate status, and align the README retrieval claims with the actual
  implementation (coordinate with `[debt--always-on-context-budget-exceeds-claims]` REQ-7).
- REQ-7: Add a test that every MCP server name referenced in documentation is declared by
  the installers, and every tool name referenced in `AGENTS.md` is provided by a declared
  server or by a local skill.

## Acceptance Criteria

- [ ] MCP dependency pinned to an exact version in one place.
- [ ] Preflight check reports MCP availability.
- [ ] No documentation references a tool that nothing provides.
- [ ] Gate wording matches enforceability; skipped gates are recorded in session logs.
- [ ] Vector-indexing / wiki-llm entity records corrected.
- [ ] Documentation-to-capability test in place.
