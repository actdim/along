---
protocol: along
protocol_version: "4.5.4"
slug: session-commit-binding
type: feat
status: open
priority: medium
created: 2026-10-30
updated: 2026-10-30
agent: antigravity
tags: [session, wrap, git, verification, gates]
milestone: v5.1.0-language-ecosystem-expansion
blocked_by: []
related: []
---

# Bind session reports and verification gates to exact git commit and tree state

Anchor session logs, wrap artifacts, and test completion receipts to exact git commit SHAs and tree dirty states for deterministic auditability.

## Context and Problem Statement
Currently, `along wrap` records completed session activities in `.along/SESSIONS/`, and the `test_before_stop` gate verifies that automated tests were executed after the last file write timestamp. However, this verification relies on filesystem modification timestamps rather than immutable git state.

If files are modified externally, git branches are rebased, or commits are amended, there is no cryptographic proof connecting the green test run to the exact tree state that was committed. Anchoring session summaries and test receipts to `git rev-parse HEAD` and tree diff hashes guarantees reproducible auditing across autonomous agent runs.

## Requirements
- REQ-1: `along wrap` and `along session create` MUST capture and store the current `commit_sha` (or `null` if uncommitted) and `tree_state` (`clean` | `dirty`) with a deterministic diff hash in the session frontmatter.
- REQ-2: Gate `test_before_stop` MUST record the git tree hash at the moment of successful test completion and reject session completion if working tree modifications occur without re-running tests.
- REQ-3: Handoff receipts in multi-agent executions MUST reference the exact tree state under which handoff artifacts were validated.
- REQ-4: Backward compatibility MUST be preserved for older session files lacking tree hash fields.

## Acceptance Criteria
- [ ] Session frontmatter schema supports `commit_sha`, `tree_state`, and `tree_diff_hash`
- [ ] `along wrap` automatically inspects git status and stamps tree verification metadata
- [ ] `test_before_stop` gate compares current git tree status against test verification receipts
- [ ] Unit tests in `tests/test_alongkit.py` verify clean vs dirty tree detection and gate enforcement
