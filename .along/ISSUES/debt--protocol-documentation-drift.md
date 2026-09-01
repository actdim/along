---
protocol: along
protocol_version: 2.2.8
slug: protocol-documentation-drift
type: debt
status: open
priority: high
created: 2026-09-01
updated: 2026-09-01
agent: claude-code
tags: [documentation, drift, single-source-of-truth, duplication]
milestone: v3.0.0-global-quality-revision
blocked_by: []
related: [always-on-context-budget-exceeds-claims, generated-docs-emit-file-uri-links, quality-gates-skip-hidden-directories]
parent: protocol-quality-audit-remediation
---

# The protocol text is duplicated in five places and has drifted in all of them

## Problem: five copies of overlapping content

```text
AGENTS.md                          22.5 KB   always loaded into every session
skills/along-init/protocol.md      20.7 KB   the template stamped into AGENTS.md
docs/topic--skills-reference.md    20.7 KB   skills documentation
llms.txt + llms-full.txt            8.0 KB   condensed protocol for LLM consumption
README.md                           6.0 KB   public entry point
```

`tests/test_skills_and_scripts.py:103-130` checks only that a single version string matches
across `protocol.md`, `AGENTS.md`, `README.md`, and `CURRENT_PROTOCOL_VERSION` in scripts.
Everything else is free to diverge, and has.

## Confirmed drift

1. **Schema version wrong in the always-loaded file.** `AGENTS.md:127` requires
   `protocol_version: "2.2.4"` in `docs/*.md` front-matter, while the protocol is `2.2.8`
   and the engine stamps `2.2.8`.
2. **Articles stuck at an old version.** `docs/topic--architecture.md:3` declares `2.2.6`.
   `along_kb_sync.py:513` only fills `protocol_version` when absent and never upgrades it,
   so every article keeps whatever version it was created with.
3. **A deleted skill is advertised.** `AGENTS.md` Project specifics lists
   `along-context-sync` among the skills, while `install.ps1:33` includes
   `along-context-sync` in `$LegacySkills` and actively deletes it on every install. The
   always-loaded instruction file tells agents to use a command that the installer removes.
4. **Wrong frontend path.** `AGENTS.md` Project specifics documents
   `packages/along-dash-ui/`; the directory is `packages/dashboard-ui/`. The file that
   instructs agents to "verify any named file/API/flag against the real code first" names a
   path that does not exist.
5. **Skill count and grouping mismatch.** `README.md:57` says "18 singular automation
   skills" and groups them into six phases; `AGENTS.md` lists a different set (19 entries,
   including the deleted `along-context-sync`).
6. **Empty LICENSE.** `README.md:103-105` states "MIT License. See LICENSE for details";
   `LICENSE` is 0 bytes. Tracked in detail under
   `[bug--quality-gates-skip-hidden-directories]` REQ-5.
7. **Contradictory link rule.** Covered by
   `[bug--generated-docs-emit-file-uri-links]`.
8. **Contradictory dependency claim.** `skills/along-kb-sync/SKILL.md:16` advertises "zero
   external dependencies", while `scripts/along_dash.py` declares five (fastapi, uvicorn,
   pydantic, pyyaml, rich) and the dashboard requires them.
9. **Determinism rule violated by the reference implementation.** `AGENTS.md` bans inline
   `python -c "..."` on Windows/PowerShell; `install.ps1:200-225` and `install.sh:160-191`
   use exactly that.

## Impact

`AGENTS.md` is loaded into every session for every agent, so its errors are the most
expensive errors in the repository: they are read first, trusted, and acted upon. Wrong
paths and phantom commands cause agents to search for files that do not exist and to invoke
skills that were deleted, which is the exact waste the protocol exists to eliminate.

## Requirements

- REQ-1: Establish one source of truth. `skills/along-init/protocol.md` generates the
  managed block in `AGENTS.md`; `docs/topic--skills-reference.md`, `llms.txt`, and
  `llms-full.txt` must be generated from the skill manifests and the protocol file, not
  hand-maintained.
- REQ-2: Add a consistency gate that fails on:
  - skills listed in documentation that do not exist in `skills/`;
  - skills in `skills/` missing from documentation;
  - any documented filesystem path that does not exist;
  - version strings inconsistent across all files including `docs/*.md` front-matter.
- REQ-3: Define and implement `protocol_version` upgrade semantics for existing `docs/`
  articles (coordinate with `[bug--kb-sync-ingestion-not-idempotent]` REQ-5).
- REQ-4: Fix all nine drift items listed above.
- REQ-5: Resolve the "zero external dependencies" claim: either scope it accurately (the KB
  engine itself is stdlib-only) or drop it.
- REQ-6: Record an ADR on the generated-documentation boundary: which files are authored and
  which are compiled.

## Acceptance Criteria

- [ ] Consistency gate implemented and green.
- [ ] Every documented path resolves; every documented skill exists.
- [ ] `docs/` front-matter versions consistent with the protocol.
- [ ] `AGENTS.md` free of phantom skills and wrong paths.
- [ ] Duplicated documentation generated rather than hand-maintained.
- [ ] ADR recorded.
