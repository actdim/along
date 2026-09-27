---
protocol: along
protocol_version: "4.2.0"
slug: conflict-marker-gate-wrong-target
type: bug
status: open
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

- [ ] Committing a staged file with unresolved markers is blocked
- [ ] A commit message containing `=======` is not blocked
- [ ] Automated tests passing
