---
protocol: along
protocol_version: "4.4.2"
slug: rule-pack-protection-gate
type: feat
status: done
completed: 2026-10-01
priority: high
created: 2026-10-01
updated: 2026-10-01
agent: claude-code
tags: [gates, rules, integrity]
milestone: v4.5.0-multi-user-merge-automation
blocked_by: []
related: [feat--rule-packs-local-extensions, feat--test-gate-lifecycle-hook-only]
---

# Rule pack protection gate and `.along/scripts/` edits as source edits

## Problem
Managed rule packs in `.along/rules/*.md` are protected only when `along rules attach` runs:
an agent can still edit them through its write tools or a shell, and the edit survives until the
next attach. `attach_rules` also prunes an obsolete rule pack without a managed header even when its
body differs from the Along template, so local edits are deleted without a backup.

Separately, the activity trace treats every edit under `.along/` as a non-source edit, so changing
a repository lifecycle hook (`.along/scripts/test.py`, `build.py`, `bump_version.py`) does not
require a test run before the turn ends.

The done issue `feat--rule-packs-local-extensions` names an external consumer repository; that
reference does not belong in this repository.

## Requirements
- REQ-1: Runtime gate `rule_pack_protection` (PreToolUse, write tools) denies writes to
  `.along/rules/**/*.md` (any nesting level). `gates.yaml` / `gates.yml` stay writable. The message
  routes project guidelines to `docs/topic--*.md` or `AGENTS.md` "Project specifics" and names
  `along rules restore`.
- REQ-2: The same gate at the git/ci layer (`along gates check`): a staged or tracked
  `.along/rules/**/*.md` must carry the managed header and its body must match the header hash.
- REQ-3: `attach_rules` prunes an obsolete headerless rule pack only when it matches the Along
  template; otherwise it keeps it. `audit_rules` reports such a file as `modified_obsolete`.
- REQ-4: Edits under `.along/scripts/` count as source edits for `test_before_stop`.
- REQ-5: `[gate: rule-pack-protection]` documented in the managed protocol block (`AGENTS.md`) and in
  the rule/gate table of `docs/topic--runtime-hooks-and-gates.md`.
- REQ-6: Remove the external repository name from `feat--rule-packs-local-extensions`.

## Acceptance Criteria
- [x] Edit/Write to `.along/rules/platforms/web.md` is denied; `.along/rules/gates.yaml` is allowed
- [x] `along gates check` flags a modified managed rule pack
- [x] Obsolete modified headerless rule pack is retained by `attach_rules`
- [x] Editing `.along/scripts/test.py` triggers `test_before_stop`
- [x] Automated tests passing (874, `tests/test_rule_pack_protection.py`, `tests/test_rules.py`)

## Notes
- Shell writes are matched per command segment; a segment that names a rule pack and is not
  read-only is denied. Writes the shell parser cannot see (scripts that open the file themselves)
  are caught at the git/ci layer.
- Git history still carries the external repository name in older commits; removing it would
  need a history rewrite and is out of scope.
