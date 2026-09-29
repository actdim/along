---
protocol: along
protocol_version: "4.2.0"
slug: claude-adapter-unmapped-tools
type: bug
status: done
completed: 2026-09-27
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

- [x] `MultiEdit` and `NotebookEdit` on `src/` without an active issue are denied
- [x] `Grep` over `docs/` triggers `fast_retrieval`
- [x] Contract test for tool coverage exists for all adapters
- [x] Automated tests passing

## Resolution

- REQ-1/REQ-2: `adapters/claude.py` maps `MultiEdit`, `NotebookEdit` (to `replace_file_content`, with `edits[].new_string` / `new_source` / `notebook_path` normalized into `ReplacementContent` / `TargetFile`), `Grep` (`grep_search`) and `Glob` (`find_by_name`), plus the read-only tools (`Read`, `LS`, `WebFetch`, `WebSearch`, `TodoWrite`, `Task`, `Agent`, `ExitPlanMode`, `AskUserQuestion`). `EXEMPT_TOOLS` lists the rest.
- REQ-3/REQ-4: new `alongkit/hooks/adapters/normalize.py`; `HookEngine.evaluate` runs `normalize.fail_closed()` on every event from every adapter. Unknown tools that look like writes (name or path+content arguments) become `replace_file_content`; other unknown tools are allowed and written to `hooks_audit.jsonl` as `unmapped_tool`.
- REQ-5: `tests/test_hooks_tool_coverage.py` - documented Claude Code tools are mapped or exempt, every adapter map points at canonical names, and end-to-end DENY/ALLOW checks for MultiEdit, NotebookEdit, Grep, unknown writer and unknown reader.
- Verified: full suite via `.along/scripts/test.py -q` on Python 3.12, 686 tests OK (3 skipped); hook modules also on 3.10.
