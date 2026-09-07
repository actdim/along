---
protocol: along
date: 2026-09-07
slug: remove-git-locking-workarounds
agent: antigravity
branch: main
commit: pending
summary: Reverted broken GIT_OPTIONAL_LOCKS=0 and diff.autoRefreshIndex=false workarounds across repo code, tooling, and documentation to restore clean Git stat-cache behavior on Windows.
issues_advanced: []
issues_completed: [bug--remove-git-locking-workarounds]
decisions: [ADR-2026-09-07--revert-git-stat-cache-workarounds]
risks_logged: []
spikes_conducted: []
---

# Session: Revert Broken Git Locking Workarounds

## Summary
Investigated and confirmed that `GIT_OPTIONAL_LOCKS=0` and `diff.autoRefreshIndex false` break the Git stat-cache on Windows without solving index corruption during write operations. Removed `GIT_OPTIONAL_LOCKS` from child process environments in `alongkit.proc`, cleaned up `.vscode/settings.json`, and removed workarounds from `install.ps1`, `skills/along-init/SKILL.md`, and `docs/topic--setup-and-workflow.md`. Documented the reversion in ADR-2026-09-07--revert-git-stat-cache-workarounds. Re-ran test suite (269 tests passed hermetically with clean working tree).

## Work Completed
- **Subprocess Environment Clean Up (`scripts/alongkit/proc.py`)**:
  - Removed `"GIT_OPTIONAL_LOCKS": "0"` from `UTF8_CHILD_ENV`.
- **IDE Settings Clean Up (`.vscode/settings.json`)**:
  - Removed `terminal.integrated.env.windows` injecting `GIT_OPTIONAL_LOCKS=0`.
- **Installation and Skill Documentation (`install.ps1`, `skills/along-init/SKILL.md`)**:
  - Removed automated recommendations instructing users to disable `diff.autoRefreshIndex` and set `GIT_OPTIONAL_LOCKS=0`.
- **Knowledge Base Synchronization (`docs/topic--setup-and-workflow.md`, `llms-full.txt`)**:
  - Replaced broken recommendations with genuine NTFS mitigations: antivirus (Windows Defender) / search indexing exclusions for `.git`, and automated 0-byte index self-healing (`git read-tree HEAD`).
  - Added explicit warning against disabling stat-cache flags.
  - Recompiled Knowledge Base and `llms-full.txt` via `along_kb_sync.py`.
- **Decisions Recorded**:
  - Marked ADR-2026-09-06--windows-git-concurrency-and-index-lock-mitigation as superseded.
  - Added ADR-2026-09-07--revert-git-stat-cache-workarounds to `.along/DECISIONS.md`.
- **System and Environment Clean Up**:
  - Removed user environment variable `GIT_OPTIONAL_LOCKS`.
  - Unset `diff.autoRefreshIndex` globally and locally.

- **Antigravity Extension Hotfix & Tracking**:
  - Identified upstream bug in `google.google-antigravity-1.2.0` (`extension.js`) where `touchGitIndexForUri` truncates `.git/index` via `fs.writeFile` in a race with `git.refresh`.
  - Created backup `extension.js.bak` and applied hotfix (`return;` early exit).
  - Created tracking issue `bug--antigravity-extension-git-index-truncation` to monitor future extension updates.

## Verification
- Ran complete project test suite via `python .along/scripts/test.py`.
- All 269 automated tests passed hermetically (0 failures, `test_zz_hermetic_suite` confirmed working tree unchanged without phantom `" M"` diffs).

