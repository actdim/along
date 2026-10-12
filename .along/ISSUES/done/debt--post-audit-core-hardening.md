---
protocol: along
protocol_version: "4.2.0"
slug: post-audit-core-hardening
type: debt
status: done
completed: 2026-10-12
priority: high
created: 2026-10-12
updated: 2026-10-12
agent: antigravity
tags: [audit, security, gates, toolnature, bootstrap, docs, hardening]
milestone: v4.5.0-multi-user-merge-automation
blocked_by: []
related: [debt--along-exec-argparse-migration, feat--tool-nature-classification, bug--uncommitted-issue-deleted-without-trace]
affects: [docs/topic--system-comparisons.md, README.md, .along/VISION.md]
---

# Post-Audit Protocol Hardening and Integrity Fixes

## Problem

A multi-agent audit of 16 recent commits identified critical issues and gaps:
1. Duplicate gate ID in `default_gates.yaml` (`entity_reference_integrity` defined twice, overwriting the PreToolUse deletion gate).
2. Broken `python -c` argument handling in `alongkit.bootstrap` (missing code string from `sys.argv`).
3. Security holes in `toolnature.py` (`env`, `git -c`, `*view` mask, `gh api --field`, `rm` classification, unconstrained repository downgrades).
4. `skills/**`, `AGENTS.md`, and `protocol.md` incorrectly treated as docs-only.
5. Unverified arXiv citations and inaccurate invariant counts in documentation.
6. Bypass of `doc-manual-lock` through unapproved stub issues.

## Requirements

- REQ-1: Fix duplicate gate ID in `default_gates.yaml` (rename deletion gate to `entity_deletion_protection`) and enforce gate ID uniqueness on load.
- REQ-2: Fix `ensure_deps` inline execution in `alongkit.bootstrap` using `sys.orig_argv`.
- REQ-3: Patch security holes in `toolnature.py` (unwrap `env`, detect dangerous `git -c` configs, fix wildcard matching, classify external `rm`, prevent repo downgrades, support destructive confirmation).
- REQ-4: Exclude `skills/**`, `AGENTS.md`, and `protocol.md` from `is_doc_only_path` and `is_doc_edit`.
- REQ-5: Clean up unverified citations in `docs/topic--system-comparisons.md`, correct invariant counts dynamically, and align VISION.md.
- REQ-6: Require active bound session with approved plan to edit manual-locked documentation.

## Acceptance Criteria

- [x] Duplicate gate IDs rejected at load time; entity deletion blocked via PreToolUse
- [x] `bootstrap.ensure_deps` correctly preserves inline code via `sys.orig_argv`
- [x] `env rm -rf ~`, `git -c core.fsmonitor=...`, `gh pr review --approve`, and `gh api --field` correctly classified
- [x] Changes to `skills/` and `AGENTS.md` trigger test requirements on wrap
- [x] Manual lock bypass blocked
- [x] All tests passing with 100% clean ASCII typography
