---
protocol: along
slug: durable-session-blackboard-and-canonical-cli
title: "Durable Multi-Agent Session Blackboard and Canonical CLI Skill Execution"
date: 2026-09-07
status: accepted
tags: [adr, architecture, decision]
---

# ADR-2026-09-07--durable-session-blackboard-and-canonical-cli - Durable Multi-Agent Session Blackboard and Canonical CLI Skill Execution

- Date: 2026-09-07
- Status: accepted
- Context:
  1. `skills/*/SKILL.md` hardcoded relative execution paths (`python scripts/<engine>.py`), which broke in consumer repositories where `scripts/` does not exist, and duplicated `along_exec.py` dispatch logic.
  2. Sibling engines (`along_update.py`, `migrate_protocol.py`) directly invoked sibling scripts via `os.path.join(repo_root, "scripts", ...)`, failing when run from installed locations or custom consumer layouts.
  3. While ADR-2026-08-31 defined the concept of session-scoped blackboards, `skills/along-team/SKILL.md` lacked a durable, machine-parsable state machine. In-flight progress, step results, living plans, and retry counters were kept in volatile agent context. If a session interrupted or hit a rate limit, all step tracking was lost and retries could loop indefinitely.
- Decision:
  1. **Canonical CLI Standardization**:
     - Standardize all 18 skill definitions and documentation on the canonical `along <command>` CLI entry point, with documented fallback to `python ~/.along/bin/along_exec.py <command>` or `python scripts/along_exec.py <command>`.
     - Update sibling engines (`along_update.py`, `migrate_protocol.py`, `along_version_bump.py`, `along_exec.py`) to resolve tool scripts dynamically via `alongkit.repo.resolve_tool_script` across local checkout, user home (`~/.along/bin`), and PATH.
  2. **Durable Session Blackboard Engine (`alongkit.session`)**:
     - Implement structured state management in `scripts/alongkit/session.py` persisting `state.json` inside `.along/.session/<slug>/`.
     - Store session metadata: `slug`, `title`, `status`, `created_at`, `updated_at`, `current_step`, `plan_revision`, `retry_limit` (default: 2), and structured `steps: [{step, status, retries, updated_at}]`.
     - Expose CLI subcommands via `along scratch`:
       - `init <slug> [--title <title>] [--steps <N>] [--restart]`
       - `state <slug> [--json]`
       - `update <slug> [--step <N>] [--step-status <status>] [--inc-retry] [--status <status>] [--plan-rev <N>]`
       - `purge <slug>`
  3. **Strict Retry Enforcement & Session Resumption**:
     - Halt execution with exit code 2 when a step exceeds its retry limit (2 retries per step), preventing runaway token consumption.
     - On agent restart or session continuation, inspect `state.json` to resume immediately from the active step rather than restarting from step 1.
  4. **Purge Lifecycle Invariant**:
     - Enforce automatic cleanup of `.along/.session/<slug>/` during `along-wrap` (Phase 8 of `along-team`) after compiling session logs into `.along/SESSIONS/<YYYY>/<date>--<slug>.md`.
- Consequences:
  - Eliminates "script not found" failures across consumer repositories when agents execute skills.
  - Multi-agent orchestration in `along-team` is fully recoverable across tool crashes, rate limits, and context resets.
  - Guarantees finite execution bounds through hard retry limits.
  - Maintains clean repository hygiene by purging ephemeral blackboard directories upon wrap-up.
