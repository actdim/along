---
protocol: along
protocol_version: "4.4.5"
slug: subcommand-help-as-argument
type: bug
status: done
completed: 2026-10-06
priority: high
created: 2026-10-05
updated: 2026-10-06
agent: claude-code
tags: [cli, help]
milestone: v4.5.0-multi-user-merge-automation
blocked_by: []
related: []
---

# Subcommand --help is taken as an argument (decision create makes ADR '--help')

`--help` is handled only at the top level of `along`. Subcommands treat it as an argument:

- `along decision create --help` created `.along/DECISIONS/ADR-2026-10-05----help.md` and
  recompiled `DECISIONS.md`, `CONSTRAINTS.md` and `docs/decisions/INDEX.md` (2026-10-05, a
  parallel session). After the ADR file was removed, the stale projections broke the link
  gate and aborted the v4.4.6 release until `along decision sync` ran.
- `along issue update --help` printed `[Error] Issue '--help' not found in .along/ISSUES/.`
- `along issue create --help` prints usage, but through the missing-arguments error path.
- `along scratch init --help` created a blackboard `.along/.session/--help/` (2026-10-06,
  session of `bug--commit-blocked-after-wrap`; removed by hand).

Not covered by [bug--cli-help-missing-subcommands], which fixed the router help listing.

## Acceptance Criteria
- [x] `-h` / `--help` anywhere after a subcommand prints that subcommand's usage, exits 0
      and writes nothing (all routers in `scripts/along_exec.py`)
- [x] Entity names starting with `-` are rejected by create/rename commands
- [x] Test sweeps every subcommand with `--help` against a hermetic fixture and asserts a clean
      tree
- [x] Automated tests passing

## Resolution
`main()` in `scripts/along_exec.py` checks every native router for `-h` / `--help` before a `--`
(`_wants_help`). `_print_router_help` captures that router's usage and prints the lines for the
named subcommand, or the full usage when it has none. `status` and `doctor` now have usage, and
`issue` lists usage for each subcommand. `_require_entity_name` exits 2 on names that start with
`-` in decision/milestone/session create, scratch, worktree create, start and issue rename.
`run`, `kb`, `graph`, tool engines and lifecycle hooks still pass `--help` through. Tests:
`tests/test_subcommand_help.py`.
