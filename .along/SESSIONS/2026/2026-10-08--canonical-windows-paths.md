---
protocol: along
protocol_version: "4.4.7"
date: 2026-10-08
slug: canonical-windows-paths
agent: antigravity
branch: main
commit: 2cf9ae2
summary: Enforce canonical path resolution across repository engines and test fixtures
issues_advanced: []
issues_completed: [debt--canonical-windows-paths]
decisions: []
risks_logged: []
spikes_conducted: []
---

# Session: Canonical windows paths

## Summary
Enforce canonical path resolution across repository engines and test fixtures

## Decisions
- None (confirmed at wrap: no architectural decisions).

## Blackboard Record

Execution mode: role-based; plan revision 1; approved: true.

| Step | Title | Status | Retries | Review |
| --- | --- | --- | --- | --- |
| 1 | Implement canonical path primitives in alongkit.repo and unit tests | passed | 0 | yes |
| 2 | Integrate Win32 short path alias simulation into hermetic test fixture | passed | 0 | yes |
| 3 | Implement static AST audit gate for uncanonicalized relpath calls in alongkit.gates | passed | 1 | yes |

### Attributed Files

| Path | Kind | Edits | Last edit | Sessions |
| --- | --- | --- | --- | --- |
| `.along/ISSUES/debt--canonical-windows-paths.md` | state | 2 | 2026-10-08T09:52:17Z | antigravity--a46c1793-637e-4630-bfb2-90844ac596a3 |
| `scripts/alongkit/__init__.py` | source | 1 | 2026-10-08T09:32:37Z | antigravity--a46c1793-637e-4630-bfb2-90844ac596a3 |
| `scripts/alongkit/budget.py` | source | 1 | 2026-10-08T09:40:11Z | antigravity--a46c1793-637e-4630-bfb2-90844ac596a3 |
| `scripts/alongkit/closeout.py` | source | 3 | 2026-10-08T09:40:35Z | antigravity--a46c1793-637e-4630-bfb2-90844ac596a3 |
| `scripts/alongkit/entities.py` | source | 9 | 2026-10-08T09:41:53Z | antigravity--a46c1793-637e-4630-bfb2-90844ac596a3 |
| `scripts/alongkit/gates.py` | source | 3 | 2026-10-08T09:48:23Z | antigravity--a46c1793-637e-4630-bfb2-90844ac596a3 |
| `scripts/alongkit/gitgates.py` | source | 4 | 2026-10-08T10:00:32Z | antigravity--a46c1793-637e-4630-bfb2-90844ac596a3 |
| `scripts/alongkit/hooks/predicates.py` | source | 6 | 2026-10-08T09:43:22Z | antigravity--a46c1793-637e-4630-bfb2-90844ac596a3 |
| `scripts/alongkit/install.py` | source | 2 | 2026-10-08T09:44:03Z | antigravity--a46c1793-637e-4630-bfb2-90844ac596a3 |
| `scripts/alongkit/lifecycle.py` | source | 3 | 2026-10-08T09:56:56Z | antigravity--a46c1793-637e-4630-bfb2-90844ac596a3 |
| `scripts/alongkit/merge.py` | source | 1 | 2026-10-08T09:44:32Z | antigravity--a46c1793-637e-4630-bfb2-90844ac596a3 |
| `scripts/alongkit/migration.py` | source | 1 | 2026-10-08T09:44:42Z | antigravity--a46c1793-637e-4630-bfb2-90844ac596a3 |
| `scripts/alongkit/repo.py` | source | 4 | 2026-10-08T09:32:14Z | antigravity--a46c1793-637e-4630-bfb2-90844ac596a3 |
| `scripts/alongkit/rules.py` | source | 3 | 2026-10-08T09:45:24Z | antigravity--a46c1793-637e-4630-bfb2-90844ac596a3 |
| `scripts/alongkit/scaffold.py` | source | 2 | 2026-10-08T09:45:44Z | antigravity--a46c1793-637e-4630-bfb2-90844ac596a3 |
| `scripts/alongkit/session.py` | source | 4 | 2026-10-08T09:55:25Z | antigravity--a46c1793-637e-4630-bfb2-90844ac596a3 |
| `scripts/alongkit/worktree.py` | source | 2 | 2026-10-08T09:47:04Z | antigravity--a46c1793-637e-4630-bfb2-90844ac596a3 |
| `tests/hermetic.py` | source | 1 | 2026-10-08T09:35:38Z | antigravity--a46c1793-637e-4630-bfb2-90844ac596a3 |
| `tests/test_alongkit.py` | source | 2 | 2026-10-08T09:49:30Z | antigravity--a46c1793-637e-4630-bfb2-90844ac596a3 |
| `tests/test_lifecycle_hooks.py` | source | 2 | 2026-10-08T09:57:14Z | antigravity--a46c1793-637e-4630-bfb2-90844ac596a3 |

