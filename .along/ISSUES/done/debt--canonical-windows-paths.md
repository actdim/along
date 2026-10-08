---
protocol: along
protocol_version: "4.4.7"
slug: canonical-windows-paths
type: debt
status: done
completed: 2026-10-08
priority: high
created: 2026-10-08
updated: 2026-10-08
agent: antigravity
tags: [windows, paths, ci, hardening]
blocked_by: []
related: [ci-windows-closeout-short-paths]
---

# Enforce canonical path resolution across repository engines and test fixtures

Systemic hardening against Windows 8.3 short path (DOS name) and symlink mismatches across all Along engines, gates, and test fixtures.

## Background & Problem
On Windows environments (particularly GitHub Actions runners where `USERPROFILE` is `C:\Users\runneradmin` -> `RUNNER~1`), paths created by Python runtime (`tempfile`, `os.getcwd()`) frequently carry 8.3 short names, whereas Git commands (`git rev-parse`, `git status`) return canonical long paths. Because standard `os.path.relpath` performs pure string-based comparison without NTFS alias resolution, mixing these paths produces catastrophic directory traversal prefixes (`../../../../RUNNER~1/...`).

Previous fixes in `01984aa` and `2cf9ae2` addressed this on a per-subsystem basis (gates, session bindings, closeout). This ticket establishes a repository-wide architectural invariant.

## Acceptance Criteria
- [x] REQ-1: Introduce `canonical_path` and `canonical_relpath` in `scripts/alongkit/repo.py`, and harden `safe_relpath` to canonicalize arguments before relative path calculation.
- [x] REQ-2: Add static audit gate in `along gates check` to detect and forbid raw `os.path.relpath` usage against repository roots across `scripts/alongkit/`.
- [x] REQ-3: Introduce automatic Windows 8.3 short path alias simulation in `tests/hermetic.py` (`make_repo_fixture`) when running on Windows, ensuring local tests execute under the same path conditions as GitHub Actions.
- [x] REQ-4: Unit and regression tests covering `canonical_path`, `canonical_relpath`, and `safe_relpath` across short, long, and cross-drive paths.
- [x] REQ-5: Full test suite passing (zero failures) and typography check clean.
