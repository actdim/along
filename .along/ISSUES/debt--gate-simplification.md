---
protocol: along
protocol_version: "4.4.16"
slug: gate-simplification
type: debt
status: open
priority: high
created: 2026-10-17
updated: 2026-10-17
agent: claude-code
tags: [gates, hooks, simplification, debt]
parent: feat--autonomous-multi-runtime-mvp
blocked_by: []
related: [feat--autonomous-gate-profile, debt--agents-md-core-slimming, debt--along-core-extras-split]
---

# Gate simplification: drop command classification, check by result at end of turn and commit

## Problem (measured 2026-10-17)

`hooks_audit.jsonl` in three repositories that use Along (along, public/dotnet, mempart):

| Repository | Gate events | `require_plan_approval` | of them "Inquiry Read-Only" |
| --- | --- | --- | --- |
| along | 1025 | 820 | 639 |
| dotnet + mempart | 2734 | 2403 | 2267 |
| Total | ~3760 | ~3220 (86%) | ~2900 (77%) |

- Ordinary read-only commands are "unclassified" and ask the user: `git`, `python`, `powershell`,
  `node`, `format-table`, `findstr`, `where-object`, `get-item`, `(get-childitem` (parser bug).
- `python` is classified destructive as a whole: a read-only analysis script is blocked, while a
  script that deletes files is not detected anyway.
- Agents loop on the same block: up to 94 identical blocks in one conversation.
- 53 of 276 closed issues in this repository are gate or hook fixes.
- The audit log does not record the command or path, so false positives cannot be measured.

Root cause: gates try to predict the harm of an arbitrary command from its text. That is not
decidable (any interpreter can write, delete or call the network). Isolation is handled by the
environment (ADR-2026-10-17--docker-isolation-now-gvisor-later); gates enforce process rules,
which are decidable from file paths and `git status`.

## Principles

1. Block only irreversible or expensive harm; do the rest automatically or log it.
2. Decide by facts that are known exactly: the target path of a write tool, a short list of
   explicit dangerous commands, and `git status` at the end of a turn or at commit.
3. Unknown command: allow and log. Never ask the user to classify tools.
4. A gate that demands a deterministic command runs it itself instead of blocking.
5. One-line messages with a stable code and exactly one fix command; no per-runtime prose.

## Changes

### Remove
- Tool-nature classification: `scripts/alongkit/hooks/toolnature.py`, the command lists in
  `shellparse.py`, `along tool classify|list|explain`. Supersedes `feat--tool-class-model`.
- Shell blocking in the "inquiry" phase (the 2900 events above).
- `circuit_breaker` (blocks every tool including diagnostics; tripped on command timeouts). Process
  hangs are handled by runner timeouts.
- `fast_retrieval` (forbids grep over `docs/` and `.along/`).

### Change
- `require_plan_approval`: before a write tool, check the target path (source file and no approved
  plan); for shell, check `git status` at the end of the turn (files changed and no approved plan:
  stop, offer approve or revert). In Claude Code, plan mode is the approval.
- `projection_sync_before_stop`: run `along issue sync` automatically in the stop hook.
- `test_before_stop`: doc-only changes do not require the full suite by default (`count_docs` opt-in).
- `cli_safety`: warning, not a block.
- `require_active_issue`: never fire on Along's own state files under `.along/`.
- Verify why `wrapped_work_uncommitted` (tier advisory) produced 63 deny decisions in other repositories.

### Move to one commit-time check (`along lint`, pre-commit and `along gates check`)
typography, code-fence-language, portable-links, stable-entry-point, windows-safe-filenames,
no-tracked-secrets, commit-no-ai-coauthor, anti-stub-injection. Remove their tags from AGENTS.md.

### Keep before the action (decided by path)
workspace_containment (write tools), projection_protection, rule_pack_protection, doc_manual_lock,
require_active_issue, entity_deletion_protection, entity_reference_integrity, subproject_boundary
(review its 26 blocks for false positives).

### Add: narrow deletion and history check
Explicit forms only: `rm -r`, `Remove-Item -Recurse`, `del /s`, `rd /s`, `git clean -f`,
`git reset --hard`, `git push --force`. Ask (interactive) or deny (autonomous) when the path is
outside the repository, empty or an unexpandable variable, or the target is untracked inside the
repository. Everything else passes. Scripts are out of reach by design; the container covers them.

### Observability
- Add a redacted `target` field (command or path) to `hooks_audit.jsonl`.
- `along gates stats` shows repeated identical blocks per conversation (loop indicator).

### Configuration
Mode resolution today has five layers (tier, state layer, profile, default modes, env). Reduce to:
catalogue default, repository override, profile (`interactive` | `autonomous`).

### Gate budget
At most about 12 runtime gates. A new gate needs: the problem observed at least twice, not
catchable at commit, replaces or merges an existing gate, adds no lines to AGENTS.md.

## Acceptance Criteria
- [ ] Tool-nature classifier and `along tool` removed; `feat--tool-class-model` closed as superseded.
- [ ] Read-only shell commands produce zero gate events in an unapproved session.
- [ ] Shell file changes without an approved plan are caught at the end of the turn by `git status`.
- [ ] `circuit_breaker` and `fast_retrieval` removed with their tests.
- [ ] Projection sync runs automatically at stop.
- [ ] Commit-time lint covers the moved gates; their runtime hooks removed.
- [ ] Narrow deletion check covers the listed forms with tests for inside, outside, untracked and empty-variable paths.
- [ ] Audit log records a redacted target; stats show loops.
- [ ] Re-measured on a normal week of work: `require_plan_approval` events down by at least 80%.
- [ ] Automated tests passing.
