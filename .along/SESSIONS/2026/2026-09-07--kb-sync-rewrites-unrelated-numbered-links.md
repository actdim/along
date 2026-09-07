---
protocol: along
date: 2026-09-07
slug: kb-sync-rewrites-unrelated-numbered-links
agent: antigravity
branch: main
commit: pending
summary: Restrict KB link rewriter heuristics to exact legacy roots and add target existence checks
milestone: v3.0.0-global-quality-revision
issues_advanced: []
issues_completed: [kb-sync-rewrites-unrelated-numbered-links]
decisions: []
risks_logged: []
spikes_conducted: []
---

# Session: KB sync rewrites unrelated numbered links

## Summary
Replaced substring guessing with exact path-segment matching against configured legacy KB roots, eliminated automatic rewriting of numbered filenames, added target existence validation, implemented dry-run output, and strengthened code-fence tracking.

## Work Completed
- REQ-1: Replaced loose substring heuristic (`/kb`, `/wiki`, `kb/`, `wiki/`) with exact path-segment matching against configured `LEGACY_KB_ROOTS` (`.along/KB`, `.agents/KB`, `along/KB`, `agents/KB`) via `matches_legacy_kb_root` in `scripts/along_kb_sync.py`.
- REQ-2: Removed automatic rewriting of numbered filenames (`^\d{1,3}[-_]`). Numbered documentation files (such as MADR ADRs like `001-use-postgres.md` or chapter files like `01-intro.md`) remain untouched by default. Added explicit `--migrate-numbered` CLI flag in `scripts/along_kb_sync.py` to allow opt-in migration when desired.
- REQ-3: Added physical target verification on disk before rewriting any link (`os.path.isfile(target_abs)`). If a target does not exist, the link is left untouched and a warning is logged (`[WARN] Legacy target does not exist on disk: ...`).
- REQ-4: Added `--dry-run` CLI mode to `scripts/along_kb_sync.py` printing line-by-line intended rewrite actions (`file:line: [text](old) -> (new)`) without modifying any files on disk.
- REQ-5: Implemented `FenceTracker` class in `scripts/alongkit/markdown.py` with CommonMark-compliant handling of opening and closing fence markers, minimum fence lengths, and info strings. Updated `iter_lines_outside_fences` and `rewrite_links` to use `FenceTracker`.
- REQ-6: Ensured byte-for-byte preservation of original link text and URL anchors during rewriting. Added 1-indexed line numbers to `Link` dataclass in `rewrite_links`.
- REQ-7: Added comprehensive unit tests in `tests/test_alongkit.py` (`test_nested_and_mixed_fences_with_lengths`, `test_rewrite_preserves_link_text_and_anchors_roundtrip`) and `tests/test_skills_and_scripts.py` (`test_30_kb_sync_unrelated_links_and_numbered_heuristics`).
- Updated `skills/along-kb-sync/SKILL.md` and `docs/topic--skills-reference.md` to document the new `--dry-run` and `--migrate-numbered` flags.
- Completed issue `bug--kb-sync-rewrites-unrelated-numbered-links.md` and moved to `.along/ISSUES/done/`.

## Code Review & Blast Radius
- Full test suite passed cleanly: 292 tests passed (0 failed, 1 skipped).
- Hermetic invariant `TestSuiteLeavesTheRepositoryAlone` passed cleanly with no uncommitted mutations from tests.
- Typography check confirmed zero banned non-ASCII typographic characters across 282 scanned files.
- Backward compatibility preserved: `rewrite_inbound_links` retains its `(rewritten_files, total_rewrites)` 2-tuple signature.
