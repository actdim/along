---
protocol: along
protocol_version: "2.2.26"
date: 2026-09-09
slug: kb-sync-readme-alert-summary
agent: antigravity
branch: main
commit: pending
summary: Ignore alerts and extract first text block in along_kb_sync
issues_advanced: []
issues_completed: [kb-sync-readme-alert-summary]
decisions: []
risks_logged: []
spikes_conducted: []
---

# Session: Kb sync readme alert summary

## Summary
Refactored `_extract_project_meta` in `scripts/along_kb_sync.py` to robustly extract project descriptions from `README.md`, ignoring GitHub alert callouts, badges, and raw HTML containers while supporting both blockquotes and prose paragraphs.

## Work Completed
- Enhanced `_extract_project_meta()` in `scripts/along_kb_sync.py`:
  - Scans blocks following the first H1 header in `README.md`.
  - Skips HTML comments (`<!-- ... -->`).
  - Skips GitHub alert callout blocks (`> [!(NOTE|TIP|IMPORTANT|WARNING|CAUTION)]` and continuation lines).
  - Skips badge-only and raw HTML blocks (`[![...](...)]`, `<p><img ...></p>`).
  - Correctly extracts multi-line blockquotes (`> text`), joining lines and cleaning HTML tags.
  - Correctly extracts prose paragraphs if no blockquote exists.
  - Falls back to generic repository summary only when no valid text block is found.
- Added comprehensive unit and integration tests in `tests/test_skills_and_scripts.py` (`test_25b_readme_meta_extraction_alerts_badges_and_prose`).
- Updated LLM-Wiki Knowledge Base architecture documentation in `docs/topic--llm-wiki-architecture.md`.
- Executed full test suite (322 tests passing) and typography sanitization check.

## Code Review & Blast Radius
- Blast Radius: evaluated via `code-review-graph` (`get_impact_radius_tool`), localized to `scripts/along_kb_sync.py` and downstream `llms.txt` / `llms-full.txt` compilers.
- Automated Tests: 322 passing hermetic unit tests via standard test hook.
- Data Safety: Zero regressions, fully backward-compatible with existing repositories.
