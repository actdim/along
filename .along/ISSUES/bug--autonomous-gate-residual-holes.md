---
protocol: along
protocol_version: "4.5.3"
slug: autonomous-gate-residual-holes
type: bug
status: open
priority: high
created: 2026-10-23
updated: 2026-10-29
agent: claude-code
tags: [gates, security, autonomous, escalation]
blocked_by: []
related: [feat--autonomous-gate-profile, bug--plan-approval-self-approval-bypass, feat--pre-approved-plans, feat--agent-execution-gate-telegram]
plan_status: approved
---

# Autonomous gate profile residual holes: self-enabled profile, escalation override

## Problem

Leftovers from the review of commit a8ea884 (`feat--autonomous-gate-profile`) that
`bug--plan-approval-self-approval-bypass` scoped out.

- The autonomous profile can be switched on from places the agent writes: `.along/config.json` /
  `.along/config.yaml` (`profile` or `hooks.profile`), the session binding / `state.json` `profile`
  (`along start --profile autonomous` accepts it), and the hook payload `profile` key
  (`hooks/containment.py`). It grants loosenings: the plan gate skips its phase check
  (`hooks/predicates.py`, `check_mutation_authorization`), `session.is_plan_approved` guesses the
  slug for an unkeyed session, and escalation routing can override other gates.
- Approval records are protected from file tools only; a shell write
  (`echo ... > .along/.session/<slug>/state.json`) is not classified, and `.along/.session/` is
  git-ignored, so the Stop-time working-tree check does not see it either. This is live in the
  ordinary interactive mode: an agent can approve its own plan through the shell.
- In `hooks/engine.py` an escalation handler's `allow` makes the loop `continue` past the gate
  that denied, including workspace-containment and credential-store denials.
- Escalation runs on PostToolUse too, recording an escalation for a command that already ran.
- Release detection misses `python scripts/along_exec.py version-bump`, `gh release create`,
  `git push --tags` and `+main` refspecs, while `git tag -l` is escalated.
- `CrossRuntimeOrchestrator.run_architect_phase` approves the architect's own plan
  (`approved_by: architect`) with no policy check.

## Requirements
- REQ-1: The autonomous profile MUST be enabled only by the hook process environment (`ALONG_PROFILE=autonomous` / `ALONG_AUTONOMOUS=1`, set by the operator: systemd unit, `along env` compose, runner environment); repository config, session binding / `state.json` and the hook payload MUST NOT enable it, and `along start --profile autonomous` MUST be refused.
- REQ-2: Shell commands that write to approval records MUST be denied before they run when the command names a record; an approval that appears during a turn without an approval event from the CLI or the ExitPlanMode hook MUST be revoked at Stop and reported.
- REQ-3: An escalation approval MUST NOT override a deny from any other gate.
- REQ-4: Escalation MUST run only on PreToolUse.
- REQ-6: Release detection MUST cover the script form of version-bump, `gh release create`, tag pushes and forced default-branch refspecs, and MUST NOT escalate read-only tag listing.
- REQ-7: Architect self-approval MUST be allowed only when the operator opts in (process environment `ALONG_ARCHITECT_SELF_APPROVAL=1`); otherwise the orchestrator records the architect's plan as `plan_status: needs-approval` and halts with needs-input, unless an approved issue plan exists.

## Acceptance Criteria
- [ ] `profile: autonomous` in `.along/config.json`, the session binding, `state.json` or the hook payload does not make the active profile autonomous; `along start --profile autonomous` exits 2.
- [ ] `echo {} > .along/.session/<slug>/state.json` (and the `bindings/`, ledger and approval-log equivalents, in bash and PowerShell forms) is denied before it runs; `cat` / `Get-Content` of the same files is allowed.
- [ ] A plan approved during a turn by an indirect write (no `approve` ledger event) is revoked at Stop and the Stop is denied with a message.
- [ ] A containment deny stays a deny when an escalation handler returns allow.
- [ ] No escalation is evaluated or recorded on PostToolUse.
- [ ] Release detection covers the listed forms and does not flag `git tag -l` / `git tag --list`.
- [ ] Without `ALONG_ARCHITECT_SELF_APPROVAL=1`, an orchestrated issue without an approved plan stops after the architect with needs-input and `plan_status: needs-approval`.
- [ ] Regression tests cover each criterion and fail on the old code; `python .along/scripts/test.py` is green.

## Notes
- REQ-5 (wiring escalation to a real Telegram handler) moved to `feat--agent-execution-gate-telegram`:
  its MVP scope already holds Approve / Reject for the escalation list, and its 2026-10-29 design
  notes fix the transport (runs never poll Telegram; the hook waits on a local decision file that the
  daemon writes from the `callback_query`). Until then escalation stays fail-closed (deny as unhandled).
- Residual risk: an agent that deliberately forges several machine-local records at once through an
  interpreter script is beyond what in-process hooks can stop; the boundary for that is OS / container
  isolation (`bug--autonomous-container-build-and-firewall`).
