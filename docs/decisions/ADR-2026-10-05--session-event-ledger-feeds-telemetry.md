---
protocol: along
slug: session-event-ledger-feeds-telemetry
type: decision
title: "Session Event Ledger Is the Source of Truth; Telemetry Is a Projection"
date: 2026-10-05
status: accepted
tags: [adr, architecture, decision, session, telemetry, observability]
---

# ADR-2026-10-05--session-event-ledger-feeds-telemetry - Session Event Ledger Is the Source of Truth; Telemetry Is a Projection

- Date: 2026-10-05
- Status: accepted
- Context: Two features record what an agent session did. feat--parallel-session-closeout needs a per-issue record of edits, test runs, plans and approvals to decide which files go into which commit; a lost event attributes a file to the wrong issue. feat--agent-run-protocol-and-observability (core done in feat--agent-run-protocol-core, scripts/alongkit/telemetry/) exports OpenTelemetry spans and is fail-open by contract: events may be dropped when the collector or the spool fails. Today the two capture paths are separate: the PostToolUse hook writes .along/diagnostics/activity/<key>.json via record_tool_activity, and along_hook.py adds span events only when a runner Tracer is active, so interactive sessions produce no telemetry at all. Building closeout on telemetry would make attribution lossy; building observability into the closeout ledger would drag LLM spans, token usage and redaction into it.
- Decision: One session event model and one capture point, two sinks with different guarantees. (1) A versioned session event record `{schema, ts, session, slug, kind, path, path_kind, ok}` (kind: edit, test, tool, plan, approve; path_kind: source, docs, state); field names follow scripts/alongkit/telemetry/conventions.py (along.issue.slug, along.session.*) instead of inventing new ones. (2) The PostToolUse hook is the single capture point: it appends the event to the durable session ledger first, then, when a Tracer is active, emits the same event as a span event (the existing branch in along_hook.py becomes this second step). (3) The ledger is the source of truth for attribution, readiness and closeout; it is durable, repo-local, and mirrored into the issue blackboard and the session log. (4) Telemetry is a projection of the ledger: it may lose events, never feeds closeout decisions, and a later adapter may replay ledger events into spans for sessions that ran without a runner. No generic event bus or subscriber mechanism is built now.
- Consequences: Closeout attribution does not depend on the fail-open telemetry pipeline. The observability epic inherits a stable event vocabulary and a capture point that already covers interactive sessions, without a schema migration. Ledger writes must not be fail-open for attribution: a failed write is reported (along doctor, closeout readiness marks the issue blocked) rather than silently ignored. The ledger schema carries a version field so the observability protocol can extend kinds without breaking closeout readers.
