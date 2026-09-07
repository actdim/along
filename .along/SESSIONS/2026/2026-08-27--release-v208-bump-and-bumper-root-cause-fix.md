---
protocol: along
date: 2026-08-27
slug: release-v208-bump-and-bumper-root-cause-fix
agent: antigravity
branch: main
commit: 58f1c91
summary: Fixed root-cause variable bug in along_bump_version.py (re.sub on u instead of c), verified 100% unit tests pass, and released ALONG-PROTOCOL v2.0.8.
milestone: v2.0.0-along-transition
issues_advanced: []
issues_completed: []
decisions: []
risks_logged: []
spikes_conducted: []
---

# Session Log: 2026-08-27 - Release v2.0.8 & Bumper Root-Cause Fix

## Summary
In this session, we identified and eliminated the root-cause bug inside `along_bump_version.py` that previously caused `migrate_protocol.py` and `along_update.py` to be overwritten with `README.md` text during version bumps. We verified all unit tests and finalized the `v2.0.8` release.

## Root Cause & Fix
- **Root Cause Identified**: In `scripts/along_bump_version.py`, `bump_along_dev_repo()` step 4 assigned `u = re.sub(...)` for `README.md`. Steps 5 and 6 subsequently called `u = re.sub(..., u)` instead of `u = re.sub(..., c)`, inadvertently applying regex to the `README.md` content and writing `README.md` into `migrate_protocol.py` and `along_update.py`.
- **Fix Applied**: Changed steps 5 and 6 to properly operate on `c` (`u = re.sub(..., c)`).
- **Quality Gate Validation**: Automated test suite (`tests/test_skills_and_scripts.py`) verified zero syntax errors, zero markdown inside Python files, and full version consistency across all files.

## Accomplishments
1. Root cause bug in `scripts/along_bump_version.py` and `skills/along-bump-version/along_bump_version.py` permanently resolved.
2. Unit test suite verified (9/9 tests pass in 0.27s).
3. Bumped project and protocol version to `v2.0.8`.
4. Global skills refreshed across all 4 providers (`Claude`, `Codex`, `Antigravity`, `OpenCode`).

## Verification & Code Review
- Unit Tests: `python -m unittest tests/test_skills_and_scripts.py -v` (OK).
- Pre-Commit Gate: Intercepts and tests automatically on `along_commit.py` and `along_bump_version.py`.
