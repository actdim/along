---
protocol: along
protocol_version: "2.2.26"
slug: kb-sync-readme-alert-summary
type: bug
status: done
completed: 2026-09-09
priority: medium
created: 2026-09-09
updated: 2026-09-09
agent: antigravity
tags: [kb-sync, parser, readme]
blocked_by: []
related: []
---

# Ignore alerts and extract first text block in along_kb_sync

## Problem
In `scripts/along_kb_sync.py`, `_extract_project_meta()` extracts project summary using naive regex `re.search(r"^>\s+(.+)$", readme_text, re.MULTILINE)`. When a README contains GitHub alerts like `> [!NOTE]` or `> [!WARNING]`, the alert marker or alert body is mistakenly extracted as the project summary. Additionally, projects that do not use blockquotes (`>`) for their introductory description fall back to generic stubs even when a valid introductory paragraph exists under H1.

## Scope & Acceptance Criteria
- [x] In `scripts/along_kb_sync.py`, enhance `_extract_project_meta()` to extract the first valid text block (blockquote or paragraph) following the first H1 header in README.md.
- [x] Skip HTML comments (`<!-- ... -->`), HTML block elements / badges (`<p ...>`, `<img ...>`, `<div>`), and markdown badge lines (`[![...](...)]`).
- [x] Skip GitHub alert callout blocks (`> [!(NOTE|TIP|IMPORTANT|WARNING|CAUTION)]` and continuation lines).
- [x] Support blockquotes (`> text`) by stripping `>` and joining multiple lines.
- [x] Support regular prose paragraphs if no clean blockquote is found, formatting the resulting summary as a clean single-line or blockquote summary.
- [x] Add comprehensive automated tests in `tests/test_skills_and_scripts.py` covering alert skipping, badge skipping, multi-line blockquotes, and prose paragraphs.
- [x] Verify test suite passes without regressions.
