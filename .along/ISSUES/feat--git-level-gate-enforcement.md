---
protocol: along
protocol_version: "4.2.0"
slug: git-level-gate-enforcement
type: feat
status: open
priority: high
created: 2026-09-27
updated: 2026-09-27
agent: cowork
tags: [gates, git-hooks, ci, cross-runtime]
milestone: v4.4.0-multi-user-merge-automation
blocked_by: []
related: [task--ci-test-matrix-workflow, feat--cowork-runtime-support, bug--conflict-marker-gate-wrong-target, feat--test-gated-code-merge-pipeline]
---

# Runtime-agnostic gate enforcement via git hooks and CI

## Problem

All mechanical gates run only inside agent runtimes that load Along's PreToolUse/Stop hooks (Claude Code via `~/.claude/settings.json`, Antigravity, Codex). Any other runtime - Claude Cowork, Cursor, a human, a CI bot, a runtime without hook support - sees `AGENTS.md` as advisory prose only. The README presents the gates as hard runtime errors without this caveat. Observed in practice: a Cowork session on this repository ran with zero gates active.

**Conflict to resolve first (found 2026-09-27):** `docs/topic--runtime-hooks-and-gates.md` invariant 1 "Zero Git Hooks Invariant" states that Along forbids `.git/hooks/*` and that all enforcement happens in the agent runtime layer. REQ-1 contradicts it. Before implementation, record an ADR that either supersedes the invariant (opt-in `along hooks install --git`, never installed by default) or drops REQ-1 and keeps only the CI job (REQ-2). Reusable pieces already exist: `predicates.find_added_conflict_markers()` and `hooks/shellparse.py` (v4.3.0), and `.github/workflows/tests.yml` (`task--ci-test-matrix-workflow`).

## Requirements

- REQ-1: `along hooks install --git` writes `pre-commit` and `commit-msg` hooks (or `core.hooksPath` to a tracked `.along/git-hooks/`) that run the commit-time subset of gates: typography, conflict markers on staged content, commit issue binding, projection protection (projections must match a fresh compile), anti-stub on staged diff.
- REQ-2: `along gates check --ci` runs the same subset plus link integrity and projection freshness for CI, with non-zero exit on violation.
- REQ-3: Gate catalogue entries declare `enforcement: [runtime, git, ci]`, and `along hook verify` reports which invariants are enforced where.
- REQ-4: Hooks are cross-platform (Python entry, no bash-only logic) and never mutate files.
- REQ-5: README and `docs/topic--runtime-hooks-and-gates.md` state that runtime gates depend on the host runtime, and that git/CI enforcement is the portable baseline.

## Acceptance Criteria

- [ ] A commit with banned typography or without an issue slug is blocked by the git hook regardless of which agent made it
- [ ] CI job fails on the same violations
- [ ] Automated tests passing
