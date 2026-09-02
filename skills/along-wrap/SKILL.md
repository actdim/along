---
name: along-wrap
description: Wrap up the current coding session or completed work stage by updating the repo's .along/ state - execute code review checklist, write a session log file, synchronize ISSUES.md projection, move completed issues to ISSUES/done/, append a HISTORY line, and record decisions/glossary terms. Use when ending work, wrapping up, or when invoking /along-wrap.
---

# Along Wrap  [v2.2.17]

Universal finalization and memory synchronization protocol for sessions, tasks, and milestone stages.

## Scope & Nearest Placement (Strict Rule)
- **Always target the NEAREST `.along/`**: If the work was conducted in a subproject, Git submodule, or symlinked component (e.g. `packages/common/`, `libs/logger/`), execute wrap-up and write session logs, history, and issue updates directly in that subproject's `.along/`.
- Never pollute the parent workspace root `.along/` with subproject-internal bug fixes or tasks.

## When to Use
- The user or agent completes a feature, bugfix, stage, or ends a work session (triggers: "wrap up", "finish session", "close stage", `/along-wrap`, `/wrap`, `/along-wrap-session`, `/along-wrap-stage`).
- An active issue acceptance criteria have been verified and ready to close.

## Mandatory Execution Checklist (Execute in Exact Order)
1. [ ] **Verification & Tests**: Run automated unit tests / linting / builds with quiet flags (`/along-test` or `/along-build`).
2. [ ] **Code Review & Blast Radius Assessment**:
   - Inspect `git diff` for unintended side effects, unhandled nulls/errors, and edge cases.
   - Evaluate systemic blast radius on callers/dependents using `code-review-graph` (`get_impact_radius_tool`, `get_affected_flows_tool`) or AST analysis.
   - Identify all modified subsystem symbols and impacted downstream interfaces to inform documentation updates.
   - Verify compliance with architectural decisions in `.along/DECISIONS.md`.
3. [ ] **Entity Reconciliation**:
   - Set `status: done` and `completed: YYYY-MM-DD` for finished issues in the nearest `.along/ISSUES/`; MOVE to `ISSUES/done/<type>--<slug>.md`.
   - Update related `.along/MILESTONES/` progress percentages.
   - Resolve mitigated `.along/RISKS/` (`status: resolved` / `mitigated`).
   - Conclude active `.along/SPIKES/` and log any resulting ADR in `.along/DECISIONS.md`.
4. [ ] **Documentation Blast Radius Check & LLM-Wiki Gate**:
   - Map identified code blast radius symbols/modules to Knowledge Base topics using `along-kb-search` or symbol search in `docs/`.
   - Factually update all affected `docs/topic--*.md` articles (and `README.md` / `AGENTS.md` if public entry points or conventions changed).
   - Run `/along-kb-sync` to recompile `docs/INDEX.md`, validate link integrity, and verify zero 404 broken relative links.
5. [ ] **Session Log**: Write `.along/SESSIONS/<YYYY>/<YYYY-MM-DD>--<short-slug>.md` in the nearest `.along/` with complete front-matter (`protocol: along`, `issues_advanced`, `issues_completed`, `decisions`, `risks_logged`, `spikes_conducted`) and a concise Code Review & Impact summary.
6. [ ] **ISSUES Board Projection**: Run `/along-issue-sync` (or update nearest `.along/ISSUES.md`).
7. [ ] **HISTORY**: Append one line to nearest `.along/HISTORY.md`: `<YYYY-MM-DD> - <slug> - <agent> - <summary> - <link>`.
8. [ ] **Compaction Prompt**: Advise user to run `/compact` to free up token budget.