### Plan

#### Living Plan: canonical-windows-paths

Title: Enforce canonical path resolution across repository engines and test fixtures

##### Execution Mode
Role-Based (along-team)

##### Steps
- [ ] Step 1: Implement `canonical_path` and `canonical_relpath` in `scripts/alongkit/repo.py`, harden `safe_relpath`, and add comprehensive unit tests in `tests/test_alongkit.py` (REQ-1, REQ-4)
- [ ] Step 2: Integrate Win32 `GetShortPathNameW` into `tests/hermetic.py` (`make_repo_fixture`) on Windows for environment parity, and verify throwaway fixtures run cleanly (REQ-3)
- [ ] Step 3: Implement AST-based static audit gate for uncanonicalized `os.path.relpath` in `scripts/alongkit/gates.py` and hook into `along gates check` / `gitgates.py` (REQ-2, REQ-5)

### Research

#### Research & Findings: canonical-windows-paths

##### Target Symbols and Files
- `scripts/alongkit/repo.py`:
  - `safe_relpath` (lines 396-406): delegates directly to `os.path.relpath(path, start)` without canonicalizing 8.3 short names or symlinks.
  - `canonical_path(path: str) -> str`: missing. Needs to return `os.path.realpath(os.path.abspath(path))`.
  - `canonical_relpath(path: str, start: str) -> str`: missing. Needs to canonicalize both operands, handle cross-drive paths cleanly, and normalize to forward slashes.
  - `_same_path` (lines 72-74) and `is_within` (lines 244-254): compare without resolving 8.3 short names; need `canonical_path`.
- `tests/hermetic.py`:
  - `make_repo_fixture` (lines 117-159): allocates `tempfile.mkdtemp(prefix=prefix)`. When `sys.platform == 'win32'`, invoke `ctypes.windll.kernel32.GetShortPathNameW` to turn the fixture path into an 8.3 short path. This guarantees local Windows tests encounter the exact same path alias conditions as GitHub Actions runners.
- `scripts/alongkit/gates.py`:
  - Static AST audit: follows the pattern of `find_exception_violations_in_code` and `exception_handling_gate`.
  - Scans `scripts/alongkit/` for `os.path.relpath` calls, enforcing `repo.canonical_relpath` or `repo.safe_relpath` across all repository engines.
  - Existing calls in `gates.py` lines 500 and 524 can be upgraded to `repo.canonical_relpath`.

##### Constraints & Risks
- Performance: `os.path.realpath` queries filesystem metadata on Windows. In hot loops or deep directory walks, caching or minimal redundant canonicalization is preferred.
- Cross-drive paths: on Windows, `os.path.relpath` raises `ValueError` when paths are on different drives (e.g. `C:\...` vs `D:\...`). `canonical_relpath` must catch `ValueError` and fall back to POSIX-normalized absolute canonical path.
- Non-existent files: `os.path.realpath` resolves existing leading directories and appends trailing components. Works safely for prospective paths.
- Clean ASCII: all code, docstrings, and comments must strictly adhere to clean ASCII.

##### Architectural Patterns
- Single source of truth for path canonicalization in `alongkit.repo`.
- AST-level gate enforcement in `alongkit.gates` to prevent regressions.
- Environment parity in `tests/hermetic.py` to prevent CI-only surprise failures.

### Execution Trace

