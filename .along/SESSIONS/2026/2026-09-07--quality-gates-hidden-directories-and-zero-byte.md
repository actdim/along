---
protocol: along
date: 2026-09-07
slug: quality-gates-hidden-directories-and-zero-byte
agent: antigravity
branch: main
commit: pending
summary: Fix quality gates skipping hidden directories and dotfiles, zero-byte file detection, and populate LICENSE
milestone: v2.2.0-along
issues_advanced: []
issues_completed: [quality-gates-skip-hidden-directories]
decisions: []
risks_logged: []
spikes_conducted: []
---

# Session: Quality gates hidden directories and zero byte

## Summary
Fix quality gates skipping hidden directories and dotfiles, zero-byte file detection, and populate LICENSE.

## Work Completed
- Populated `LICENSE` with standard MIT License text for copyright holder `actdim`, 2026, resolving 0-byte state.
- Exported canonical `FORBIDDEN_CHARACTERS` tuple in `alongkit.typography` to unify character sets between sanitizer and test gates.
- Exported `UTF8_BOM` byte constant (`b"\xef\xbb\xbf"`) and `has_utf8_bom` helper in `alongkit.textio` for byte-level BOM checking.
- Refactored `test_00_zero_byte_files_forbidden` in `tests/test_skills_and_scripts.py` to use `git ls-files` (covering all tracked files regardless of extension), with exact path-segment filtering fallback and explicit allowlist for `.gitkeep`.
- Added `test_00b_readme_referenced_files_exist_and_nonempty` in `tests/test_skills_and_scripts.py` asserting all local files referenced in `README.md` exist and have non-zero size.
- Refactored `test_05_clean_typography` in `tests/test_skills_and_scripts.py` using `os.walk` with exact segment filtering to cover `.along/`, root dotfiles (`.mise.toml`), and `tests/`, checking for byte-level BOM and all forbidden characters.
- Added `test_05b_quality_gates_catch_hidden_dist_bom_and_tests` verifying quality gates catch violations in hidden directories, paths containing substring 'dist', byte-level BOMs, `tests/`, and empty extensionless files.
- Completed issue `bug--quality-gates-skip-hidden-directories.md` and moved to `.along/ISSUES/done/`.

## Code Review & Blast Radius
- Ran `python .along/scripts/test.py`: 271 passed, 1 skipped. Meta-test `tests/test_zz_hermetic_suite.py` verified working tree clean and hermetic.
- Ran `python scripts/sanitize_typography.py --check --include-data`: 420 files scanned, 0 banned typography findings.
- Blast radius confined to testing gates, LICENSE documentation, and alongkit shared constants; existing production engine behaviors remain unbroken.
