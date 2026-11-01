---
protocol: along
protocol_version: "4.5.4"
slug: team-worktree-concurrency-rules
type: feat
status: open
priority: medium
created: 2026-10-30
updated: 2026-10-30
agent: antigravity
tags: [team, concurrency, worktree, rules]
milestone: v5.1.0-language-ecosystem-expansion
blocked_by: []
related: []
---

# Worktree concurrency rules and negative activation triggers for along-team

Codify strict file ownership and worktree concurrency invariants in `along-team`, and define explicit negative triggers (SKIP-TEAM) to prevent orchestration overhead on trivial tasks.

## Context and Problem Statement
Multi-agent orchestration in `along-team` coordinates distinct roles (Supervisor, Research, Architect, Implementer, Reviewer). Without strict write boundaries, parallel subagents risk stepping on each other's edits, creating lockfile merge conflicts, or invalidating compiled projections.

Additionally, while Along specifies that tasks touching more than 3 files or crossing subsystems require `along-team`, it lacks an explicit, enforced negative checklist. As a result, agents and users occasionally invoke heavy multi-agent swarms for 1-line typo fixes, dependency bumps, or informational questions, leading to unnecessary token consumption and context bloat.

## Requirements
- REQ-1: Concurrency Invariant: At most one writing agent MUST be active per git worktree at any given moment.
- REQ-2: File Ownership Invariant: Subagents MUST modify only files within their declared step scope. Package manifests (`package.json`, `Cargo.toml`, `pyproject.toml`) and Along projections (`ISSUES.md`, `CONSTRAINTS.md`) MUST be modified exclusively by the integration owner (Supervisor / Step Loop integrator).
- REQ-3: Lease Semantics: An active step lease (`claim.lock`) coordinates execution ownership among agents, but MUST NEVER grant authority to bypass runtime gates, tests, or linters.
- REQ-4: Negative Checklist (SKIP-TEAM): `along-team` activation MUST be explicitly prohibited for:
  1. Informational queries, codebase exploration, and read-only questions.
  2. Single-file typo, formatting, or docstring fixes.
  3. Single-dependency version bumps with existing unit test coverage.
  4. Non-breaking documentation revisions confined to `docs/`.

## Acceptance Criteria
- [ ] Concurrency and file ownership rules documented in `skills/along-team/SKILL.md` and `docs/topic--along-protocol.md`
- [ ] Negative activation checklist implemented in `scripts/along_team.py` and skill prompt
- [ ] Claim verification enforces manifest edit protection against non-integrator roles
- [ ] Unit tests added in `tests/test_alongkit.py` covering negative triggers and concurrency validation