#### Execution Trace: canonical-windows-paths
- 2026-10-08T09:22:22Z edit .along/ISSUES/debt--canonical-windows-paths.md
- 2026-10-08T09:26:46Z plan approved (along plan approve)
- 2026-10-08T09:26:50Z step 1: pending -> in-progress
- 2026-10-08T09:32:14Z edit scripts/alongkit/repo.py (x4)
- 2026-10-08T09:32:37Z edit scripts/alongkit/__init__.py
- 2026-10-08T09:33:19Z edit tests/test_alongkit.py
- 2026-10-08T09:34:06Z step 1: in-progress -> passed
- 2026-10-08T09:34:14Z step 2: pending -> in-progress
- 2026-10-08T09:35:38Z edit tests/hermetic.py
- 2026-10-08T09:36:27Z step 2: in-progress -> passed
- 2026-10-08T09:36:32Z step 3: pending -> in-progress
- 2026-10-08T09:40:11Z edit scripts/alongkit/budget.py
- 2026-10-08T09:40:35Z edit scripts/alongkit/closeout.py (x3)
- 2026-10-08T09:41:53Z edit scripts/alongkit/entities.py (x9)
- 2026-10-08T09:42:05Z edit scripts/alongkit/gates.py
- 2026-10-08T09:42:12Z edit scripts/alongkit/gitgates.py
- 2026-10-08T09:43:22Z edit scripts/alongkit/hooks/predicates.py (x6)
- 2026-10-08T09:44:03Z edit scripts/alongkit/install.py (x2)
- 2026-10-08T09:44:32Z edit scripts/alongkit/merge.py
- 2026-10-08T09:44:42Z edit scripts/alongkit/migration.py
- 2026-10-08T09:45:24Z edit scripts/alongkit/rules.py (x3)
- 2026-10-08T09:45:44Z edit scripts/alongkit/scaffold.py (x2)
- 2026-10-08T09:46:36Z edit scripts/alongkit/session.py (x3)
- 2026-10-08T09:47:04Z edit scripts/alongkit/worktree.py (x2)
- 2026-10-08T09:48:23Z edit scripts/alongkit/gates.py (x2)
- 2026-10-08T09:48:56Z edit scripts/alongkit/gitgates.py (x2)
- 2026-10-08T09:49:30Z edit tests/test_alongkit.py
- 2026-10-08T09:52:07Z step 3: in-progress -> passed
- 2026-10-08T09:52:17Z edit .along/ISSUES/debt--canonical-windows-paths.md
- 2026-10-08T09:55:17Z denied [team_step_active] replace_file_content: along-team Step Violation [gate: team-step-active]: 'canonical-windows-paths' runs the along-team step loop, but no step is in progress, so 'scripts/alongkit...
- 2026-10-08T09:55:21Z step 3: passed -> in-progress
- 2026-10-08T09:55:21Z step 3: retry 1/2
- 2026-10-08T09:55:25Z edit scripts/alongkit/session.py
- 2026-10-08T09:56:56Z edit scripts/alongkit/lifecycle.py (x3)
- 2026-10-08T09:57:14Z edit tests/test_lifecycle_hooks.py (x2)
- 2026-10-08T10:00:32Z edit scripts/alongkit/gitgates.py
- 2026-10-08T10:04:05Z step 3: in-progress -> passed
- 2026-10-08T10:04:28Z test pass (along test)

### Review step-1

#### Step 1 Review: Canonical Path Primitives & Unit Tests

##### Status: PASS

##### Criteria Evaluation
- REQ-1 (Canonical Primitives):
  - `canonical_path(path: str) -> str` implemented in `scripts/alongkit/repo.py`: resolves symlinks, 8.3 short names, and relative references into a canonical path via `os.path.realpath(os.path.abspath(path))`.
  - `canonical_relpath(path: str, start: str) -> str` implemented in `scripts/alongkit/repo.py`: canonicalizes both paths, returns relative path formatted with forward slashes (`/`), and gracefully falls back to canonical normalized absolute path on cross-drive Windows paths.
  - `safe_relpath(path: str, start: str) -> str` hardened: resolves canonical paths before computing relative paths, eliminating traversal artifacts (`..`) when comparing 8.3 short names and long names.
  - `_same_path` and `is_within` updated to use `canonical_path`, ensuring short/long path equivalency on Windows.
  - Primitives exported in `scripts/alongkit/__init__.py`.
- REQ-4 (Unit Tests):
  - Unit tests added to `tests/test_alongkit.py` (`TestRepositoryPaths`):
    - `test_canonical_path_basic_behavior`: tests empty path and absolute normalization.
    - `test_canonical_relpath_and_safe_relpath_basic`: tests nested child files, same directory (`.`), and empty paths.
    - `test_canonical_relpath_and_safe_relpath_cross_drive`: tests cross-drive resilience on Windows (`C:` vs `Z:`).
    - `test_windows_8dot3_short_path_resolution`: uses Win32 `GetShortPathNameW` on Windows to create short-path alias and verifies identical canonical paths, `_same_path` equality, `is_within` containment, and absence of `..` artifacts in `safe_relpath` and `canonical_relpath`.
