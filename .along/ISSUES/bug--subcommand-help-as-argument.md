---
protocol: along
protocol_version: "4.4.5"
slug: subcommand-help-as-argument
type: bug
status: open
priority: high
created: 2026-10-05
updated: 2026-10-05
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
- [ ] `-h` / `--help` anywhere after a subcommand prints that subcommand's usage, exits 0
      and writes nothing (all routers in `scripts/along_exec.py`)
- [ ] Entity names starting with `-` are rejected by create/rename commands
- [ ] Test sweeps every subcommand with `--help` against a hermetic fixture and asserts a clean
      tree
- [ ] Automated tests passing
