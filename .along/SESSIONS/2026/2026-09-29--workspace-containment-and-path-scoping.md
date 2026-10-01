---
protocol: along
protocol_version: "4.4.1"
date: 2026-09-29
slug: workspace-containment-and-path-scoping
agent: claude-code
branch: main
commit: 27c6642
summary: workspace_containment gate (alongkit.hooks.containment) with read/write asymmetry, built-in whitelist, allowed_roots/write_scope from gates.yaml, issue frontmatter and along start flags; gate options and merged repo overrides in the declarative engine (uncommitted, per user)
issues_advanced: []
issues_completed: [feat--workspace-containment-and-path-scoping]
decisions: []
risks_logged: []
spikes_conducted: []
milestone: v4.5.0-multi-user-merge-automation
---

# Session: Workspace containment and path scoping

## Summary

Fourth v4.5.0 task by priority, single-agent sequential, workspace: inherit, no commits per user.

## Initial Implementation Plan (Baseline)

1. `alongkit/hooks/containment.py`: canonical paths (`realpath` + `normcase`), policy from
   defaults, gate options and in-progress issue frontmatter; per-tool path extraction
   (write / read / search incl. absolute glob base / shell `Cwd`) (REQ-1, REQ-2, REQ-3, REQ-5).
2. `predicates.check_workspace_containment`: write outside -> DENY, credential store -> DENY,
   read outside -> ASK (interactive) or DENY (autonomous) (REQ-6).
3. Declarative engine: non-definition keys become `options=` for predicates; a repo
   `gates.yaml` entry for a built-in gate is merged (so it can add options or `enabled: false`) (REQ-4).
4. `along start --allow-root/--write-scope` append to issue frontmatter (REQ-4).
5. Catalogue entry, prose badge in protocol/AGENTS.md, docs, tests.

## Execution & Loop Trace (Fixes & Re-plans)

- Additions beyond the issue text: `~/.claude/projects/` is writable (Claude Code project
  memory), `~/.along` is readable (installed engines), a git worktree's main checkout is
  readable, and extra credential stores (`~/.gnupg`, `~/.azure`, `~/.kube`, ...) are denied.
- Brain dir write access is limited to the current conversation id when the runtime sends one.
- Autonomous detection: Claude Code `permission_mode: bypassPermissions`, env
  `ALONG_AUTONOMOUS=1`, or `on_violation: deny`. The engine already converts ASK to DENY for
  every runtime except Antigravity, so Claude Code sees DENY with the reason either way.
- Shell commands are checked only by `Cwd` (as the issue specifies); absolute paths inside
  the command line are not parsed.
- Behaviour change: repo `gates.yaml` entries for built-in ids are now merged instead of
  replacing the gate; entries with their own `rule(s)` behave as before.
- `along hook verify` flagged the gate as undocumented until the protocol badge was added.

## Verification Walkthrough & Gate Manifest

- `along test -q`: 793 tests OK (22 new in `tests/test_workspace_containment.py`).
- `along hook verify`: PASSED (clean bi-directional contract).

```text
Gate Execution Manifest:
- Workspace Isolation: EXECUTED (PASS) [mode: inherit (default)]
- File Integrity: EXECUTED (PASS)
- Automated Tests: EXECUTED (PASS) [along test -q, 793 OK]
- Diff Scope Audit: EXECUTED (PASS)
- Requirement Traceability: EXECUTED (PASS) [REQ-1..REQ-6]
- Blast Radius: DEGRADED (PASS) [static search: get_all_declarative_gates merge semantics; predicates receive options= only when a gate declares options]
- Documentation Parity: EXECUTED (PASS) [declarative-gates, runtime-hooks, cli-reference, AGENTS.md/protocol.md]
- Clean Typography: EXECUTED (PASS)
```
