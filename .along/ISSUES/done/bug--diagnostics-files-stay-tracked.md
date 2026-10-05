---
protocol: along
protocol_version: "4.4.5"
slug: diagnostics-files-stay-tracked
type: bug
status: done
completed: 2026-10-05
priority: medium
created: 2026-10-05
updated: 2026-10-05
agent: claude-code
tags: [git, gates, migration, diagnostics]
blocked_by: []
related: []
---

# Diagnostics files committed before the self-ignore stay tracked in git

`repo.ensure_diagnostics_dir` writes a `*` `.gitignore` into `.along/diagnostics/`, because
diagnostics are per-machine runtime state (hook audit, activity traces, heartbeat, circuit
breaker). A `.gitignore` does not affect files that are already tracked: repositories that
committed `hooks_audit.jsonl`, `activity_trace.json` or `circuit_breaker.json` before the
self-ignore existed keep tracking them. Every session then dirties the working tree, branches
conflict on these files, and the audit log publishes local paths of other projects the hooks saw.

This repository untracked its three files by hand (`git rm --cached`); other installations still
carry them, and nothing reports it.

## Requirements
- REQ-1: The `untracked-exports` gate (`repochecks.check_untracked_exports`, `default_gates.yaml`)
  also rejects tracked paths under `.along/diagnostics/` (any nested context), with a
  `git rm --cached` hint.
- REQ-2: A migration step untracks `.along/diagnostics/**` (`git rm --cached`, files stay on disk),
  idempotent, no-op outside git or when nothing is tracked.
- REQ-3: `along doctor` reports tracked diagnostics files.

## Acceptance Criteria
- [x] Hermetic test: a commit that adds or keeps `.along/diagnostics/hooks_audit.jsonl` is rejected by the gate; a nested `<sub>/.along/diagnostics/` file too; untracking passes (`tests/test_diagnostics_untracked.py`).
- [x] Hermetic test: the migration step untracks tracked diagnostics files, keeps them on disk, and a second run changes nothing; a repository already at the current version still runs it.
- [x] Docs: `docs/topic--cli-reference.md`, `docs/topic--migrations.md`, `docs/topic--declarative-gates-and-traceability.md`, AGENTS.md / `skills/along-init/protocol.md` rule line.
- [x] Automated tests passing (964)

## Notes
- REQ-1 needed no `default_gates.yaml` change: the handler is shared, only its check grew.
- Pre-commit passes only added/modified paths (`--diff-filter=ACMR`) to the check, so `git rm --cached` is never rejected; CI mode checks every tracked path.
