---
protocol: along
protocol_version: "4.4.15"
slug: ste-cnl-specification-engine
type: feat
status: open
priority: medium
created: 2026-10-16
updated: 2026-10-17
agent: antigravity
tags: [ste, cnl, specifications, requirements, convention]
milestone: v5.0.0-agent-run-protocol-and-observability
parent: feat--autonomous-multi-runtime-mvp
blocked_by: []
related: [docs--ground-topic-based-docs, feat--cross-runtime-handoff-entities, debt--agents-md-core-slimming, debt--gate-simplification]
---

# Controlled Natural Language (STE-inspired) requirement format for cross-runtime handoff

## Goal

Make requirements unambiguous enough that a cheaper implementer model executes them literally,
using principles of Simplified Technical English (ASD-STE100) and Controlled Natural Language as a
writing convention, not as a gate.

## Re-scope (2026-10-17)

The original version proposed a runtime gate (`SteComplianceGate`), a passive-voice detector, a
lexical analysis module, `along ste-check` and `kb-sync --check-ste`. That repeats the pattern that
`debt--gate-simplification` removes: a new gate built on a heuristic with a high false-positive rate
(passive voice is not reliably detectable with regular expressions). Full ASD-STE100 compliance (a
controlled dictionary of about 900 approved words) is not realistic for a repository; the target is
"STE-inspired".

In the multi-runtime mode (`feat--autonomous-multi-runtime-mvp`) the value is real: a strong model
writes `REQ-N`, a cheap model implements them literally, and vague wording turns into review FAIL
loops. So the format becomes part of the handoff contract; the linter is deferred.

## Scope Now (MVP, convention only)

1. `REQ-N` pattern: `[Subject] + MUST | MUST NOT + [one verifiable action] + [object] + [condition]`.
   One observable, testable action per requirement. No `should`, `could`, `might`, `preferably`,
   `appropriate`, `various`, `as needed`, `etc.`.
2. The issue template (`along issue create` scaffold) shows the pattern in `## Requirements` instead
   of placeholder text.
3. The architect role writes requirements in this format; `along brief` passes them unchanged to the
   implementer and the reviewer (`feat--cross-runtime-handoff-entities`).
4. The same style (short imperative sentences) applies to the managed AGENTS.md block in
   `debt--agents-md-core-slimming`.
5. A short guide `docs/topic--requirement-format.md` (type: guide): pattern, banned words, three
   good and three bad examples.

## Deferred (only if data shows the need)

- Commit-time warning inside the shared `along lint` (`debt--gate-simplification`), limited to
  `## Requirements` and `## Acceptance Criteria`: banned-word list and sentence length. Never a
  runtime gate, never blocking.
- Trigger to start this work: review verdicts show repeated FAILs caused by misread requirements.
- Out of scope: passive-voice detection, controlled dictionary checks, `kb-sync` integration.

## Requirements

- `REQ-1`: The issue scaffold MUST show the `REQ-N` pattern in the `## Requirements` section.
- `REQ-2`: The architect role prompt MUST instruct the model to write requirements in the `REQ-N` pattern.
- `REQ-3`: `along brief` MUST pass the `## Requirements` section to the implementer and reviewer unchanged.
- `REQ-4`: The guide MUST list the banned words and give at least three good and three bad examples.
- `REQ-5`: Along MUST NOT add a runtime gate for requirement wording.

## Acceptance Criteria

- [ ] Issue scaffold updated with the `REQ-N` pattern.
- [ ] Architect role instructions reference the pattern.
- [ ] `docs/topic--requirement-format.md` published and indexed in `docs/INDEX.md`.
- [ ] Brief output contains the requirements verbatim (test in `feat--cross-runtime-handoff-entities`).
