---
protocol: along
protocol_version: "4.4.5"
slug: tool-class-model
type: feat
status: superseded
completed: 2026-10-17
priority: high
created: 2026-10-05
updated: 2026-10-17
agent: claude-code
tags: [hooks, gates, config]
milestone: v4.6.0-structured-state-and-blackboard-engine
blocked_by: []
related: []
superseded_by: debt--gate-simplification
---

# Tool classes and data-driven rules replace shellparse lists; plan gate decides by class

Superseded on 2026-10-17 by `debt--gate-simplification` before any work started. Classifying
arbitrary commands by tool class cannot decide harm (any interpreter can write or delete), so the
classifier is removed instead of refined: gates decide by write-tool path, a short list of explicit
dangerous commands, and `git status` at the end of a turn and at commit.

## Acceptance Criteria
- [x] Not implemented; replaced by `debt--gate-simplification`.
