---
protocol: along
slug: mandatory-code-review-and-blast-radius-impact-gate
title: "Mandatory Agentic Code Review & Blast Radius Impact Assessment Gate"
date: 2026-08-27
status: accepted
tags: [adr, architecture, decision]
---

# ADR-2026-08-27--mandatory-code-review-and-blast-radius-impact-gate - Mandatory Agentic Code Review & Blast Radius Impact Assessment Gate

- Date: 2026-08-27
- Status: accepted
- Context: Unchecked AI code modifications often introduce regression risks, silent broken callers, edge-case crashes, or unhandled nulls that accumulate unnoticed until runtime.
- Decision:
  1. Formalize a mandatory **Code Review & Blast Radius Assessment** gate in the ALONG-PROTOCOL and session wrap-up checklist.
  2. Mandate agents to inspect their own git diffs and trace blast radius across dependent modules using `code-review-graph` MCP tools (`build_or_update_graph_tool`, `get_impact_radius_tool`, `get_affected_flows_tool`) or AST analysis.
  3. Require verification of ADR conformance in `.along/DECISIONS.md`, null-safety, and edge-case handling.
  4. Document the code review findings and impact summary in the session log (`.along/SESSIONS/`).
- Consequences: Significantly reduced regression rate, improved long-term architectural health, and explicit accountability for multi-module impact.
