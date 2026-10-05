---
protocol: along
protocol_version: "4.4.4"
date: 2026-10-05
slug: readonly-classifier-pipelines
agent: claude-code
branch: main
commit: e2f3172
summary: Hook root anchored on CLAUDE_PROJECT_DIR instead of shell cwd; read-only shell classifier understands filters, sed/find reads, loops and substitutions
issues_advanced: []
issues_completed: [bug--containment-root-from-shell-cwd, bug--readonly-classifier-pipelines]
decisions: []
risks_logged: []
spikes_conducted: []
---

# Session: Containment root and read-only classifier

## Summary
- `bug--containment-root-from-shell-cwd`: a Claude session opened in `infomnia` got a
  workspace-containment ASK for a Grep over its own root. The hook resolved its root from the
  payload `cwd` (the agent's current shell cwd), which had followed `cd` into
  `src/apps/webapp/` with its own `.along/`. New `repo.find_session_root(cwd, project_dir)`;
  `along_hook.py` passes `CLAUDE_PROJECT_DIR`, and the project root wins whenever the cwd lies
  inside it. Relative paths still resolve against the shell cwd. An "outermost `.along`" climb
  was considered and dropped (it would break sessions opened inside a subproject).
- `bug--readonly-classifier-pipelines`: `shellparse.is_read_only_command` now accepts pure
  filters (`cut`, `tr`, `nl`, `diff`, `cmp`, `comm`, `basename`, `dirname`, `realpath`, `du`,
  `df`, `test`, `[`), `sort` without `-o`, `uniq` with at most one file, `sed` without
  `-i`/`-f`/`w`/`W`/`e`, `find` without `-exec`/`-delete`/`-fprint*`, recursive classification
  of `$(...)` and backquotes, and shell keywords (`for ... in`, `do`, `done`, `if`, `then`,
  `else`, `fi`, `while`, braces).
- Docs: `docs/topic--runtime-hooks-and-gates.md`, `docs/topic--declarative-gates-and-traceability.md`.
- Tests: 5 new in `tests/test_hooks_claude.py`, 31 new cases in `tests/test_shell_classification.py`.
  Full suite passes under the repo `.venv` (wrap quality gate); with system Python 6 tests fail
  identically on clean HEAD (missing `pydantic`, installer manifest tests).
- Follow-up: the global install in `~/.along` still reports 4.4.4 (new entities got
  `protocol_version: "4.4.4"`); the fixes reach live hooks only after reinstalling/updating.

## Decisions
- None (confirmed at wrap: no architectural decisions).

## Blackboard Record

Execution mode: direct; plan revision 1; approved: true.
