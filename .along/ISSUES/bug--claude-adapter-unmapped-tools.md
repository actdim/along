---
protocol: along
protocol_version: "4.2.0"
slug: claude-adapter-unmapped-tools
type: bug
status: open
priority: high
created: 2026-09-27
updated: 2026-09-27
agent: cowork
tags: [hooks, gates, claude-code, security]
milestone: v4.3.0-developer-experience-and-runtime-resilience
blocked_by: []
related: [bug--safe-command-prefix-bypass, feat--workspace-containment-and-path-scoping]
---

# Claude adapter leaves MultiEdit, NotebookEdit, Grep and Glob ungated

## Problem

`scripts/alongkit/hooks/adapters/claude.py` `TOOL_NAME_MAP` maps only `Write`, `Edit`, `Bash`, `PowerShell` and a few aliases. Claude Code also mutates files through `MultiEdit` and `NotebookEdit`, and searches through `Grep` and `Glob`. Unmapped tool names fall through as-is, and `check_mutation_authorization` explicitly allows unknown tools ("Other / unknown tools: do not block"). Result:

- every write gate (`require_active_issue`, `anti_stub_injection`, `typography`, `projection_protection`, `doc_manual_lock`, `subproject_boundary`, `require_plan_approval`) is bypassed by `MultiEdit`;
- `fast_retrieval` never fires under Claude Code.

## Evidence

Reproduced through `ClaudeCodeAdapter.parse` + `engine.evaluate_event` on a repo with no in-progress issue:

```text
Write     src/a.py -> DENY
MultiEdit src/a.py -> ALLOW
```

## Requirements

- REQ-1: Map `MultiEdit` and `NotebookEdit` to the canonical write tools, including argument normalization (`edits[].new_string`, `new_source`, `notebook_path`).
- REQ-2: Map `Grep` and `Glob` to the canonical search tools (`path`, `pattern` arguments).
- REQ-3: Fail closed: an unknown tool whose payload carries a file path plus content, or whose name matches a write/edit/patch pattern, is treated as a mutation; truly unknown tools are logged to `hooks_audit.jsonl` as `unmapped_tool`.
- REQ-4: Same audit for the Codex and Antigravity adapters.
- REQ-5: A contract test enumerates the documented tool names per runtime and asserts each is mapped or explicitly exempted.

## Acceptance Criteria

- [ ] `MultiEdit` and `NotebookEdit` on `src/` without an active issue are denied
- [ ] `Grep` over `docs/` triggers `fast_retrieval`
- [ ] Contract test for tool coverage exists for all adapters
- [ ] Automated tests passing
