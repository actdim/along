---
protocol: along
protocol_version: "4.4.5"
date: 2026-10-05
slug: hook-activation-and-gate-deadlock
agent: claude-code
branch: main
commit: e81ba5c
summary: Hooks activate only on an Along context (no bare AGENTS.md), declared roots, diagnostics never create .along/, awk and verification commands pass the plan gate, edits counted on PostToolUse, unbound sessions fail open unless enforce_unbound
issues_advanced: []
issues_completed: [bug--hook-activation-and-gate-deadlock]
decisions: []
risks_logged: []
spikes_conducted: []
---

# Session: Hook activation and gate deadlock

## Summary
Field report from a consumer repository: the global hooks activated in a repository that never
adopted Along, created `.along/diagnostics/` wherever the session sat, treated that directory as a
subproject, rejected a read-only audit command, and deadlocked test-before-stop against
require-plan-approval.

- Activation (REQ-1, REQ-8): `along_hook.py` acts only on an Along context: a `.along/` (or legacy
  `.agents/` with Along state, `repo.LEGACY_STATE_ENTRIES`) holding more than hook runtime output
  (`repo.RUNTIME_ONLY_ENTRIES`), or a declared root. A bare `AGENTS.md` no longer activates. Without a
  context the hook exits before the dependency bootstrap; new `alongkit/hookpreflight.py` answers
  in-workspace Read/Grep/Glob without bootstrapping.
- Declared roots (REQ-2): `<!-- along-root: <dir> -->` in `AGENTS.md` (`repo.ROOT_POINTER_RE`) or
  `context_roots` in `~/.along/config.json`; state resolves to `<dir>/.along/`, gates still judge paths
  against the workspace.
- Diagnostics (REQ-3): written to the resolved state dir when it exists, else `~/.along/diagnostics/`
  (`repo.global_along_dir`); hooks never create a `.along/`, and a diagnostics-only `.along/` is never a
  subproject.
- Read-only classifier (REQ-4): `shellparse` accepts `awk` without `system()`, output redirection or
  pipes, `-i inplace` or `-f`.
- Verification commands (REQ-5): build, test, lint and typecheck commands (no `--fix` / format) pass the
  plan gate in every phase.
- test-before-stop (REQ-6): counts only edits that succeeded (PostToolUse) and test runs the gates
  allowed; silent while the circuit breaker blocks commands.
- Unbound sessions (REQ-7): require-plan-approval and test-before-stop fail open for sessions not bound
  to an issue unless `enforce_unbound: true`; this repository opts in via `.along/rules/gates.yaml`.
- Bootstrap: `ensure_deps(quiet=..., stdin_data=...)` keeps hook stderr clean and replays the consumed
  hook payload to the re-executed process.
- Docs: `docs/topic--runtime-hooks-and-gates.md`, `docs/topic--declarative-gates-and-traceability.md`,
  `.along/GLOSSARY.md`.
- Tests: new `tests/test_hook_activation.py` (REQ-1..REQ-8, positive and negative) plus adjusted gate,
  inquiry, binding and classifier tests. 953 pass from the system interpreter (the `along test` path).
- Committed by a follow-up session: this session wrapped without committing and without a recorded
  plan approval.

## Decisions
- None (confirmed at wrap: no architectural decisions).

## Blackboard Record

Execution mode: direct; plan revision 1; approved: false.
