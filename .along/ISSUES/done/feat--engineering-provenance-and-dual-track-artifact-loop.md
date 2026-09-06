---
protocol: along
protocol_version: 2.2.8
slug: engineering-provenance-and-dual-track-artifact-loop
type: feat
status: done
completed: 2026-09-06
priority: medium
created: 2026-09-06
updated: 2026-09-06
agent: antigravity
tags: [skills, along-team, provenance, artifacts, loop]
milestone: v3.0.0-global-quality-revision
blocked_by: []
related: [team-skill-uses-provider-specific-subagent-api]
parent: protocol-quality-audit-remediation
---

# Engineering Provenance, Dual-Track UI Artifacts, and Loop Trace Persistence in along-team

## Context & Motivation

Following the Google Antigravity Loop specification ("The Antigravity Loop: From Chat to Autonomous Engineering"), autonomous engineering cycles require both rich user feedback during execution and permanent provenance in repository memory. Currently, `along-team` stores living plans in ephemeral `.along/.session/<slug>/` storage that is deleted upon wrap-up, and Antigravity's native interactive artifacts (`implementation_plan.md` with "Proceed" and `walkthrough.md`) are not systematically utilized or archived.

## Requirements

- **REQ-1 (Dual-Track UI Projection)**: In Phase 2 (Architect), project the Living Plan into `<appDataDir>/brain/<id>/implementation_plan.md` with `RequestFeedback: true` when running under Google Antigravity, while preserving clean terminal output in Claude Code, Codex, and OpenCode.
- **REQ-2 (Loop Trace & Fix Loop vs Re-plan Loop)**: In Phase 3-5 (Step Loop), explicitly distinguish between local test/lint micro-corrections (`[Fix Loop]`, scoped strictly to failure diff/trace, max 2 retries) and structural architectural revisions (`[Re-plan Loop]`, incrementing `Living Plan Revision N`). Trace attempts in `.along/.session/<slug>/execution_trace.md`.
- **REQ-3 (Verification Walkthrough & Session Provenance)**: In Phase 7 (Finish), project results to `walkthrough.md` in Antigravity brain, and compile the permanent 3-part provenance into `.along/SESSIONS/<YYYY>/<date>--<slug>.md`:
  1. `## Initial Implementation Plan (Baseline)`
  2. `## Execution & Loop Trace (Fixes & Re-plans)`
  3. `## Verification Walkthrough & Gate Manifest`
- **REQ-4 (Documentation & Skill Mirroring)**: Update `skills/along-wrap/SKILL.md`, `docs/topic--skills-reference.md`, and global skill mirror in `~/.gemini/config/skills/along-team/SKILL.md`.
- **REQ-5 (ADR & Verification)**: Record an ADR in `.along/DECISIONS.md` and add automated regression test in `tests/test_skills_and_scripts.py`.

