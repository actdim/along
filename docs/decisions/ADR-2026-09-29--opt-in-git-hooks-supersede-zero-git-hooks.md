---
protocol: along
slug: opt-in-git-hooks-supersede-zero-git-hooks
type: decision
title: "Opt-in git hooks and CI supersede the Zero Git Hooks invariant"
date: 2026-09-29
status: accepted
tags: [adr, architecture, decision]
---

# ADR-2026-09-29--opt-in-git-hooks-supersede-zero-git-hooks - Opt-in git hooks and CI supersede the Zero Git Hooks invariant

- Date: 2026-09-29
- Status: accepted
- Context: Runtime gates run only where the host runtime loads Along hooks; Cowork, Cursor, humans and CI bots commit with zero gates. The Zero Git Hooks invariant in topic--runtime-hooks-and-gates forbade the only local layer that sees every commit. It was prose only, never an ADR.
- Decision: Replace it with No Git Hooks by Default: init, update and installers never write .git/hooks. along hooks install --git (opt-in) writes pre-commit/commit-msg shims that exec along gates check; a foreign hook is chained as <hook>.pre-along, and with core.hooksPath nothing is written. along gates check --ci runs the same subset in CI. Gates declare enforcement: [runtime, git, ci] in default_gates.yaml, and git/ci read their patterns from the same entries. Checks are read-only.
- Consequences: Every committer is covered by CI; local hooks are voluntary and bypassable with --no-verify. Only added lines are checked, so legacy debt never blocks commits. The commit_issue_binding regex now also accepts (refs #slug), the form along-commit writes.
