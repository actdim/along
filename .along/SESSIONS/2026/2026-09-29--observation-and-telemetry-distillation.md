---
protocol: along
protocol_version: "4.4.1"
date: 2026-09-29
slug: observation-and-telemetry-distillation
agent: claude-code
branch: main
commit: 27c6642
summary: alongkit.distill + run_capture(distill=True); along test/build distil output for non-terminal callers, raw kept in .along/artifacts; spans record only the observation (uncommitted, per user)
issues_advanced: []
issues_completed: [feat--observation-and-telemetry-distillation]
decisions: []
risks_logged: []
spikes_conducted: []
milestone: v4.5.0-multi-user-merge-automation
---

# Session: Observation and telemetry distillation

## Summary

Third v4.5.0 task by priority, via `/along-team` (single-agent sequential, workspace:
inherit, no commits per user).

## Initial Implementation Plan (Baseline)

1. `alongkit/distill.py`: pure `distill()` (PASS one-liner + summary; failure blocks kept,
   noise dropped; 50 lines / 2 KB cap) (REQ-1).
2. `proc.run_capture(distill=True, distill_max_lines, distill_max_bytes)` ->
   `Result.observation`; tracer records the observation and force-offloads raw output (REQ-1, REQ-3).
3. `along test` / `along build`: `lifecycle.resolve_output_mode` + `run_lifecycle_command`
   (distil when stdout is not a TTY; `--raw` / `--distill` / `ALONG_OUTPUT`), raw log in
   `.along/artifacts/lifecycle/<action>.log` (REQ-2).
4. Tests, docs (`cli-reference`, `agent-run-protocol`), `.gitignore` for `.along/artifacts/`.

## Execution & Loop Trace (Fixes & Re-plans)

- Deviation from the issue: the full-output flag is `--raw`, not `--verbose`, because
  `--verbose` belongs to the wrapped runners (pytest, cargo) and is passed through.
- Default mode is TTY-aware: agents (pipes) get distilled output, humans in a terminal keep
  live streaming.
- Incident: the first distilled run used `run_capture`'s anomaly classifier, which read
  the string "bad signature" in test fixture output as index corruption and tripped the
  circuit breaker. Reset via `along circuit reset` (health probe passed, git index OK);
  lifecycle runs now pass `trip_on_anomaly=False`, matching passthrough behaviour.
- Fix loop 1: deprecation lines matched a `file.py:N` signal before the noise filter; the
  cap counted the header wrongly (51 > 50); summaries were swallowed into failure blocks
  and could be cut off. Chatter is now filtered first, summaries are reserved outside the
  cap, and Python 3.11 caret underlines are dropped.
- `.along/artifacts/` was not gitignored although the offloader already wrote there; added.
- Tool quirk recorded in memory: Write/Edit decode backslash-u escapes into literal
  characters (hit again in a regex); `chr()` is used instead.

## Verification Walkthrough & Gate Manifest

- `along test -q` (itself distilled now): 771 tests OK; the whole observation is 4 lines.
  A failing run earlier distilled 445 raw lines to about 13 lines containing the failing
  test, file/line, assertion and summary.
- Hermetic test asserts a >= 70% token reduction on a noisy unittest failure.

```text
Gate Execution Manifest:
- Workspace Isolation: EXECUTED (PASS) [mode: inherit (default)]
- File Integrity: EXECUTED (PASS)
- Automated Tests: EXECUTED (PASS) [along test -q, 771 OK]
- Diff Scope Audit: EXECUTED (PASS)
- Requirement Traceability: EXECUTED (PASS) [REQ-1..REQ-3]
- Blast Radius: DEGRADED (PASS) [static search: Result gained an optional field; record_command_result/maybe_offload gained optional params; lifecycle dispatch in along_exec]
- Documentation Parity: EXECUTED (PASS) [cli-reference, agent-run-protocol]
- Clean Typography: EXECUTED (PASS)
```
