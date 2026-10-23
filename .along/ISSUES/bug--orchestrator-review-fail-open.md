---
protocol: along
protocol_version: "4.5.3"
slug: orchestrator-review-fail-open
type: bug
status: in-progress
priority: high
created: 2026-10-23
updated: 2026-10-23
agent: claude-code
tags: [orchestrator, handoff, autonomous, security, regression]
blocked_by: []
related: [feat--cross-runtime-supervisor-orchestrator, feat--cross-runtime-handoff-entities, feat--pre-approved-plans]
plan_status: approved
---

# Orchestrator and handoff pass steps on missing or broken reviews

## Problem

Review of commits 2d84ceb (`feat--cross-runtime-handoff-entities`) and 6a379f5
(`feat--cross-runtime-supervisor-orchestrator`). With `feat--pre-approved-plans` the orchestrator
runs a whole issue unattended, so a step that passes without a real review ships unreviewed work.

- `handoff.parse_review_verdict` defaults a missing `verdict` to `pass`; `load_review_verdict`
  never validates the result. In `CrossRuntimeOrchestrator.run_step_loop` a missing review file,
  an unparseable one, or a stdout fallback whose `write_review_verdict` raises (swallowed) leaves
  `verdict = "pass"` whenever the reviewer exits 0.
- An implementer run with `outcome: fail` is not handled: the loop goes straight to review.
- `--dry-run` changes real state: it claims the issue, approves the plan (`run_architect_phase`
  calls `approve_plan`), marks every step passed and the session `completed`, and runners write
  `done` run records.
- Claims (`acquire_claim`) are an unlocked read-modify-write of `state.json`: two runners can both
  see "expired" and both acquire. The claim TTL is never renewed during a multi-step run, and
  `orchestrate` releases with `force=True`, wiping a claim another process took over.
- `DEFAULT_TIMEOUT` is unused, so a runner without a configured timeout waits forever.
- `run_id`, `qid` and `slug` are joined into paths unchecked (`handoff.py` run records, questions,
  session dir): `run_id="../../x"` writes outside `.along/`. A non-dict defect crashes the brief
  (`_extract_open_defects`).

## Requirements
- REQ-1: The orchestrator MUST treat a step as failed when the review verdict is missing, unparseable, or fails `validate_review_verdict`, and feed a blocking defect that says why.
- REQ-2: `handoff.load_review_verdict` MUST report an invalid or missing verdict instead of defaulting to `pass`.
- REQ-3: An implementer run with outcome `fail` MUST count as a failed attempt of the step (retry counter, defect fed back) without running the reviewer.
- REQ-4: `orchestrate(dry_run=True)` MUST NOT change the blackboard, claims or run records; it MUST return a preview of the phases, roles, runtimes and brief sizes it would run.
- REQ-5: `handoff.acquire_claim` MUST be exclusive across processes (lock file created with `O_CREAT|O_EXCL`, stale locks recovered).
- REQ-6: The orchestrator MUST renew its claim before each runner invocation, abort with `blocked` when another run holds it, and release only its own claim.
- REQ-7: A runner without a configured timeout MUST use `DEFAULT_TIMEOUT`.
- REQ-8: `handoff` MUST reject `slug`, `run_id` and `qid` values that are not plain identifiers (`[A-Za-z0-9][A-Za-z0-9._-]*`, no `..`).
- REQ-9: Brief generation MUST skip malformed defect entries instead of raising.

## Acceptance Criteria
- [x] Reviewer exits 0 with no review file: the step fails with a blocking defect and is retried.
- [x] A review file without `verdict`, or with `verdict: fail` and no severe defect: the step fails.
- [x] Implementer outcome `fail`: no reviewer run, retry counter incremented, defect recorded.
- [x] Dry run: `state.json`, run records and claims are byte-identical before and after; result status `dry-run` lists the phases; CLI exits 0.
- [x] Two concurrent `acquire_claim` calls for different run ids: exactly one succeeds.
- [x] A claim taken over by another run is not released by the orchestrator's `finally`.
- [x] `create_run_record(run_id="../x")`, `create_question(qid="../x")` and a slug with `/` or `..` raise `ValueError`.
- [x] Regression tests cover each criterion and fail on the old code; `python .along/scripts/test.py` is green.

## Notes
- The architect self-approving its own plan in autonomous runs is a gate-policy question and
  lives in `bug--autonomous-gate-residual-holes`.
- Killing the runner's process tree on SIGTERM belongs to `bug--runtime-adapters-invented-cli-contracts`.
