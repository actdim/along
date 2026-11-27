---
protocol: along
protocol_version: "4.9.1"
date: 2026-11-27
slug: decouple-protocol-and-toolchain-versioning
agent: antigravity
branch: main
commit: 68787c4
summary: Decoupled CURRENT_PROTOCOL_VERSION from CURRENT_VERSION across version.py, pyproject.toml, along_version_bump.py, doctor diagnostics, and release tests
issues_advanced: []
issues_completed: [debt--decouple-protocol-and-toolchain-versioning]
decisions: []
---

# Session: Decouple protocol and toolchain versioning

## Summary
Decoupled CURRENT_PROTOCOL_VERSION from CURRENT_VERSION across version.py, pyproject.toml, along_version_bump.py, doctor diagnostics, and release tests

## Decisions
- None (confirmed at wrap: no architectural decisions).

## Blackboard Record

Execution mode: role-based; plan revision 2; approved: true.

| Step | Title | Status | Retries | Review |
| --- | --- | --- | --- | --- |
| 1 | Step 1 | passed | 0 | yes |
| 2 | Step 2 | passed | 0 | yes |
| 3 | Step 3 | passed | 0 | yes |
| 4 | Step 4 | passed | 0 | yes |

Plan: kept with the issue (`plan/plan.md`, 1 revision(s)).

### Execution Trace

#### Execution Trace: decouple-protocol-and-toolchain-versioning
- 2026-11-24T20:14:24Z plan approved (along plan approve) approved_via: cli-unverified, plan_sha256: 880d630f0c57
- 2026-11-24T20:14:25Z step 1: pending -> in-progress
- 2026-11-24T20:14:53Z step 1: in-progress -> passed
- 2026-11-24T20:14:53Z step 2: pending -> in-progress
- 2026-11-24T20:15:54Z step 2: in-progress -> passed
- 2026-11-24T20:15:55Z step 3: pending -> in-progress
- 2026-11-24T20:16:09Z step 3: in-progress -> passed
- 2026-11-24T20:16:10Z step 4: pending -> in-progress
- 2026-11-24T20:17:58Z step 4: in-progress -> passed
- 2026-11-24T20:18:13Z test FAIL (Wrap Quality Gate)
- 2026-11-24T20:26:51Z test FAIL (Wrap Quality Gate)
- 2026-11-24T21:03:29Z test FAIL (Pre-Commit Quality Gate)
- 2026-11-27T23:27:16Z plan approved (approved issue plan; approved_via: issue-plan)

### Review step-1

#### Step 1 Review: Core Version Constants, Packaging, and CLI

VERDICT: PASS

##### Checks
- `scripts/alongkit/version.py`: `CURRENT_PROTOCOL_VERSION = "4.9.1"`, `CURRENT_VERSION = "4.9.1"`, `__version__ = CURRENT_VERSION`, `MIN_SUPPORTED_PROTOCOL_VERSION = "4.8.0"`, `is_protocol_supported` implemented using `semver.parse`.
- `scripts/alongkit/__init__.py`: exports `CURRENT_PROTOCOL_VERSION`, `CURRENT_VERSION`, `__version__`.
- `pyproject.toml`: `[tool.hatch.version]` pattern updated to `CURRENT_VERSION = "(?P<version>[^"]+)"`.
- `scripts/alongkit/cli.py`: `along --version` verified (`along 4.9.1 (protocol v4.9.1)`).

Gate Execution Manifest:
- Workspace Isolation: EXECUTED (PASS) [mode: inherit (default)]
- File Integrity: EXECUTED (PASS)
- Automated Tests: SKIPPED (full suite deferred to Step 4)
- Diff Scope Audit: EXECUTED (PASS)
- Requirement Traceability: EXECUTED (PASS) [REQ-1, REQ-2, REQ-5]
- Blast Radius: DEGRADED (PASS) [static search]
- Clean Typography: EXECUTED (PASS)

### Review step-2

#### Step 2 Review: Release Engine Refactoring (`scripts/along_version_bump.py`)

VERDICT: PASS

