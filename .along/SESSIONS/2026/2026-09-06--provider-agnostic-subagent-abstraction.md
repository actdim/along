---
protocol: along
date: 2026-09-06
slug: provider-agnostic-subagent-abstraction
agent: antigravity
branch: main
commit: pending
summary: Made along-team provider-agnostic across Antigravity, Claude Code, Codex, and OpenCode, specified single-agent Ralph loop degradation, made reviewer rubric conditional with structured manifests, and hardened git against Windows concurrent index lock collisions.
milestone: v3.0.0-global-quality-revision
issues_advanced: []
issues_completed: [bug--team-skill-uses-provider-specific-subagent-api, bug--commit-binds-arbitrary-active-issue]
decisions: [ADR-2026-09-06--provider-agnostic-subagent-abstraction]
risks_logged: []
spikes_conducted: []
---

# Session: Provider-Agnostic Subagent Abstraction and Concurrency Hardening

## Summary
Refactored the along-team skill to abstract subagent orchestration across Google Antigravity, Claude Code, OpenAI Codex, and OpenCode. Added a deterministic single-agent degradation path (Ralph Loop state machine), made the reviewer rubric conditional on installed tooling, documented workspace isolation contracts, resolved commit binding ambiguity, and eliminated Windows NTFS git index locking race conditions.

## Work Completed
- Refactored `skills/along-team/SKILL.md` (and mirrored to global user skills):
  - Abstracted subagent lifecycle into portable primitives (`spawn_readonly_researcher`, `spawn_worker`, `spawn_reviewer`) with capability mapping matrices for Antigravity (`invoke_subagent`), Claude Code (`Agent` tool / `/fork`), Codex (`spawn_agent`), and OpenCode (`session.fork`).
  - Implemented single-agent Ralph Loop fallback state machine for tools lacking subagent APIs or when running in constrained single-agent mode.
  - Replaced hardcoded reviewer rubrics with 7 conditional gates, explicitly reporting `DEGRADED` when `code-review-graph` is absent and requiring a structured `Gate Execution Manifest`.
  - Defined explicit workspace isolation contracts (`Workspace: "inherit"` default, branch naming conventions, merge/abort cleanup rules).
  - Specified canonical test runner resolution order (`along test` -> `<resolved>/along_exec.py test` -> native test runners).
  - Added smoke verification procedures for all 4 supported providers.
- Recorded Architectural Decision Record `## ADR-2026-09-06--provider-agnostic-subagent-abstraction` in `.along/DECISIONS.md`.
- Updated Knowledge Base reference in `docs/topic--skills-reference.md`.
- Hardened Git concurrency on Windows:
  - Added `GIT_OPTIONAL_LOCKS: "0"` in `scripts/alongkit/proc.py` and Windows User environment to prevent read-only status and diff checks from contending for write locks on `.git/index`.
  - Added automatic zero-byte `.git/index` self-healing in `alongkit.proc.git`.
  - Configured `core.preloadindex = false` to eliminate multi-threaded stat cache collisions.
- Resolved issue `bug--commit-binds-arbitrary-active-issue`:
  - Added `--issue` flag, ambiguity validation, and deterministic parent/subtask binding in `scripts/along_commit.py` and `skills/along-commit/SKILL.md`.
- Added unit tests in `tests/test_skills_and_scripts.py` and `tests/test_commit.py`.
- Closed issues `bug--team-skill-uses-provider-specific-subagent-api.md` and `bug--commit-binds-arbitrary-active-issue.md`, moving both to `.along/ISSUES/done/`.

## Code Review & Blast Radius
- All 252 unit tests pass cleanly in 18.5s.
- Hermetic invariant `TestSuiteLeavesTheRepositoryAlone` passes cleanly.
- Clean typography check passes across all files with zero banned characters.

