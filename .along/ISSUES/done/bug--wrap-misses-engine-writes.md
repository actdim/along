---
protocol: along
protocol_version: "4.5.0"
slug: wrap-misses-engine-writes
type: bug
status: done
completed: 2026-10-19
priority: high
created: 2026-10-19
updated: 2026-10-19
agent: claude
tags: [wrap, closeout, migration, diagnostics]
blocked_by: []
related: [debt--agents-md-core-slimming, debt--gate-simplification]
---

# Wrap auto-commit misses engine-written files; migration leaves removed classifier/breaker leftovers

## Problem

1. `along wrap` auto-commits only the paths with edit events (recorded by the runtime hook on agent file tools) plus `closeout.PROJECTION_FILES`. Files the engine writes during the session (`along init` / `along update` refreshing the `AGENTS.md` managed block and `docs/topic--along-protocol.md`) have no edit event and are not projections, so they stay out. Seen on `debt--agents-md-core-slimming`: commit 856249a failed its own projection tests until c8244e0 added the two files by hand.
2. `debt--gate-simplification` (348766f) removed the circuit breaker and the tool-nature classifier, but no migration step cleans up what they left on disk:
   - `.along/diagnostics/circuit_breaker.json` and `.along/diagnostics/syntax_churn.json` (breaker state; nothing reads them).
   - `.along/tool_rules.yaml` (classifier rules; ignored).
   - a top-level `tools:` section in `.along/rules/gates.yaml` (ignored silently; repo-owned, so not rewritten).

## Requirements

- REQ-1: Wrap auto-commit includes `docs/topic--along-protocol.md` (fully managed) when dirty.
- REQ-2: Wrap auto-commit includes a dirty `AGENTS.md` (root or nested) when its only change against `HEAD` is inside the managed blocks (`ALONG-PROTOCOL`, `ALONG-RULES`). A change outside them (hand edits in Project specifics) keeps it out, as today.
- REQ-3: A migration step removes `circuit_breaker.json`, `syntax_churn.json` and `.along/tool_rules.yaml` through `Migration.discard` (backed up), and reports a leftover `tools:` section in `.along/rules/gates.yaml` without rewriting it. Idempotent.
- REQ-4: `.along/diagnostics/activity_trace.json` and `activity/` stay: they are still live (per-session traces, plus the shared fallback without a session key).

## Acceptance Criteria

- [x] Hermetic test: wrap commit includes a managed-only `AGENTS.md` change and `docs/topic--along-protocol.md`; an `AGENTS.md` with a Project specifics edit stays out (`tests/test_wrap_engine_writes.py`, which also covers nested `AGENTS.md`, CRLF-only changes and untracked files)
- [x] Hermetic test: the migration step discards the three leftovers with backup, reports `tools:` in gates.yaml, keeps the activity traces, is a no-op on a second run, and heals an up-to-date repository
- [x] `docs/topic--migrations.md` lists Step 15; `docs/topic--session-lifecycle.md` and `docs/topic--cli-reference.md` describe the managed-file rule
- [x] Automated tests passing (1430 OK)

## Notes

- Live repo: Step 15 removed `.along/diagnostics/circuit_breaker.json` (backup `.along/.migration-backup/2026-10-19-171540`). No `syntax_churn.json`, `tool_rules.yaml` or `tools:` section was present. The 69 per-session activity traces stay; they are not pruned (separate concern).
- `along session close` uses the same `managed_only_agents_changes` rule in its projections commit.
