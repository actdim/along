---
protocol: along
protocol_version: "4.4.4"
slug: containment-root-from-shell-cwd
type: bug
status: done
completed: 2026-10-05
priority: high
created: 2026-10-05
updated: 2026-10-05
agent: claude-code
tags: [hooks, containment, windows]
blocked_by: []
related: []
---

# Hook workspace root follows shell cwd into nested .along, containment asks on own repo

`scripts/along_hook.py` resolves the hook root as `repo.find_repo_root(event.workspace_root)`, and the
Claude adapter fills `workspace_root` from the payload `cwd`, which is the agent's *current shell cwd*
(it persists across Bash calls). After `cd src/apps/webapp` in `infomnia` (which carries its own
`.along/`), the hook root became `infomnia/src/apps/webapp`, so a Grep over the session's own project
root `infomnia` was reported as "Read outside the allowed scope" (ASK). Evidence:
`infomnia/src/apps/webapp/.along/diagnostics/hooks_audit.jsonl`.

The same root drives every gate (session binding, plan approval, subproject-boundary), so a `cd` into a
nested context also loses the session's binding at the project root. Nearest-context is a rule for
*where entities go*, decided by the target path (`subproject_context`), not a security boundary.

## Requirements
- REQ-1: The hook root is the session's project workspace, not the shell cwd: prefer
  `CLAUDE_PROJECT_DIR` (Claude Code) when it contains the cwd; otherwise keep the nearest root of the
  cwd. (An "outermost ancestor" climb was dropped: a session opened inside a subproject would then
  bind against the parent `.along/` and lose its own session binding.)
- REQ-2: Containment scope covers the whole project workspace; nested `.along/` contexts never narrow
  readable/writable scope.
- REQ-3: Subproject-boundary stays path-based (unchanged semantics) under the new root.

## Acceptance Criteria
- [x] Hermetic test: workspace with nested `sub/.along`, cwd inside `sub`, Grep at workspace root -> allowed.
- [x] Hermetic test: `CLAUDE_PROJECT_DIR` honored; cwd outside it keeps its nearest root; foreign repo still asks.
- [x] Existing hook/containment/subproject tests pass.
- [x] Automated tests passing (6 pre-existing env failures, identical on clean HEAD: missing `pydantic`, installer manifest tests)
