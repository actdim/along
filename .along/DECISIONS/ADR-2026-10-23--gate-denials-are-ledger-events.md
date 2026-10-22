---
protocol: along
slug: gate-denials-are-ledger-events
type: decision
title: "Gate Denials Are Ledger Events; Closing Requires Resolution or User-Verified Disclosure"
date: 2026-10-23
status: accepted
tags: [adr, architecture, decision]
---

# ADR-2026-10-23--gate-denials-are-ledger-events - Gate Denials Are Ledger Events; Closing Requires Resolution or User-Verified Disclosure

- Date: 2026-10-23
- Status: accepted
- Context: Agents denied by a pre-tool gate sometimes dropped the blocked sub-task, worked around it, closed the issue and reported success. Denials were only trace lines and audit entries, so nothing tied them to closeout. The issue proposed a separate gate_denials.jsonl and a new --bypass-denial flag.
- Decision: An enforced denial of a bound session's tool call is a deny event in the issue's event ledger (events.jsonl), once per gate and target while open. It settles by a resolve event (an allowed retry on the same target), by a later approve event for gates the catalogue marks denial: procedural (require_plan_approval, require_active_issue), or is disclosed by an ack event (along gates ack --note) that counts once the user has replied after it, the same rule as bypasses. A Stop gate unresolved_gate_denial holds turns with open denials of that turn; closeout, along wrap and along issue done (delivered statuses) refuse open denials and unverified acks. The only override is the existing --force-reason under bypass.guard(wrap-checks); no new flag and no separate denial file.
- Consequences: Reuses the ledger, closeout and bypass machinery, so denials appear in along session status and in the session log (Disclosed Gate Denials). Retry matching compares a digest of the raw target, so a workaround on a different target stays open by design and must be disclosed. Unbound sessions record nothing (no blackboard). Gates without a target (subagent payloads) collapse to one open denial per gate. An agent can ack on its own, but closing still waits for the user's next message.
