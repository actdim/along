---
protocol: along
protocol_version: "4.5.2"
slug: ci-fence-language-missing
type: bug
status: in-progress
priority: high
created: 2026-10-23
updated: 2026-10-23
agent: claude-code
tags: [ci, docs]
blocked_by: []
related: []
---

# CI gate fails: code fence without language in topic--autonomous-environment.md

CI run https://github.com/actdim/along/actions/runs/39935722047 fails in
`along gates check --ci --no-links`: `[gate: code-fence-language]
docs/topic--autonomous-environment.md:37: code fence without a language`. The bare fence
wraps the plain-text isolation diagram (added in ab51db5).

## Requirements
- REQ-1: The diagram fence at `docs/topic--autonomous-environment.md:37` MUST declare the `text` language.

## Acceptance Criteria
- [x] `python scripts/along_exec.py gates check --ci --no-links` reports no violations.
- [x] `python .along/scripts/test.py -q` is green.
