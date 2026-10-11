---
protocol: along
protocol_version: "4.4.9"
slug: agents-md-budget-project-specifics
type: debt
status: done
completed: 2026-10-11
priority: low
created: 2026-10-11
updated: 2026-10-11
agent: claude-code
tags: [agents-md, context-budget]
milestone: v4.5.0-multi-user-merge-automation
blocked_by: []
related: [debt--agents-md-core-slimming, feat--bounded-prompt-footprint-gate]
parent: task--field-report-fixes
---

# AGENTS.md budget fails once Project specifics grows

Reported from field use (2026-10-11). Needs a decision (ADR).

## Problem

`along context-budget --check` constantly reports `agents_md_bytes` FAIL (limit 14336 B) in
consumer repos: the managed protocol block plus the "Project specifics" section quickly
exceed the limit, and the user cannot fix the managed part.

## Requirements

- REQ-1: Choose and record one option:
  - the limit counts only the managed block; "Project specifics" is budgeted separately;
  - the generator suggests moving "Project specifics" into `docs/topic--*.md` with a link;
  - the limit becomes configurable in `.along/config.json`.
- REQ-2: The FAIL message says which part is over budget and what the user can do.

## Acceptance Criteria
- [ ] ADR recorded
- [ ] Budget check implements the chosen option
- [ ] Automated tests passing
