---
protocol: along
date: 2026-09-07
slug: link-gates-skip-along-directory
agent: antigravity
branch: main
commit: pending
summary: Fix link rewriter and integrity gates skipping .along/ directory and implement CI JSON reporting
milestone: v3.0.0-global-quality-revision
issues_advanced: []
issues_completed: [link-gates-skip-along-directory]
decisions: []
risks_logged: []
spikes_conducted: []
---

# Session: Link gates skip along directory

## Summary
Fix link rewriter and integrity gates skipping .along/ directory, narrow placeholder exclusions, add --json CI output, block legacy deletion on unresolved references, and enforce the Stable Entry Point Rule.

## Work Completed
- REQ-1 & REQ-2: Updated `rewrite_inbound_links` and `validate_repo_link_integrity` in `scripts/along_kb_sync.py` to walk `.along/` and protocol-relevant dot directories using shared `IGNORED_DIRS` (`scripts/alongkit/repo.py`), eliminating the blanket `not d.startswith('.')` skip.
- REQ-2: Added `.migration-backup` and `.session` to `IGNORED_DIRS` with documented rationales in `scripts/alongkit/repo.py`.
- REQ-3: Narrowed placeholder detection in `scripts/alongkit/markdown.py` (`is_placeholder`) to regex `r"<[^>]+>|{{[^}]+}}"`. Removed concrete article names (`./topic--architecture.md`, `./topic--setup-and-workflow.md`) from `ILLUSTRATIVE_PLACEHOLDERS` in `scripts/along_kb_sync.py`.
- REQ-3: Updated protocol reference links in `skills/along-init/protocol.md` and `AGENTS.md` to canonical `[Title](./topic--<slug>.md)`.
- REQ-4: Added `--json` flag to `scripts/along_kb_sync.py` emitting structured machine-readable reports for CI consumption. Allowed `sync_kb` to run integrity checks and output JSON even when `docs/` is absent.
- REQ-5: Updated `sync_kb` to verify the Global Link Integrity Gate before deleting legacy KB directories (`.along/KB/`, `.agents/KB/`). Collected legacy references in `LinkIntegrityTriple` / `LinkIntegrityResult` and blocked deletion when unresolved references remain. Preserved non-markdown assets in legacy directories from improper rewriting.
- REQ-7: Enforced the Stable Entry Point Rule in `validate_repo_link_integrity`. Links in files outside `.along/` pointing into `.along/` are recorded as violations and suggest canonical `docs/` alternatives.
- REQ-6: Added comprehensive unit tests `test_17b` through `test_17g` in `tests/test_skills_and_scripts.py`.
- Completed issue `bug--link-gates-skip-along-directory.md` and moved to `.along/ISSUES/done/`.

## Code Review & Blast Radius
- Ran full test suite via `python .along/scripts/test.py`: 289 tests passed (0 failed, 1 skipped).
- Meta-tests in `tests/test_zz_hermetic_suite.py` verified the working tree was not mutated by the test suite.
- Verified backwards compatibility of `validate_repo_link_integrity` return types (tuple unpacking for both 2-element and 3-element callers).
