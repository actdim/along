---
protocol: along
protocol_version: "4.4.16"
slug: cross-runtime-handoff-entities
type: feat
status: open
priority: high
created: 2026-10-17
updated: 2026-10-17
agent: claude-code
tags: [multi-runtime, handoff, blackboard, entities, mvp]
milestone: v5.0.0-agent-run-protocol-and-observability
parent: feat--autonomous-multi-runtime-mvp
blocked_by: []
related: [feat--cross-runtime-supervisor-orchestrator, feat--agent-interactive-stdin-bridge, debt--entity-model-slimming, feat--clean-turn-context-isolation-in-along-team]
---

# Cross-runtime handoff: run records, review verdicts, questions, claims and along brief

## Goal

Runtimes from different vendors share no memory. Files in the repository are the only bus. Define
the minimal set of files each role reads and writes, so that any runtime can pick up a step from
any other runtime with a deterministic, compact context.

## What already exists and stays

- Issue `.along/ISSUES/<type>--<slug>.md`: the task, `REQ-N`, acceptance criteria, status.
- ADRs and `.along/CONSTRAINTS.md`: durable decisions every role must respect.
- Session blackboard `.along/.session/<slug>/`: `research.md`, `plan.md`, `reviews/`, `state.json`.

## What is missing

1. **Run record** `.along/.session/<slug>/runs/<run-id>.json`: role, runtime, model, start, end,
   exit code, outcome (`done` | `fail` | `needs-input` | `timeout`), changed files (from git),
   usage or cost when the runtime reports it, pointer to the handoff note. Single source for the
   Telegram status card and for observability.
2. **Machine-readable review verdict**: `reviews/step-N.md` front matter `verdict: pass|fail` and
   `defects: [...]`. The orchestrator branches on it without parsing prose.
3. **Questions** `.along/.session/<slug>/questions/<id>.md`: front matter `status: open|answered`,
   `options`, `recommended`, `answer`, `answered_by`. A run that needs input writes a question and
   exits with outcome `needs-input`; the operator answers in Telegram; the next run reads it.
   Replaces the stdin bridge (`feat--agent-interactive-stdin-bridge`).
4. **Claim** in `state.json`: `claimed_by: {run_id, runtime, expires_at}`. Prevents two runs from
   working on one issue; the orchestrator renews or releases it; an expired claim is reclaimable.
5. **Handoff note** `handoff.md`, written by every role at the end of its run, at most about 20
   lines: what was done, what is left, traps. Overwritten per run; history lives in run records.
6. **`along brief <slug> --role <role>`**: generates the prompt payload for the next run
   deterministically: issue goal, `REQ-N`, acceptance criteria, current plan step, relevant ADR
   constraints, open review defects, answered questions, last handoff note, `git diff --stat`.

## Review criteria: root `REVIEW.md` (input, not output)

Claude Code Review auto-discovers a root `REVIEW.md` with review-only rules: what to flag, at which
severity, what to skip (https://code.claude.com/docs/en/code-review). It is plain Markdown, so it
works as the repository review policy for every reviewer runtime, not only Claude:
- `along brief <slug> --role reviewer` includes `REVIEW.md` when present (and AGENTS.md rules).
- Defect severities in the verdict front matter follow the same scale the file defines (default:
  blocking, important, nit); `verdict: fail` only on blocking or important defects.
- `REVIEW.md` is the policy (repository-wide, human-maintained); `reviews/step-N.md` is the result
  (per step, written by the reviewer role). Along does not generate `REVIEW.md`; an optional
  scaffold in `along init` can come later.

## What is NOT passed between runtimes

Chat transcripts, session logs (`SESSIONS/`), `HISTORY.md`, telemetry. Context is shared by
generating a brief from the files above, not by forwarding sessions.

## Role contract (MVP)

| Role | Reads (via brief) | Writes |
| --- | --- | --- |
| architect | issue, ADRs, research | `plan.md`, `REQ-N` in the issue, plan approval in `state.json` |
| implementer | brief for step N | code, `handoff.md`, run record |
| reviewer | brief, diff, test result | `reviews/step-N.md` with verdict, run record |
| orchestrator | `state.json`, run records, verdicts, questions | step transitions, claims, retries |

## Acceptance Criteria
- [ ] Schemas for run record, review verdict, question and claim documented in `docs/topic--domain-model.md` and validated.
- [ ] `along brief <slug> --role <role>` implemented, deterministic, and size-bounded.
- [ ] A run exiting with `needs-input` leaves an open question file; answering it lets the next run proceed.
- [ ] A second run cannot claim an issue with a live claim; an expired claim can be taken over.
- [ ] Automated tests passing.
