---
protocol: along
protocol_version: "4.9.1"
slug: commit-gates-skip-chained-and-dash-c-commits
title: "Commit gates anchored to ^git commit miss chained and git -C invocations"
type: bug
status: open
priority: medium
created: 2026-11-24
updated: 2026-11-24
agent: dsh
tags: [gates, hooks, commit, regex, runtime]
blocked_by: []
related: []
---

# Commit gates anchored to ^git commit miss chained and git -C invocations

## Problem

Two commit gates filter the command line with a start-anchored pattern:

```yaml
# scripts/alongkit/hooks/default_gates.yaml:17 (commit_issue_binding) and :35
match_args:
  CommandLine: '^git\s+commit'
```

`declarative.py` applies `match_args` with `pat.search()` on the argument string, so the
anchored pattern matches only when the command string begins with `git commit`.

The correct pattern already exists in the repository, one layer away: the third commit gate,
`commit_no_ai_coauthor`, is now commit-time only (`enforcement: [git, ci]`,
`default_gates.yaml:48`) and carries no `match_args` at all, while its predicate uses the
unanchored, `-C`-aware `_GIT_COMMIT_RE = re.compile(r"\bgit\s+(?:-C\s+\S+\s+)?commit\b")`
(`scripts/alongkit/hooks/predicates.py:1275`).

`commit_no_conflict_markers` is anchored twice: the catalogue matcher at `:35` and its own
predicate guard `re.match(r"^git\s+commit\b", cmd)`
(`scripts/alongkit/hooks/predicates.py:1258`). Fixing only the catalogue would leave the
predicate still rejecting the chained forms.

Measured consequence: `cd repo && git commit -m "no issue tag"` and
`git -C repo commit -m "no issue tag"` are admitted by the runtime layer, while
`enforcement: [runtime, git, ci]` is declared for both gates and
`docs/topic--runtime-hooks-and-gates.md` lists commit binding as runtime enforced. The git and
ci layers still reject the message, so the defect cheapens the runtime layer rather than the
whole guarantee.

## Requirements

- REQ-1: All runtime commit gates MUST share one unanchored, word-bounded command pattern that
  admits `git commit`, `git -C <path> commit`, and a `git commit` segment after `&&`, `;` or a
  pipe - in the catalogue matcher and in every predicate guard that re-checks the command.
- REQ-2: The pattern MUST be defined once and imported by every commit gate, so a fourth gate
  cannot reintroduce a private anchor.
- REQ-3: Tests MUST cover the plain form, the `&&` chain, `;`, a pipe, and `git -C <path>`.

## Acceptance Criteria

- [ ] `cd /tmp && git commit -m "x"` is denied by `commit_issue_binding`.
- [ ] `git -C /tmp commit -m "x"` is denied by `commit_issue_binding`.
- [ ] An unresolved conflict marker staged through either form is denied by
      `commit_no_conflict_markers`.
- [ ] A test enumerates the four invocation shapes and fails if any is admitted.

## Evidence

- Anchored patterns: `scripts/alongkit/hooks/default_gates.yaml:17`, `:35`.
- Double anchor in the predicate: `scripts/alongkit/hooks/predicates.py:1258`.
- Co-author gate is commit-time only: `default_gates.yaml:48`; its correct, unanchored pattern:
  `scripts/alongkit/hooks/predicates.py:1275`.
- `search()` semantics: `scripts/alongkit/hooks/declarative.py:97-101`.
