---
protocol: along
date: 2026-09-07
slug: generated-docs-emit-file-uri-links
agent: antigravity
branch: main
commit: pending
summary: Eliminate file:// URI pseudo-scheme in favor of standard portable relative Markdown links and enforce via link integrity gate
milestone: v3.0.0-global-quality-revision
issues_advanced: []
issues_completed: [generated-docs-emit-file-uri-links, issue-create-stamps-wrong-agent-and-milestone]
decisions: [ADR-2026-09-07--ban-file-uri-scheme-in-markdown-links]
risks_logged: []
spikes_conducted: []
---

# Session: Eliminate file:// URI links and enforce standard relative Markdown links

## Summary
Resolved the protocol contradiction between AGENTS.md and along-kb-sync by banning the `file://` pseudo-scheme in favor of standard portable relative Markdown links (`[Title](./target.md)`). Recorded ADR-2026-09-07--ban-file-uri-scheme-in-markdown-links, updated all generators to compute relative paths, hardened the link integrity gate to flag `file://` as a violation, removed Windows drive-letter workarounds, and migrated all existing `file://` links across the repository while repairing stale ADR anchors.

## Work Completed
- REQ-1: Resolved rule contradiction across AGENTS.md, skills/along-init/protocol.md, and all skill definitions. Explicitly banned `file://` and `file:///` pseudo-schemes in Technical Markdown Standards. Recorded `ADR-2026-09-07--ban-file-uri-scheme-in-markdown-links` in `.along/DECISIONS.md`.
- REQ-2: Updated all generators to emit strictly relative links:
  - `scripts/along_exec.py`: `handle_session_command` generates `./SESSIONS/{year}/{today}--{slug}.md`.
  - `scripts/alongkit/rules.py`: `attach_rules` emits `[{r}](.along/rules/{r})`.
  - `scripts/along_history_sync.py`: emits `./SESSIONS/{c_year}/{c_date}--{slug}.md`.
  - `scripts/along_kb_sync.py`: `sync_kb` dynamically computes relative paths for "Related Context" in `docs/INDEX.md` and only links files that exist on disk.
- REQ-3 & REQ-8: Implemented migration logic in `rewrite_inbound_links` in `scripts/along_kb_sync.py`:
  - Automatically converts `file://` and `file:///` links across repository files (including `.along/`) into relative paths based on document location.
  - Implemented `_repair_or_drop_anchor` to map legacy numbered ADR anchors (`#011`, `#2`) to slug headers (`#adr-YYYY-MM-DD--<slug>`) and drop dead ADR anchors on `DECISIONS.md`.
  - Converted existing repository `file://` links to relative paths.
- REQ-4 & REQ-5: Hardened `validate_repo_link_integrity` in `scripts/along_kb_sync.py`:
  - Flags `file://` and `file:///` as broken link violations (`reason: "file:// pseudo-scheme forbidden (use standard relative links)"`).
  - Removed Windows drive-letter resolution branch (`p[1] == ':'`) from both `validate_repo_link_integrity` and `alongkit.markdown.resolve_target`.
- REQ-6: Softened universal rendering claim in `skills/along-kb-sync/SKILL.md` to reflect actual supported environments.
- REQ-7: Added `test_31_banned_file_uri_scheme_and_relative_migration` in `tests/test_skills_and_scripts.py` and updated `tests/test_alongkit.py:test_file_uri_targets_resolve`.
- Completed issue `bug--generated-docs-emit-file-uri-links.md` and moved to `.along/ISSUES/done/`.
- Verified and closed issue `bug--issue-create-stamps-wrong-agent-and-milestone.md` and moved to `.along/ISSUES/done/`.

## Code Review & Blast Radius
- Ran full automated test suite (`python .along/scripts/test.py`): 293 tests ran, 293 passed (0 failures, 1 skipped).
- Meta-tests in `tests/test_zz_hermetic_suite.py` verified the working tree was left clean.
- Verified typography via `python scripts/along_exec.py sanitize --check`: 0 banned characters across 284 files.
- Verified entity integrity via `python scripts/along_exec.py doctor --entities`: 157 entities scanned, 0 errors, 0 warnings.
