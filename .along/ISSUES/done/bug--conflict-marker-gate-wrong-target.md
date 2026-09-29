---
protocol: along
protocol_version: "4.2.0"
slug: conflict-marker-gate-wrong-target
type: bug
status: done
completed: 2026-09-27
priority: medium
created: 2026-09-27
updated: 2026-09-27
agent: cowork
tags: [hooks, gates, git]
milestone: v4.3.0-developer-experience-and-runtime-resilience
blocked_by: []
related: [feat--git-level-gate-enforcement]
---

# Conflict marker gate inspects the command line instead of staged content

## Problem

Gate `commit_no_conflict_markers` in `scripts/alongkit/hooks/default_gates.yaml` applies `regex_forbidden` with pattern `<<<<<<<|=======|>>>>>>>` to the `CommandLine` of `git commit`. Conflict markers live in the staged files, not in the commit command, so the gate never catches a real unresolved conflict, while a commit message that contains a Markdown horizontal rule of `=======` would be falsely rejected.

## Requirements

- REQ-1: Replace the regex rule with a predicate that inspects `git diff --cached` (added lines only) for markers at line start (`^<<<<<<< `, `^=======$`, `^>>>>>>> `).
- REQ-2: Respect `.gitattributes` binary files and the typography scope; skip files with `merge=union` only if markers there are intentional (document the decision).
- REQ-3: Reuse the same predicate in the git pre-commit hook from `feat--git-level-gate-enforcement`.

## Acceptance Criteria

- [x] Committing a staged file with unresolved markers is blocked
- [x] A commit message containing `=======` is not blocked
- [x] Automated tests passing

## Resolution

- REQ-1: `commit_no_conflict_markers` in `default_gates.yaml` is now a predicate, `predicates.check_staged_conflict_markers`: it runs `git diff --cached -U0` (or `git diff HEAD` for `commit -a` / `--all`) and reports markers on added lines only (`<<<<<<< `, `=======`, `>>>>>>> ` at line start).
- REQ-2: decision documented in `docs/topic--declarative-gates-and-traceability.md`: no file class is exempt, because git never writes markers into `merge=union` files; binary files are skipped by `git diff` itself.
- REQ-3: `find_added_conflict_markers()` is a pure function, ready for the git pre-commit hook of `feat--git-level-gate-enforcement`.
- Tests: `tests/test_conflict_marker_gate.py` (throwaway git repo). Full suite on Python 3.12, 686 tests OK (3 skipped).
