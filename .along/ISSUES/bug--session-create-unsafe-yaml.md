---
protocol: along
protocol_version: "4.2.0"
slug: session-create-unsafe-yaml
type: bug
status: open
priority: high
created: 2026-09-27
updated: 2026-09-27
agent: cowork
tags: [sessions, yaml, provenance]
milestone: v4.3.0-developer-experience-and-runtime-resilience
blocked_by: []
related: [debt--along-exec-argparse-migration, bug--py310-fstring-syntax-error]
---

# session create emits unsafe YAML and a fabricated test attestation

## Problem

`handle_session_command` (`along session create`, `scripts/along_exec.py` around line 805-850) builds the session front-matter with f-strings instead of `alongkit.frontmatter` / `ruamel.yaml`:

1. `summary: {summary}` is unquoted - a summary containing `:`, `#`, `[`, a leading `-` or `*` produces invalid or silently different YAML.
2. `branch: main` is hard-coded regardless of the current branch or worktree.
3. `commit: pending` is never back-filled.
4. The generated body asserts `- Automated tests verified and passing.` under "Code Review & Blast Radius" even though nothing was verified. Session logs are the immutable audit trail, so this writes a false attestation into history.

## Requirements

- REQ-1: Serialize front-matter through `alongkit.frontmatter` (ruamel round-trip), same as issues and ADRs.
- REQ-2: `branch` comes from `git rev-parse --abbrev-ref HEAD` of the target repo (or worktree); `commit` from `HEAD` short SHA, or is omitted with an explicit `--commit` option.
- REQ-3: The body template contains only neutral placeholders; verification lines are written only from real evidence (e.g. the activity trace `last_test_time` and the exit code of the last `along test`), otherwise `- Tests: not run in this session.`.
- REQ-4: Regression tests with summaries containing `:`, `#`, quotes and non-ASCII text round-trip exactly.

## Acceptance Criteria

- [ ] Generated session files parse with `ruamel.yaml` for adversarial summaries
- [ ] No session template claims tests passed without evidence
- [ ] Automated tests passing
