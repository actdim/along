---
protocol: along
protocol_version: "4.4.11"
slug: destructive-authorization-and-lock-hardening
type: bug
status: done
completed: 2026-10-12
priority: critical
created: 2026-10-12
updated: 2026-10-12
agent: antigravity
tags: [security, gates, toolnature, predicates, doc-manual-lock, destructive]
blocked_by: []
related: [bug--post-audit-regressions-and-alignment]
affects: [scripts/alongkit/hooks/predicates.py, scripts/alongkit/hooks/toolnature.py, scripts/alongkit/hooks/shellparse.py, scripts/alongkit/verify.py, scripts/alongkit/session.py]
---

# Harden Destructive Authorization, Doc Manual Lock, Git Security, and Shell Parsing

## Problem

Audit review of commit 6b21678 identified several security gaps and regressions:
1. `doc-manual-lock`: `check_doc_manual_lock` in `predicates.py` allowed bypass when `is_targeted` without checking plan approval, allowed file-based issue bypass in keyed sessions (instead of restricting to unkeyed runtimes), and read `target_doc` from document `fm` instead of ticket `i_fm`.
2. `_DOC_SUFFIXES`: `.txt` was included in `_DOC_SUFFIXES` in `verify.py`, causing `requirements.txt`, `constraints.txt`, etc. to be misclassified as docs-only.
3. In-repository destructive targets: `_classify_deletion` treated all in-workspace targets as `WORKSPACE_WRITE`, allowing `rm -rf .git` and `rm -rf .along` as ordinary writes. Additionally, cmd flags like `/q` in `del /q` were misparsed as root paths, and `dist/*` was misclassified as root wildcard.
4. Destructive confirmation persistence: destructive authorization remained valid for the entire session and could be self-granted; it needs to be single-use / consumed upon execution and refused when unverified.
5. Environment variable stripping: `_strip_wrappers` in `shellparse.py` stripped environment variable assignments (`GIT_SSH_COMMAND`, `GIT_CONFIG_*`, etc.) before classification, allowing dangerous config injection to bypass `git -c` checks.
6. `git -c` allowlist: `git -c` was implemented as a denylist rather than an allowlist of known benign flags.
7. `gh api -X DELETE`: classified as `EXTERNAL` instead of `DESTRUCTIVE`.
8. `Out-File`: PowerShell `Out-File` flag arguments (e.g. `-Encoding utf8`) leaked into `subcommand`, causing false positive unclassified holds, and lacked classification.

## Requirements

- REQ-1: Require approved plan in `check_doc_manual_lock` for keyed sessions; restrict file-based ticket check to unkeyed runtimes (`not key`); read `target_doc` from `i_fm`.
- REQ-2: Remove `.txt` from `_DOC_SUFFIXES` in `verify.py`, keeping only `llms*.txt` through `_DOC_FILES`.
- REQ-3: Classify `.git/**` and `.along/**` as DESTRUCTIVE in `_classify_deletion`. Parse Windows flags (`/q`, `/f`, `/s`, etc.) correctly so they are not treated as root paths, and distinguish repo subfolder wildcards (`dist/*`) from root wildcards.
- REQ-4: Make destructive confirmation single-use (consumed upon execution) and refuse unverified self-approval.
- REQ-5: Do not strip dangerous environment variables (`GIT_*`, `LD_PRELOAD`, `PAGER`, `EDITOR`, etc.) or elevate command nature to DESTRUCTIVE when they carry dangerous overrides.
- REQ-6: Transition `git -c` to an allowlist of known safe keys (user info, formatting, color, advice), classifying all other `git -c` configurations as DESTRUCTIVE.
- REQ-7: Classify `gh api -X DELETE` and `--method DELETE` as DESTRUCTIVE.
- REQ-8: Add `Out-File` to built-in tools and prevent flag arguments (`-Encoding utf8`) from leaking into subcommand tokens.

## Acceptance Criteria

- [x] `check_doc_manual_lock` requires approved plan for keyed sessions, reads `target_doc` from `i_fm`, and only allows file-based issue check for unkeyed runtimes
- [x] `.txt` removed from `_DOC_SUFFIXES` in `verify.py`; `requirements.txt` is not doc-only
- [x] `rm -rf .git` and `rm -rf .along` classified as DESTRUCTIVE; `del /q file.txt` and `rm -rf dist/*` not falsely marked DESTRUCTIVE
- [x] Destructive confirmation is single-use and consumed upon tool execution; unverified CLI cannot confirm destructive
- [x] Dangerous environment variable overrides (`GIT_SSH_COMMAND`, `GIT_CONFIG_*`, `LD_PRELOAD`) classified as DESTRUCTIVE
- [x] `git -c` enforces allowlist of known safe configuration keys
- [x] `gh api -X DELETE` classified as DESTRUCTIVE
- [x] `Out-File` parsed and classified cleanly without `utf8` subcommand pollution
- [x] Full test suite passes 100% with clean ASCII typography
