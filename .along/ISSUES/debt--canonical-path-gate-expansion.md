---
protocol: along
protocol_version: "4.4.7"
slug: canonical-path-gate-expansion
type: debt
status: open
priority: medium
created: 2026-10-08
updated: 2026-10-08
agent: antigravity
tags: [windows, paths, gates, quality]
blocked_by: []
related: []
---

# Expand canonical path gate to scripts and harden residual path comparisons

Extend the static canonical path verification gate to scripts/ and eliminate all remaining raw os.path.relpath calls and uncanonicalized path comparisons across repository engines.

## Context and Problem
The canonical path hardening (debt--canonical-windows-paths) and root discovery resolution (bug--lexical-path-root-resolution) established clean separation between lexical traversal and semantic path canonicalization in alongkit. However, the static gate (check_canonical_paths) currently inspects only scripts/alongkit/, allowing CLI entrypoints in scripts/ to call raw os.path.relpath without detection. Additionally, residual path comparisons using normcase(os.path.abspath(...)) remain in entities.py and scaffold.py.

## Key Changes Needed
1. Expand `check_canonical_paths` in `scripts/alongkit/gates.py` to scan `scripts/` (including CLI entrypoints).
2. Replace all raw `os.path.relpath` calls in `scripts/*.py` (`along_dep_scan.py`, `along_kb_search.py`, `along_kb_sync.py`, `along_graph_arch.py`, `along_graph_impact.py`, `along_update.py`, `migrate_protocol.py`) with `repo.canonical_relpath` or `repo.safe_relpath`.
3. Replace remaining `normcase(os.path.abspath(...))` string comparisons in `scripts/alongkit/entities.py` and `scripts/alongkit/scaffold.py` with `repo._same_path` or `repo.is_within`.
4. Ensure regression coverage in `tests/test_alongkit.py` and hermetic test suite.

## Acceptance Criteria
- [ ] `check_canonical_paths` scans both `scripts/alongkit/` and `scripts/`
- [ ] Zero raw `os.path.relpath` calls in `scripts/` and `scripts/alongkit/` (verified by `canonical_path_gate`)
- [ ] Residual `normcase(os.path.abspath(...))` in `entities.py` and `scaffold.py` replaced with `repo._same_path` / `repo.is_within`
- [ ] All automated tests pass with 0 failures

