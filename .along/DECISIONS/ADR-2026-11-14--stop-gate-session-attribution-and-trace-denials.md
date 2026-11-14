---
protocol: along
slug: stop-gate-session-attribution-and-trace-denials
type: decision
title: "Stop Gate Session Attribution and Trace-Backed Denials"
date: 2026-11-14
status: accepted
tags: [adr, architecture, decision, gates, stop-gate, session-attribution, projections]
---

# ADR-2026-11-14--stop-gate-session-attribution-and-trace-denials - Stop Gate Session Attribution and Trace-Backed Denials

- Date: 2026-11-14
- Status: accepted
- Context: `require_plan_approval` at `Stop` previously evaluated working-tree changes globally across git status against turn baseline. This caused severe false positives in three areas: (1) compiled projections at any workspace depth (such as `packages/<pkg>/docs/INDEX.md` or `.along/ISSUES.md` generated during `along wrap` and `kb-sync`) were treated as unapproved source edits, (2) concurrent or foreign background writes were falsely attributed to the active turn, and (3) Stop-time gate denials could not be listed or acknowledged via `along gates ack` once session bindings were cleared or unbound. Additionally, legacy protocol prose claimed a 1-line typo exemption that contradicted mechanical gate enforcement.
- Decision: Compiled projections are non-plan-governed (`closeout.is_compiled_projection`). Index sync is idempotent. Wrap commits dynamically written projections. Stop gate counts session-attributed writes. Stop denials are recorded with deterministic IDs and ackable unbound. Removed 1-line exemption from protocol.
- Consequences: Eliminates Stop-gate false positives during wrap, multi-subproject builds, and concurrent tool runs while maintaining absolute zero-bypass safety on actual repository source changes.