- REQ-5 (Verification & Typography):
  - Ran `python .along/scripts/test.py test_alongkit.py`: 89 tests passing, 0 failures.
  - Ran `python scripts/sanitize_typography.py . --check`: 804 files scanned, 0 banned characters.

##### Next Step
- Step 2: Integrate Win32 `GetShortPathNameW` into `tests/hermetic.py` (`make_repo_fixture`) on Windows for environment parity.

### Review step-2

#### Step 2 Review: Win32 Short Path Alias Simulation in Hermetic Test Fixture

##### Status: PASS

##### Criteria Evaluation
- REQ-3 (Windows 8.3 Short Path Simulation):
  - Implemented `to_short_path(path: str) -> str` in `tests/hermetic.py`: queries Win32 `GetShortPathNameW` via ctypes when `sys.platform == 'win32'` and returns the 8.3 short name alias.
  - Integrated `to_short_path` into `make_repo_fixture` (enabled by default via `simulate_short_path=True`).
  - Integrated `to_short_path` into `isolated_home()`, ensuring throwaway user profile directories on Windows simulate the GitHub Actions `RUNNER~1` environment locally.
  - Verified `shutil.rmtree` cleans up short-path throwaway fixtures without leakage.
- REQ-5 (Verification & Typography):
  - Ran `python .along/scripts/test.py test_zz_hermetic_suite.py`: 3 tests passing, 0 failures, verified no test mutated the real working tree.
  - Ran `python .along/scripts/test.py test_parallel_closeout.py`: all 35 complex parallel closeout scenario tests passed cleanly under the simulated 8.3 short path environment.
  - Ran `python scripts/sanitize_typography.py . --check`: clean typography across the entire repository.

##### Next Step
- Step 3: Implement static AST audit gate for uncanonicalized `os.path.relpath` in `scripts/alongkit/gates.py` and hook into `along gates check` / `gitgates.py`.

### Review step-3

#### Step 3 Review: Static AST Audit Gate & Repository Hardening

##### Status: PASS

##### Criteria Evaluation
- REQ-2 (AST Static Audit Gate):
  - Implemented `find_relpath_violations_in_code` and `check_canonical_paths` in `scripts/alongkit/gates.py`:
    - Parses Python source files using `ast.parse`.
    - Detects calls to `os.path.relpath` and bare `relpath`.
    - Supports inline suppression via `# along: allow-relpath`.
    - Automatically scans `scripts/alongkit/` (excluding `repo.py` where the canonical primitives are implemented).
  - Implemented `canonical_path_gate` in `scripts/alongkit/gates.py` and hooked it into test runner pre-flight quality gates in `.along/scripts/test.py`.
  - Hooked `check_canonical_paths` into `check_pre_commit` and `check_ci` in `scripts/alongkit/gitgates.py`.
  - Cleaned all uncanonicalized `os.path.relpath` usages across `scripts/alongkit/`:
    - `budget.py`, `closeout.py`, `entities.py`, `gates.py`, `gitgates.py`, `hooks/predicates.py`, `install.py`, `merge.py`, `migration.py`, `rules.py`, `scaffold.py`, `session.py`, `worktree.py`.
    - In `hooks/predicates.py`, replaced brittle `not os.path.relpath(ctx, root).startswith("..")` with `repo.is_within(ctx, root)`, preventing cross-drive traversal exceptions.
- REQ-4 (Gate Unit Tests):
  - Added `TestCanonicalPathGate` (6 unit tests) to `tests/test_alongkit.py`:
    - `test_detects_os_path_relpath`
    - `test_detects_imported_relpath`
    - `test_honors_suppression_comment`
    - `test_ignores_unrelated_calls`
    - `test_handles_syntax_error_gracefully`
    - `test_alongkit_modules_are_clean`
- REQ-5 (Verification & Typography):
  - Ran `python .along/scripts/test.py test_alongkit.py`: 95 unit tests passing, zero failures.
  - Ran `python scripts/along_exec.py gates check`: all checks passed.
  - Ran `python scripts/along_exec.py gates check --ci --no-links`: all checks passed.
  - Ran full test suite `python .along/scripts/test.py`: 1126 tests passed, zero failures (2 skipped).
  - Ran `python scripts/sanitize_typography.py . --check`: 804 files scanned, zero banned characters.

##### Step Summary
All 3 steps of the team plan are fully completed, verified, and passing quality gates across the entire repository test suite.
