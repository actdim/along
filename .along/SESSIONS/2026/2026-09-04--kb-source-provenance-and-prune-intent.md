---
protocol: along
date: 2026-09-04
slug: kb-source-provenance-and-prune-intent
agent: antigravity
branch: main
commit: pending
summary: Eliminated .archive/ directory, implemented in-place source provenance, drift detection, --prune-intent gate, and non-destructive llms.txt sync
milestone: v2.2.0-along
issues_advanced: []
issues_completed: [feat--kb-source-provenance-and-reconstruction]
decisions: []
risks_logged: []
spikes_conducted: []
---

# Session: Kb source provenance and prune intent

## Summary
Eliminated .archive/ directory, implemented in-place source provenance, drift detection, --prune-intent gate, and non-destructive llms.txt sync

## Work Completed
- Document key tasks and achievements.
- **Eliminated .archive/**: Removed directory creation, moving, and archiving logic from `scripts/along_kb_sync.py` and `scripts/migrate_protocol.py`. Raw sources stay in-place without modification.
- **Source Provenance & Drift Detection**: Added SHA-256 content hashing normalized to LF newlines (`compute_content_hash`). Stored provenance in front-matter `sources: [{path, hash}]`. If a source is modified, `along_kb_sync.py` flags `[DRIFT]` with expected and current hash prefixes.
- **Intent Gate & Content Reduction Safety**: Added safety guard against accidental document deletion: if an article shrinks by >25% and >=10 lines compared to Git `HEAD`, `along_kb_sync.py` aborts with exit code 2 unless `--prune-intent [REASON]` or `--allow-shrink` is passed.
- **Smart llms.txt Synchronization**: Built non-destructive updater that refreshes `## Documentation Links` to reflect active `docs/topic--*.md` articles while preserving all custom titles, descriptions, and user-defined external sections.
- **Audited Knowledge Base**: Populated exact source paths and SHA-256 hashes across all 8 canonical articles in `docs/topic--*.md`.
- **Protocol & Skills Synchronization**: Updated `skills/along-kb-sync/SKILL.md`, `skills/along-init/protocol.md`, and `AGENTS.md` to document the in-place provenance paradigm.
- **Unit Test Suite**: Added 3 new comprehensive hermetic unit tests (`test_22_sources_provenance_and_drift_detection`, `test_23_content_reduction_intent_gate`, `test_24_smart_llms_txt_sync`), bringing total tests to 229 with 100% passing.

## Code Review & Blast Radius
- Automated tests verified and passing.
- All 229 tests in `python .along/scripts/test.py -q` pass cleanly without errors or working tree mutation.
- Verified that all link integrity gates pass across the entire repository (64 links checked, 0 broken).
- Strict ASCII typography preserved across all modified documents and code files.
