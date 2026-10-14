---
protocol: along
protocol_version: "4.4.12"
slug: doc-routing-compliance-gate
type: feat
status: done
completed: 2026-10-14
priority: medium
created: 2026-10-14
updated: 2026-10-14
agent: antigravity
tags: [gates, docs, kb-sync, routing]
blocked_by: []
related: []
---

# Enforce Documentation Routing Tree via gate and kb sync checks

## Problem Statement
The Along Protocol defines a strict Documentation Routing Tree:
- Architectural choice / trade-off -> .along/DECISIONS/ (ADR)
- Public overview / pitch / landing page -> README.md
- Technical interface contract / CLI spec -> docs/topic--<slug>.md (type: reference)
- Conceptual explanation / comparison / philosophy -> docs/topic--<slug>.md (type: explanation, write_policy: manual)
- Procedural walkthrough / runbook -> docs/topic--<slug>.md (type: guide)

However, there is currently no gate or static validation enforcing this boundary. As a result:
- Agents or developers frequently place hundreds of lines of technical reference rules, coding conventions, or component models directly into README.md or AGENTS.md instead of creating modular topic articles in docs/.
- AGENTS.md files end up referencing README.md for conventions rather than the Knowledge Base (docs/).
- along kb sync does not check for oversized or misplaced reference content in README.md.

## Requirements
1. Gate `[gate: doc-routing-compliance]`:
   - Inspect writes to `README.md` and ensure they do not exceed reasonable overview length when containing technical reference blocks, coding conventions, or deep code fences (>50 lines of technical rule specifications).
   - Require reference material and interface contracts to reside in `docs/topic--<slug>.md`.
2. Static inspection in `along kb sync`:
   - Add a check in `along kb sync` / `along doctor` to detect reference bloat in README.md across workspace and subprojects.
   - Verify that AGENTS.md files reference topics under `docs/` rather than treating README.md as the conventions source of truth.

## Acceptance Criteria
- [x] Implement `doc_routing_compliance` check in `scripts/alongkit/hooks/` or `along kb sync`.
- [x] Add diagnostic warning or enforcement when README.md contains detailed rule-pack / reference conventions that belong in `docs/topic--*.md`.
- [x] Ensure hermetic tests verify the gate behavior on oversized README files and valid topic references.
