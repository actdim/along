---
protocol: along
date: 2026-09-04
slug: well-known-llms-and-context-discovery
agent: antigravity
branch: main
commit: pending
summary: Deterministic llms.txt and llms-full.txt compilation with .well-known resolution and unified downward context discovery
milestone: v2.2.0-along
issues_advanced: []
issues_completed: [well-known-llms-and-context-discovery]
decisions: []
risks_logged: []
spikes_conducted: []
---

# Session: Well known llms and context discovery

## Summary
Deterministic llms.txt and llms-full.txt compilation with .well-known resolution and unified downward context discovery

## Work Completed
- Document key tasks and achievements.
- Implemented `resolve_llm_targets` in `alongkit.repo` to resolve `llms.txt` and `llms-full.txt` targets across `.well-known/` and context root without drift.
- Unified downward discovery in `alongkit.repo`: `find_agent_contexts` and `find_manifest_projects` without hardcoding `packages/` or `libs/`.
- Refactored `along_update.py` and `along_kb_sync.py` to use `alongkit.repo` discovery functions.
- Implemented deterministic `sync_llms_txt` (preserving custom sections/links) and `sync_llms_full_txt` (deterministic multi-document context aggregation) in `along_kb_sync.py`.
- Added support for `.well-known/` in `along_dep_scan.py` and `along_version_bump.py`.
- Added hermetic tests `test_25_well_known_llms_txt_and_full_txt_sync` and `test_26_canonical_context_and_manifest_discovery`.
- Verified 100% pass rate across 231 tests in test runner.

## Code Review & Blast Radius
- Automated tests verified and passing.
- All 231 tests passing in `.along/scripts/test.py`.
- Zero broken relative markdown links verified via `validate_repo_link_integrity`.
- Updated source hashes in `docs/topic--llm-wiki-architecture.md` and `docs/topic--skills-reference.md`.
- No non-ASCII typography violations. Zero mutations to working tree during hermetic test execution.
