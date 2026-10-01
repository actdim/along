---
protocol: along
protocol_version: "4.4.1"
date: 2026-09-30
slug: prose-rules-to-deterministic-checks
agent: claude-code
branch: main
commit: 27c6642
summary: Audit of every managed AGENTS.md rule (class a/b/c) in docs; 7 git/ci repository-state gates (alongkit.repochecks) run by along gates check; prose for enforced rules cut to one-line gate references (uncommitted, per user)
issues_advanced: []
issues_completed: [debt--prose-rules-to-deterministic-checks]
decisions: []
risks_logged: []
spikes_conducted: []
milestone: v4.5.0-multi-user-merge-automation
---

# Session: Prose rules to deterministic checks

## Summary

Fifth v4.5.0 task by priority, single-agent sequential, workspace: inherit, no commits per user.

## Initial Implementation Plan (Baseline)

1. Classify every managed-block rule; publish the table in `docs/topic--runtime-hooks-and-gates.md` (REQ-1, REQ-2).
2. `alongkit/repochecks.py`: path/content checks for class (b) rules; catalogue entries with
   `enforcement: [git, ci]` reusing the existing layer field (REQ-3, REQ-5).
3. `gitgates.check_repo_state`: pre-commit over staged blobs, `--ci` over every tracked file.
4. Shorten prose for enforced rules to one line with the gate tag (REQ-4).

## Execution & Loop Trace (Fixes & Re-plans)

- New gates: `windows_safe_filenames`, `untracked_exports`, `code_fence_language`,
  `portable_links`, `stable_entry_point`, `issue_lifecycle`, `no_tracked_secrets`.
- Runtime pipeline now skips gates without the `runtime` layer (`get_all_declarative_gates`).
- Stable entry point and `file://` were already checked by `along kb-sync --check`, but that CI
  step is report-only, so they got hard git/ci gates too.
- `ISSUES.md` size was already enforced by `along context-budget` (class a).
- Live repo fixes: 10 fences without a language got `text`; 12 fake secrets in the redactor
  tests got the `along: allow-no-tracked-secrets` pragma.
- Canonical-key references stay class (b), deferred to `feat--entity-reference-integrity-gate`.
- AGENTS.md 13010 -> 12724 bytes; protocol.md 10954 -> 10668 bytes.

## Verification Walkthrough & Gate Manifest

- `along test -q`: 804 tests OK (11 new in `tests/test_repo_state_gates.py`).
- `along hook verify`: PASSED. `along gates check --ci --no-links`: all checks passed.

```text
Gate Execution Manifest:
- Workspace Isolation: EXECUTED (PASS) [mode: inherit (default)]
- File Integrity: EXECUTED (PASS)
- Automated Tests: EXECUTED (PASS) [along test -q, 804 OK]
- Diff Scope Audit: EXECUTED (PASS)
- Requirement Traceability: EXECUTED (PASS) [REQ-1..REQ-5]
- Blast Radius: DEGRADED (PASS) [static search: get_all_declarative_gates runtime filter; check_pre_commit/check_ci callers]
- Documentation Parity: EXECUTED (PASS) [runtime-hooks, declarative-gates, AGENTS.md/protocol.md, CI workflow comment]
- Clean Typography: EXECUTED (PASS)
```
