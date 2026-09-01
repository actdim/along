---
protocol: along
protocol_version: 2.2.8
slug: team-skill-state-not-persisted
type: debt
status: open
priority: critical
created: 2026-09-01
updated: 2026-09-01
agent: claude-code
tags: [along-team, multi-agent, backtracking, blackboard, state-machine, resumability]
milestone: v3.0.0-global-quality-revision
blocked_by: []
related: [team-skill-uses-provider-specific-subagent-api, always-on-context-budget-exceeds-claims]
parent: protocol-quality-audit-remediation
---

# Multi-agent state machine keeps its state only in context, so backtracking is not real

## Problem

`skills/along-team/SKILL.md` specifies a sequential state machine with a Living Plan, a
requirement traceability matrix (`REQ-N`), reviewer verdicts, and a retry budget
("maximum 2 retries before escalating to human", `SKILL.md:153`).

None of it is written to disk. The skill never instructs the agent to persist:

- the Living Plan and its per-step acceptance criteria;
- the `REQ-N` matrix produced in Phase 0;
- which step is current;
- reviewer PASS/FAIL verdicts and the reasons;
- the retry counter per step;
- the research findings from Phase 1.

The mechanism to store exactly this already exists and is unused by the skill:

```python
# scripts/along_exec.py:654-680
def handle_scratch_command(repo_root, args):     # scratch init|purge <slug>
    scratch_dir = os.path.join(repo_root, ".along", ".session", slug)
    plan_file = os.path.join(scratch_dir, "plan.md")
```

`AGENTS.md` also documents this blackboard ("Session-scoped ephemeral blackboard
`.along/.session/<slug>/` in `along-team`, automatically purged on wrap-up"), so the
protocol describes a facility the skill does not use.

## Impact

This is the gap that matters most for the stated purpose of the repository (backtracking,
multi-step development, agent optimization):

1. **No resumability.** After `/compact`, a context window overflow, a crash, a switch to
   another provider, or simply the next day, the state machine restarts from nothing. The
   agent re-derives the plan and re-does work.
2. **Retry limits are unenforceable.** "Max 2 retries" cannot be enforced without a
   counter that survives a phase boundary. In practice the limit depends on the model
   remembering how many times it already failed.
3. **Backtracking is nominal.** The FAIL branches ("Implementation flaw -> retry",
   "Architecture flaw -> update Living Plan", "Missing knowledge -> Researcher") have no
   stored decision history, so the same wrong branch can be re-taken repeatedly with no
   record.
4. **No auditability.** The session log is written only at the end, from memory, so what
   actually happened during the loop is unverifiable.
5. **Token cost.** Re-deriving plan and findings on every resumption is precisely the waste
   the token-efficiency claims target.

## Requirements

- REQ-1: Mandate `scratch init <slug>` at the start of Phase 0, and specify the blackboard
  file set:
  - `plan.md` - Living Plan with per-step `REQ-N` mapping, target files, acceptance criteria;
  - `state.json` - current step index, per-step status, retry counters, timestamps;
  - `research.md` - Phase 1 findings;
  - `reviews/step-<N>.md` - reviewer verdict with the rubric result per gate.
- REQ-2: Define the update contract: after every phase transition the agent MUST write the
  new state before proceeding, so an interruption at any point leaves a resumable record.
- REQ-3: Define resume semantics: on `/along-team <slug>` with an existing blackboard,
  read state and continue at the recorded step instead of re-planning. Add an explicit
  `--restart` to discard.
- REQ-4: Enforce the retry budget from `state.json`, and specify the escalation message
  produced when it is exhausted.
- REQ-5: Specify purge semantics on successful wrap-up, and retention on failure (a failed
  run's blackboard must survive for diagnosis, and be referenced from the session log).
- REQ-6: Provide deterministic CLI support for the blackboard beyond `init` / `purge`:
  reading and updating `state.json` should not require the agent to hand-edit JSON.
- REQ-7: Record an ADR for the durable-state design, including why state lives in
  `.along/.session/` (ephemeral, gitignored) rather than in the issue file.
- REQ-8: Tests: blackboard round-trip through the CLI; resume picks the recorded step;
  retry budget exhaustion is detected from state, not from context.

## Acceptance Criteria

- [ ] `along-team` writes and reads a durable blackboard for plan, state, and verdicts.
- [ ] An interrupted run resumes at the correct step with retry counters intact.
- [ ] Failed runs leave a diagnosable blackboard referenced from the session log.
- [ ] CLI support for state updates exists and is covered by tests.
- [ ] ADR recorded.