##### Checks
- Migrated `main()` to `argparse` preserving `bump_arg`, `-c`/`--commit`, `-p`/`--push`, `-cp`/`-pc`, `--fix-typography`, `-n`/`--no-verify`, `--skip-ci`, `--reason`, `--carry-over`, and adding `--protocol TYPE_OR_VER`.
- `bump_along_dev_repo` and `detect_and_bump_project` decouple toolchain (`CURRENT_VERSION`, `package.json`, `README.md` header, `llms-full.txt` header, milestones/changelog/tag) from protocol (`CURRENT_PROTOCOL_VERSION`, `.protocol-version`, `AGENTS.md`, `protocol.md`, `VISION.md`, `README.md` and `llms-full.txt` protocol mentions, `docs/topic--*.md`).
- Protocol-only mode skips `update_along_milestones`, `update_changelog`, and release tag creation; commits with `chore(protocol): ALONG-PROTOCOL v{new_version}` when `-c` is passed.
- Dead regex substitutions (`migrate_protocol.py`, `along_kb_sync.py`, `along_update.py`, `.well-known/`, `Skills & Slash Commands (v...)`) removed.
- `python scripts/along_version_bump.py --help` exits 0 with expected options.

Gate Execution Manifest:
- Workspace Isolation: EXECUTED (PASS) [mode: inherit (default)]
- File Integrity: EXECUTED (PASS)
- Automated Tests: SKIPPED (full suite and hermetic tests in Step 4)
- Diff Scope Audit: EXECUTED (PASS)
- Requirement Traceability: EXECUTED (PASS) [REQ-3, REQ-4]
- Blast Radius: DEGRADED (PASS) [static search]
- Clean Typography: EXECUTED (PASS)

### Review step-3

#### Step 3 Review: Diagnostics Alignment (`scripts/alongkit/commands/doctor.py`)

VERDICT: PASS

##### Checks
- `audit_subproject_protocol_versions`: preserves `mismatch` (`str(not is_root and ver != root_ver)`) for backward compatibility and adds `supported` (`str(version.is_protocol_supported(ver))`).
- `handle_doctor_command`: evaluates `version.is_protocol_supported(root_v)` unconditionally outside `if len(sub_contexts) > 1:`, emitting `[WARN]` and incrementing `warnings` for unsupported root protocol versions even in single-root repositories.
- `along_update.py:762` and `migrate_protocol.py:815`: verified to already use `CURRENT_PROTOCOL_VERSION`.

Gate Execution Manifest:
- Workspace Isolation: EXECUTED (PASS) [mode: inherit (default)]
- File Integrity: EXECUTED (PASS)
- Automated Tests: SKIPPED (full suite and doctor tests in Step 4)
- Diff Scope Audit: EXECUTED (PASS)
- Requirement Traceability: EXECUTED (PASS) [REQ-5]
- Blast Radius: DEGRADED (PASS) [static search]
- Clean Typography: EXECUTED (PASS)

### Review step-4

#### Step 4 Review: Test Suite Adaptation & Verification

VERDICT: PASS

##### Checks
- `tests/test_skills_and_scripts.py`: `test_04_protocol_version_consistency` validates `README.md` header and `pyproject.toml` `[tool.hatch.version]` against `CURRENT_VERSION`, and protocol files (`protocol.md`, `AGENTS.md`, `.protocol-version`, `README.md` protocol mention) against `CURRENT_PROTOCOL_VERSION`.
- `tests/test_version_bump.py`: added `TestDecoupledDevRepoBump` covering hermetic toolchain `patch` bump, `--protocol minor` bump, `argparse` combined flags (`-cp`, `--carry-over`), and `is_protocol_supported`.
- `tests/test_lint_unstaged.py`: added `test_along_doctor_warns_on_unsupported_root_protocol`.
- Executed `python .along/scripts/test.py -q tests/test_version_bump.py tests/test_release_engine.py tests/test_migration.py tests/test_lint_unstaged.py tests/test_rules.py tests/test_skills_and_scripts.py` (with `ALONGKIT_PROJECT_ENV=1` due to `.venv` Python 3.13 DLL init failure): **138 tests ran in 33.739s, OK (skipped=2)**.
- Executed `along sanitize` (1387 files, 0 banned chars), `python scripts/along_kb_sync.py --strict` (705 links verified), and `along hook verify --strict` (PASSED).

Gate Execution Manifest:
- Workspace Isolation: EXECUTED (PASS) [mode: inherit (default)]
- File Integrity: EXECUTED (PASS)
- Automated Tests: EXECUTED (PASS) [138 tests in 6 suites, skipped=2]
- Diff Scope Audit: EXECUTED (PASS)
- Requirement Traceability: EXECUTED (PASS) [REQ-1, REQ-2, REQ-3, REQ-4, REQ-5, REQ-6]
- Blast Radius: DEGRADED (PASS) [static search]
- Documentation Parity: EXECUTED (PASS)
- Clean Typography: EXECUTED (PASS)
