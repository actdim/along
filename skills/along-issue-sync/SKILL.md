---
name: along-issue-sync
description: Reconcile the nearest .along/ issue board (ISSUES.md) and per-issue files (ISSUES/<type>--<slug>.md) for the target subproject/area - create/update issue files with status/priority and protocol: along in the nearest .along/, keep the board accurate, and move completed issues to ISSUES/done/. Use when invoking /along-issue-sync.
---

# Along Issue Sync  [v2.2.13]

Maintains `.along/ISSUES.md` and `.along/ISSUES/<type>--<slug>.md` files with strict YAML front-matter (`protocol: along`).

## Scope & Placement
- Always create and update issues in the **NEAREST** `.along/ISSUES/` folder corresponding to the subproject, module, or submodule being modified.
- Never dump subproject-specific issues into the root workspace board if that subproject has or should have its own `.along/` context.

## Usage
- Command: `/along-issue-sync`
