---
protocol: along
protocol_version: "4.4.5"
slug: tool-nature-classification
type: feat
status: open
priority: high
created: 2026-10-05
updated: 2026-10-05
agent: claude-code
tags: [hooks, gates, config]
milestone: v4.5.0-multi-user-merge-automation
blocked_by: []
related: []
---

# Classify unknown tools by nature (ask, record in config, act by class)

The plan gate decides on tools from a hardcoded list. That cannot scale: users install their
own CLIs and MCP servers, and they differ per agent and per machine.

## Current state (verified 2026-10-05)
- `predicates.check_mutation_authorization` inspects only shell tools and file-write tools.
  Any other tool (MCP servers, plugins, unknown agent tools) passes unchecked ("Other / unknown
  tools: do not block"), even if it writes or has external effects.
- Shell commands outside the built-in list in `alongkit/hooks/shellparse.py` are held before
  plan approval (`gh pr view`, `kubectl get`, `jq`, ...). The list cannot be extended by config;
  `default_gates.yaml` only exposes `enforce_unbound`.

## Design (agreed direction, 2026-10-05)
- Effect-based checks (diff the work tree after a call) are not the basis: they miss external
  side effects (push, deploy, API calls, messages). At most a safety net for workspace writes.
- REQ-1: An unknown command or tool is not silently allowed or denied. The gate holds it with a
  reason ("unclassified tool"); the agent asks the user for its nature, not for allow/deny,
  and records the answer through the CLI (e.g. `along tool classify "<pattern>" <class>`).
- REQ-2: Classes and their protocol rules:
  - `read-only` (inspect): allowed in every phase.
  - `verification` (build, test, lint): allowed in every phase (as today).
  - `workspace-write`: allowed after plan approval.
  - `external` (merge, deploy, push, send): after plan approval, and asked every time.
  - `destructive`: always asked.
- REQ-3: Granularity: command plus subcommand pattern (`gh pr view` vs `gh pr merge`); full tool
  name for MCP (`mcp__<server>__<tool>`).
- REQ-4: Layered storage, nearest wins: built-in defaults (today's `shellparse` lists become
  this layer), global user config under `~/.along/` (default target of `classify`), repository
  override in `.along/rules/gates.yaml`.
- REQ-5: Tool self-description (MCP `readOnlyHint` / `destructiveHint`) is only a suggested
  default in the question, never trusted on its own.
- REQ-6: Unknown agent tools (MCP etc.) go through the same flow, closing the current
  pass-through.

## Acceptance Criteria
- [ ] Class model and layered config implemented (built-in, global, repository)
- [ ] `along tool classify` / `along tool list` CLI
- [ ] Plan gate resolves shell commands and agent tools through the classification
- [ ] Unknown tools are held with a reason that tells the agent to ask for the class
- [ ] Docs: `docs/topic--runtime-hooks-and-gates.md`
- [ ] Automated tests passing
