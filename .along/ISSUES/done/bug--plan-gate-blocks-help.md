---
protocol: along
protocol_version: "4.4.6"
slug: plan-gate-blocks-help
type: bug
status: done
completed: 2026-10-09
priority: medium
created: 2026-10-07
updated: 2026-10-09
agent: claude
tags: [gates, shellparse, cli]
milestone: v4.5.0-multi-user-merge-automation
blocked_by: []
related: [bug--subcommand-help-as-argument, bug--inquiry-readonly-commands-blocked]
---

# --help of mutating commands blocked by the plan gate

## Problem

Without an approved plan, `require-plan-approval` rejected (2026-10-07):

```bash
along commit --help
python scripts/along_commit.py --help
```

Asking for usage is read-only, but `shellparse` classifies by subcommand only, so a mutating
subcommand with `--help` / `-h` counts as a mutation. The agent cannot learn the flags of
`along commit` before its plan exists. Counterpart of the done
`bug--subcommand-help-as-argument` (parser side); this is the classifier side.

## Requirements

- REQ-1: An Along CLI invocation (any entry form: `along`, `along_exec.py`, `scripts/along_*.py`)
  whose arguments contain `--help` or `-h` is read-only.
- REQ-2: The engines guarantee it: `--help` never mutates (covered by the parser fix), with a
  test per subcommand.

## Acceptance Criteria
- [x] Hermetic tests: `along commit --help`, `along bump --help`, `python scripts/along_commit.py -h` pass the plan gate
- [x] Automated tests passing
