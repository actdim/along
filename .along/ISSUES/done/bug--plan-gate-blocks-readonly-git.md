---
protocol: along
protocol_version: "4.4.5"
slug: plan-gate-blocks-readonly-git
type: bug
status: done
completed: 2026-10-05
priority: high
created: 2026-10-05
updated: 2026-10-05
agent: claude-code
tags: [hooks, gates, shellparse]
blocked_by: []
related: []
milestone: v4.5.0-multi-user-merge-automation
---

# Plan gate blocks read-only git commands (tag -l, ls-remote, for-each-ref, ...)

A plain question ("is the v4.4.5 tag pushed?") could not be answered: the
`require-plan-approval` gate (Inquiry Read-Only Invariance) denied `git tag -l "*4.4.5*"` and
`git ls-remote --tags origin`, although both only read.

## Facts
- `check_mutation_authorization()` in `scripts/alongkit/hooks/predicates.py` lets a shell
  command through only if `shellparse.is_read_only_command`, `is_along_state_command` or
  `is_verification_command` accept it.
- `_GIT_READ` in `scripts/alongkit/hooks/shellparse.py` allows only `status, diff, log,
  branch, show, rev-parse, describe`. Missing read-only forms include: `tag -l/--list` (and
  bare `git tag`), `ls-remote`, `for-each-ref`, `show-ref`, `ls-files`, `ls-tree`, `cat-file`,
  `rev-list`, `blame`, `shortlog`, `reflog` (show), `merge-base`, `grep`, `remote -v`,
  `config --get/--list`, `stash list`, `worktree list`, `name-rev`, `count-objects`.
- `git fetch` updates refs only, but is not read-only in the strict sense; decide separately.
- The PowerShell tool chain (`;`, `2>$null`) should be checked too.

## Acceptance Criteria
- [x] Listing forms of `git tag`, `git remote`, `git stash`, `git config` accepted; creating
      forms (`git tag v1`, `git tag -d`, `git remote add`, `git config k v`) still held
- [x] Pure read subcommands above added to the read-only classifier
- [x] Tests in the shellparse suite cover allowed and held forms
- [x] Automated tests passing (967 tests, 2026-10-05)

## Resolution
- `_GIT_READ` widened; new `_GIT_MODAL` set handled by `_git_modal_is_read_only` (`branch`,
  `tag`, `remote`, `stash`, `config`, `reflog`, `worktree`, `notes`: listing forms only).
- `_git_is_read_only` now gets the words in their original case: `-C <dir>` passes as a global
  option, `-c` (pager/alias injection) does not; `-O` (grep pager), `--upload-pack` and
  `--ext-diff` are held under any subcommand. `git fetch` stays held.
- Documented in `docs/topic--runtime-hooks-and-gates.md` (Read-only shell commands).
