---
protocol: along
slug: code-review-graph-windows-ignore-hardening
type: task
status: done
completed: 2026-09-18
priority: high
created: 2026-09-15
updated: 2026-09-18
agent: antigravity
tags: [code-review-graph, windows, ignore, node_modules]
milestone: v2.0.0-along-transition
blocked_by: []
related: []
---

# Code Review Graph Windows Ignore Hardening

## Problem
On Windows, `code-review-graph` uses `PurePosixPath` to test nested directory ignore patterns,
which fails when file paths contain backslashes (`\`). Consequently, `packages\dashboard-ui\node_modules`
was not matched by `node_modules/**` unless wildcard patterns (`*node_modules*`) or `.code-review-graphignore`
are explicitly provided.

## Requirements
- Ensure both `.code-review-graph-ignore` and `.code-review-graphignore` are synchronized with `*node_modules*`.
- Rebuild graph from scratch and verify 0 node_modules files are indexed.
