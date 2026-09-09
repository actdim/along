---
protocol: along
date: 2026-09-09
slug: line-endings-and-kb-search-ranking
agent: antigravity
branch: main
commit: pending
summary: Resolved generator line-ending churn, normalized repository to gitattributes, replaced naive substring matching with token-based IDF ranking and snippet extraction in KB search, closed 3 debt items and parent audit remediation epic, and recorded ADR.
milestone: v3.0.0-global-quality-revision
issues_advanced: []
issues_completed: [debt--unpinned-mcp-and-ghost-wiki-query-tool, debt--line-ending-churn-vs-gitattributes, debt--kb-search-ranking-and-snippet-quality, debt--protocol-quality-audit-remediation]
decisions: [ADR-2026-09-09--kb-search-in-memory-ranking-vs-sqlite-fts5]
risks_logged: []
spikes_conducted: []
---

# Session: Line Endings Normalization and KB Search Ranking Overhaul

## Summary
Addressed three technical debt items and completed the remaining remediation scope of the 2026-09-01 quality audit epic:
1. Closed `debt--unpinned-mcp-and-ghost-wiki-query-tool` after removing phantom tool references and pinning `code-review-graph` to 2.3.8.
2. Resolved `debt--line-ending-churn-vs-gitattributes` by adding `newline_for_path()` in `scripts/alongkit/textio.py`, enforcing explicit newline parameters across 24 generator write sites, setting local `core.autocrlf false`, renormalizing tracked files to match `.gitattributes` (0 CRLF mismatches), and adding newline regression tests.
3. Replaced naive substring search in `scripts/along_kb_search.py` (`debt--kb-search-ranking-and-snippet-quality`) with word-boundary token matching, lightweight English suffix stemming, smoothed IDF weighting, AND-by-default semantics (`--any` for OR), exact quoted phrases, and centered word-boundary snippet extraction. Verified 99.8% token savings via `--stats` mode, added 7 test fixture methods, and recorded ADR-2026-09-09--kb-search-in-memory-ranking-vs-sqlite-fts5.
4. Closed parent epic `debt--protocol-quality-audit-remediation` with all 28 child findings resolved and marked milestone `v3.0.0-global-quality-revision` 100% complete.

## Initial Implementation Plan (Baseline)
1. **Phase 0 (Housekeeping)**: Commit pending changes and close `debt--unpinned-mcp-and-ghost-wiki-query-tool`.
2. **Phase A (Line Endings)**:
   - Audit write sites and add `newline_for_path(path)` helper.
   - Enforce explicit `newline="\n"` across markdown and config generators.
   - Renormalize git tree to `.gitattributes` in dedicated commit.
   - Add line ending regression tests in `tests/test_alongkit.py`.
   - Document line ending policy in `docs/topic--setup-and-workflow.md`.
3. **Phase B (KB Search Ranking)**:
   - Tokenize query terms on word boundaries with lightweight stemming.
   - Smooth IDF corpus weighting (`math.log((N + 1) / (df + 1)) + 1.0`).
   - AND semantics by default, optional `--any` and `--prefix` flags.
   - Exact quoted phrase matching support.
   - Centered passage snippet extraction without mid-word truncation.
   - Add `--stats` output mode and test fixtures.
   - Record ADR in `.along/DECISIONS.md`.

## Execution & Loop Trace (Fixes & Re-plans)
- `[Fix Loop - Windows Git CRLF Churn]`: ggit ls-files --eol` reported 151 files with `w/crlf attr/text eol=lf`. Configured local git `core.autocrlf false` and ran ggit rm --cached -r . ; git reset --hard`. Added regression test `test_tracked_files_match_gitattributes_newline_policy` verifying working tree files match `.gitattributes` policy.
- `[Fix Loop - Snippet Centering]`: Slicing snippets from start of match resulted in losing context or cutting off terms when matches occurred later in passages. Implemented 1/3 leading context budget with whitespace-aware boundary snapping.
- `[Fix Loop - Test Runner Bootstrap]`: Running tests via raw `pytest` or `unittest` directly misses uv hermetic dependency injection. Enforced contract-first execution via `python .along/scripts/test.py`.

## Verification Walkthrough & Gate Manifest
- **Unit & Behavioral Tests**: `python .along/scripts/test.py` -> 337 passing (0 failed, 1 skipped).
- **Entity Doctor**: `python scripts/along_exec.py doctor --entities` -> 0 errors, 0 warnings across 170 entities.
- **Typography Check**: `python scripts/along_exec.py sanitize` -> 300 files scanned, 0 violations.
- **KB Sync & Links**: `python scripts/along_exec.py kb-sync` -> Rebuilt `docs/INDEX.md` and `llms-full.txt`, 0 broken links.
- **Git Line Endings**: ggit ls-files --eol` -> 0 CRLF mismatches for `eol=lf` declared files.
- **Search Relevance**: 7 new regression assertions in `tests/test_kb_search.py` covering token boundaries, AND/OR logic, phrases, stemming, and token reduction stats.

## Code Review & Blast Radius Assessment
- `scripts/alongkit/textio.py`: Added `newline_for_path()` and `_CRLF_EXTENSIONS = {".bat", ".cmd", ".ps1"}`. Safe backward-compatible extension.
- Generator writers (`along_kb_sync.py`, `along_exec.py`, `along_update.py`, `along_version_bump.py`, `along_feedback.py`, `alongkit/entities.py`, `alongkit/lifecycle.py`, `alongkit/diagnostics.py`): Explicit `newline="\n"` or `newline=newline_for_path(path)` prevents platform newline drift on Windows machines.
- `scripts/along_kb_search.py`: Replaced naive `term in text` with `parse_query`, `light_stem`, `tokenize`, `compute_idf`, and structured snippet extraction. CLI_interface remains backward compatible while adding `--any`, `--prefix`, and `--stats`.
- `code-review-graph`: Offline in current environment; fell back to AST and static caller analysis. All callers of `along_kb_search.py` and `textio.py` verified intact.
