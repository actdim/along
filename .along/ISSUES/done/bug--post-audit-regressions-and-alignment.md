---
protocol: along
protocol_version: "4.2.0"
slug: post-audit-regressions-and-alignment
type: bug
status: done
completed: 2026-10-12
priority: critical
created: 2026-10-12
updated: 2026-10-12
agent: antigravity
tags: [regression, security, toolnature, gates, bootstrap, docs, alignment]
milestone: v4.5.0-multi-user-merge-automation
blocked_by: []
related: [debt--post-audit-core-hardening]
affects: [scripts/alongkit/session.py, scripts/along_exec.py, scripts/alongkit/hooks/predicates.py, scripts/alongkit/hooks/toolnature.py, scripts/alongkit/hooks/shellparse.py, scripts/alongkit/verify.py, scripts/alongkit/bootstrap.py]
---

# Fix Regressions in External/Destructive Commands and Align Audit Implementations

## Problem

Commit b62fb4a introduced a critical regression and left several audit discrepancies:
1. External commands (git push, gh pr create, npm publish) and destructive commands are blocked permanently because is_destructive_confirmed and is_external_confirmed are never set; the flags --confirm-destructive and --confirm-external do not exist on `along plan approve`.
2. `_slugs_equal` and `_bare_slug` in `session.py` break issue type isolation by stripping prefixes (e.g. feat--x matches bug--x).
3. Path checking for rm / Remove-Item uses brittle token regexes rather than path normalization against the repo root (missing rm -rf ~/.ssh, /etc, ../other-repo, etc.).
4. Dangerous git -c keys list is incomplete (missing credential.helper, include.path, diff.external, core.hooksPath, filter.*, and --config-env).
5. gh api with -X POST/PUT/DELETE defaults to DESTRUCTIVE instead of EXTERNAL.
6. python dev.py is classified as VERIFICATION instead of WORKSPACE_WRITE, and external scripts (python /tmp/x.py) are classified as WORKSPACE_WRITE instead of DESTRUCTIVE.
7. Wrapper stripping drops `sudo`, causing `sudo cat /etc/shadow` to be classified as read-only.
8. Unbound session early exit in predicates.py occurs before UNKNOWN and DESTRUCTIVE checks.
9. bootstrap.py has an unsafe fallback taking sys.argv[1] as code when -c is missing from orig_argv.
10. `is_doc_only_path` (verify.py) and `is_doc_edit` (predicates.py) diverge and doc-manual-lock matching is overly broad.

## Requirements

- REQ-1: Restore EXTERNAL commands to allow execution after plan approval; add `--confirm-destructive` and `--confirm-external` to `along plan approve`.
- REQ-2: Roll back `_bare_slug` and `_slugs_equal` in `session.py`, enforcing exact canonical key matches.
- REQ-3: Replace regex-based deletion matching with path-normalized check against repo root for `rm`, `del`, `erase`, `rmdir`, `remove-item`.
- REQ-4: Expand dangerous git -c keys and add --config-env handling in `_classify_git`.
- REQ-5: Classify `gh api` mutation methods and flags as EXTERNAL.
- REQ-6: Classify `dev.py` as WORKSPACE_WRITE and scripts outside repo as DESTRUCTIVE; do not strip `sudo` and classify `sudo` as DESTRUCTIVE.
- REQ-7: Enforce UNKNOWN and DESTRUCTIVE checks before unbound session early exit.
- REQ-8: Remove unsafe fallback in `bootstrap.py`.
- REQ-9: Unify `is_doc_only_path` and `is_doc_edit` into a single canonical implementation and tighten `doc-manual-lock` path matching.

## Acceptance Criteria

- [x] EXTERNAL commands succeed after plan approval; DESTRUCTIVE commands succeed with `--confirm-destructive`
- [x] `_bare_slug` and `_slugs_equal` removed; `feat--x` never matches `bug--x`
- [x] `rm -rf ~/`, `rm -rf /etc`, `rm -rf ../other-repo`, `Remove-Item -Recurse C:\Users` classified as DESTRUCTIVE
- [x] Dangerous git -c keys and --config-env classified as DESTRUCTIVE
- [x] `gh api -X POST` classified as EXTERNAL
- [x] `sudo` classified as DESTRUCTIVE
- [x] Unbound sessions blocked from executing UNKNOWN and DESTRUCTIVE commands
- [x] Unsafe fallback removed from `bootstrap.py`
- [x] `is_doc_only_path` and `is_doc_edit` unified without divergence
- [x] Full test suite passes 100% with clean ASCII typography
