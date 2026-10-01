---
protocol: along
protocol_version: "4.4.1"
date: 2026-09-29
slug: git-level-gate-enforcement
agent: claude-code
branch: main
commit: 27c6642
summary: Runtime-agnostic gate enforcement - opt-in git hooks (along hooks install --git), along gates check (--hook / --ci), enforcement layers in the gate catalogue, CI job (uncommitted, per user)
issues_advanced: []
issues_completed: [feat--git-level-gate-enforcement]
decisions: [ADR-2026-09-29--opt-in-git-hooks-supersede-zero-git-hooks]
risks_logged: []
spikes_conducted: []
milestone: v4.5.0-multi-user-merge-automation
---

# Session: Git-level and CI gate enforcement

## Summary

Second v4.5.0 task by priority, via `/along-team` (single-agent sequential, workspace:
inherit, no commits per user). The user chose option 1: opt-in git hooks plus CI, which
supersedes the prose-only "Zero Git Hooks" invariant. The same invariant also banned merge
drivers, which contradicted `feat--git-merge-drivers-and-setup` from earlier in this
session; the user asked to clarify it (drivers are per-clone `.git/config`, not hooks).

## Initial Implementation Plan (Baseline)

1. ADR + catalogue: `enforcement: [runtime, git, ci]` in `default_gates.yaml`, parsed and
   validated in `hooks/declarative.py`; binding regex also accepts `(refs #slug)` (REQ-3).
2. `alongkit/gitgates.py`: added-line diff checks, message checks, projection freshness in a
   temp snapshot (index for pre-commit, tree for CI), hook installer (REQ-1, REQ-2, REQ-4).
3. CLI: `along gates check`, `along hooks install --git [--uninstall]`, enforcement matrix in
   `along hook verify`; CI step in `.github/workflows/tests.yml` (REQ-2, REQ-3).
4. Docs (README caveat, runtime-hooks invariant, cli-reference, declarative-gates) and tests (REQ-5).

## Execution & Loop Trace (Fixes & Re-plans)

- Found that the runtime `commit_issue_binding` regex only accepted `[type--slug]` while
  `/along-commit` writes `(refs #slug)`; the audit log shows repeated denials. Regex widened.
- Shared `install.engine_script()` extracted; `merge.driver_command` now uses it.
- Fix loop 1: the Write tool turned a backslash-u-2014 escape into a literal em dash in the test
  file (typography test failed); replaced with `chr(0x2014)`. Test fixtures that contain
  conflict markers / stub comments are built at runtime so the new hook can commit them.

## Verification Walkthrough & Gate Manifest

- `along test -q`: 759 tests OK (18 new in `tests/test_git_gate_enforcement.py`, including
  real `git commit` runs through installed hooks in temp repos).
- Live repo, read-only: `along gates check` clean on the (empty) staged set;
  `along gates check --ci --range HEAD~6..HEAD --no-links` flags the real unbound commit
  9db6147. `along hook verify`: PASSED, matrix printed.
- The CI workflow step was not executed on GitHub (nothing pushed).

```text
Gate Execution Manifest:
- Workspace Isolation: EXECUTED (PASS) [mode: inherit (default)]
- File Integrity: EXECUTED (PASS)
- Automated Tests: EXECUTED (PASS) [along test -q, 759 OK]
- Diff Scope Audit: EXECUTED (PASS)
- Requirement Traceability: EXECUTED (PASS) [REQ-1..REQ-5]
- Blast Radius: DEGRADED (PASS) [static search: declarative parser, traceability report, along_hook install, along_exec, merge.driver_command]
- Documentation Parity: EXECUTED (PASS) [README, runtime-hooks-and-gates, declarative-gates, cli-reference]
- Clean Typography: EXECUTED (PASS)
```

## Follow-ups

- Pushing to main now runs `along gates check --ci` on `<before>..HEAD`; unbound commits
  (for example a hand-written `chore(...)` without `(refs #slug)`) will fail the job.
- Hooks are not installed in this repository; run `along hooks install --git` to opt in.
