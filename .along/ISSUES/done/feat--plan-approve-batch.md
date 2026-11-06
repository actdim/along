---
protocol: along
protocol_version: "4.6.0"
slug: plan-approve-batch
type: feat
status: done
completed: 2026-11-06
priority: medium
created: 2026-11-05
updated: 2026-11-06
agent: antigravity
tags: [lifecycle, planning, cli]
blocked_by: []
related: []
plan_status: needs-approval
---

# Batch plan approval and draft plan status header

Provide batch plan approval via `along plan approve --from <dir>` and support marking plan files as draft (`status: draft`) to prevent premature approvals. Currently, approving decomposed plans across dozens of issues requires running `along plan approve <slug> --plan-file <path>` individually for each issue.

## Requirements
- REQ-1: Support `along plan approve --from <dir>` to scan a folder of plan files and register approvals in batch.
- REQ-2: Resolve target issue keys deterministically: frontmatter field `issue:` (or `slug:`) takes precedence, falling back to canonical filename prefix `NN--<type>--<slug>.md` or `<type>--<slug>.plan.md`.
- REQ-3: Support `status: draft` in plan frontmatter. `along plan approve` (both single and batch) MUST refuse to approve any plan marked as draft, printing an explicit refusal.
- REQ-4: Provide `--dry-run` listing each candidate plan file, target issue key, subproject context, and validation status (Ready, Refused: draft, Error: issue not found) without modifying filesystem state.
- REQ-5: Copy approved plan content into the canonical issue plan file `.along/ISSUES/<key>/plan.md` and record the approval event.
- REQ-6: Unit tests in `tests/test_plan_approve_batch.py` covering directory scanning, draft protection, dry run, and batch approval execution.

## Acceptance Criteria
- [x] Batch plan approval via `along plan approve --from <dir>` resolves target tickets.
- [x] Frontmatter `status: draft` is refused for both single and batch approvals.
- [x] `--dry-run` displays plan approval candidates without mutating filesystem state.
- [x] Approved plans are persisted to `.along/ISSUES/<key>/plan.md` and recorded in approval log.
