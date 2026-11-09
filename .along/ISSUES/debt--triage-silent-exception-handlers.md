---
protocol: along
protocol_version: "4.7.0"
slug: triage-silent-exception-handlers
type: debt
status: open
priority: medium
created: 2026-11-09
updated: 2026-11-09
agent: antigravity
tags: [debt, exceptions, diagnostics, error-handling]
blocked_by: []
related: [task--domain-exceptions-and-error-flow]
---

# Triage Silent Exception Handlers Across Scripts

Audit and classify all silent exception catch blocks (`except ...: pass`) across `scripts/` to prevent silent corruption of state while preserving intentional fail-open behavior in hooks and optional feature checks.

## Context and Problem Statement

During the domain exceptions analysis (see `task--domain-exceptions-and-error-flow`), approximately 195 sites with `except ...: pass` or bare exception absorption were measured across `scripts/`. Some of these represent legitimate fallback patterns (e.g. non-critical metadata discovery, optional tools availability), but others risk masking corrupt Along-owned files or configuration errors without diagnostic records.

## Requirements

- REQ-1 (Classification): Audit all `except ...: pass` sites in `scripts/` and categorize them into:
  1. Intentional fail-open (hooks, optional tooling).
  2. Benign missing state (e.g. optional front-matter fields or missing transient caches).
  3. Corruption of Along-owned state (unparseable YAML, malformed JSON blackboards, damaged logs).
- REQ-2 (Diagnostic Logging): For corruption of Along-owned state, record diagnostic events via `DiagnosticsStore.record_incident`, deduplicated per component/path/mtime.
- REQ-3 (Fail-Open Hooks): Ensure runtime hooks maintain safe fail-open contracts while logging diagnostic notices.
- REQ-4 (Typography): Maintain 100% pure ASCII typography.

## Acceptance Criteria

- [ ] All `except ...: pass` locations in `scripts/` are audited and classified.
- [ ] Damaged or corrupt state is recorded to diagnostics instead of being silently swallowed.
- [ ] Hook fail-open behaviors remain protected by test coverage.
- [ ] Automated tests pass cleanly.

