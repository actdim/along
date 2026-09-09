---
protocol: along
slug: v3-dod-alignment-and-board-reconciliation
type: debt
status: done
priority: high
created: 2026-09-09
updated: 2026-09-09
completed: 2026-09-09
agent: antigravity
tags: [dod, v3, board, honesty, documentation, skills]
milestone: v3.0.0-global-quality-revision
blocked_by: []
related: [debt--protocol-quality-audit-remediation, debt--unpinned-mcp-and-ghost-wiki-query-tool, debt--always-on-context-budget-exceeds-claims]
---

# Reconcile Board and Documentation with v3.0.0 Definition of Done

## Problem

An audit of the repository state prior to the v3.0.0 release identified several discrepancies against the four v3.0.0 Definition of Done criteria (Executable, Behaviorally tested, Honest, Non-destructive):

1. **Board Hygiene & Milestones**:
   - `feat--knowledge-base-management-and-init-kb-skill` is open in milestone v1.5.0, referencing obsolete `/along-init-kb` and `.along/KB/`.
   - `feat--runtime-enforcement-of-prose-rules` is marked `in-progress` in milestone v4.0.0 without any implementation code.
   - Milestone `v3.0.0-global-quality-revision` was prematurely marked `status: completed` while the project version is `2.3.0` and open debts remained.

2. **Protocol & Gate Honesty**:
   - `AGENTS.md` and `skills/along-wrap/SKILL.md` still prescribe `MUST execute code-review-graph`, contradicting REQ-3 of `debt--unpinned-mcp-and-ghost-wiki-query-tool` which required softening to "when available".
   - `debt--protocol-quality-audit-remediation.md` line 72 and session logs mistype the MCP pin version as `v1.2.0` instead of `2.3.8`.
   - `along-kb-search` and documentation advertise an unverified "95-99% measured token reduction" marketing figure.

3. **Skill Portability**:
   - `along-graph-check/SKILL.md` lists `python scripts/along_exec.py graph-check` as the primary CLI command, failing in consumer repositories.
   - `along-init/SKILL.md` hardcodes protocol versions in `description`, causing version churn across releases.
   - `pyproject.toml` retains an obsolete comment about closed bug `bug--skill-commands-reference-missing-script-paths`.

## Requirements

- REQ-1: Mark `feat--knowledge-base-management-and-init-kb-skill` as superseded and move to `done/`.
- REQ-2: Revert `feat--runtime-enforcement-of-prose-rules` status to `open`.
- REQ-3: Revert milestone `v3.0.0-global-quality-revision` status to `in-progress`.
- REQ-4: Soften blast-radius gate wording to "when available" in `AGENTS.md` and `skills/along-wrap/SKILL.md`.
- REQ-5: Replace unverified token reduction percentage in `skills/along-kb-search/SKILL.md` and `docs/topic--*.md` with factual snippet retrieval description.
- REQ-6: Correct `code-review-graph` version pin typo (`v1.2.0` -> `2.3.8`) in closed epic and session log.
- REQ-7: Prioritize `along graph-check` in `skills/along-graph-check/SKILL.md`.
- REQ-8: Remove hardcoded protocol version in `skills/along-init/SKILL.md` description and clean up obsolete comment in `pyproject.toml`.

## Acceptance Criteria

- [x] Zombie issue superseded and moved to `done/`.
- [x] v4 issue status reset to `open`.
- [x] Milestone `v3.0.0` status reconciled.
- [x] Gate wording softened to "when available" in protocol and wrap skill.
- [x] Unverified marketing percentages removed from search documentation.
- [x] Version pin typo corrected in epic and session record.
- [x] Skill portability fixed in `along-graph-check`.
- [x] Stale comment and hardcoded description versions cleaned up.
- [x] Full test suite and typography verification pass clean.
