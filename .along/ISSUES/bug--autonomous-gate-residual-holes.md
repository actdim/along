---
protocol: along
protocol_version: "4.5.3"
slug: autonomous-gate-residual-holes
type: bug
status: open
priority: high
created: 2026-10-23
updated: 2026-10-23
agent: claude-code
tags: [gates, security, autonomous, escalation]
blocked_by: []
related: [feat--autonomous-gate-profile, bug--plan-approval-self-approval-bypass, feat--pre-approved-plans]
---

# Autonomous gate profile residual holes: self-enabled profile, escalation override

## Problem

Leftovers from the review of commit a8ea884 (`feat--autonomous-gate-profile`) that
`bug--plan-approval-self-approval-bypass` scoped out.

- The autonomous profile can be switched on by the agent: `ALONG_PROFILE` / `ALONG_AUTONOMOUS`
  env, the payload `profile` key (`hooks/containment.py`), `state.json` / binding `profile`.
- Approval records are protected from file tools only; a shell write
  (`echo ... > .along/.session/<slug>/state.json`) is not classified.
- In `hooks/engine.py` an escalation handler's `allow` makes the loop `continue` past the gate
  that denied, including workspace-containment and credential-store denials.
- The Telegram escalation is not wired: `set_escalation_handler` is never called from the hook
  entry path, so every escalation-list operation is always denied as unhandled (safe, but the
  feature does nothing); its tests only use injected mocks.
- Escalation runs on PostToolUse too, recording an escalation for a command that already ran.
- Release detection misses `python scripts/along_exec.py version-bump`, `gh release create`,
  `git push --tags` and `+main` refspecs, while `git tag -l` is escalated.
- `CrossRuntimeOrchestrator.run_architect_phase` approves the architect's own plan
  (`approved_by: architect`) with no policy check.

## Requirements
- REQ-1: The autonomous profile MUST be enabled only by a source the agent cannot write (daemon / orchestrator process environment set by the operator, or user-level config outside the workspace); payload and blackboard values MUST NOT enable it.
- REQ-2: Shell commands that write to approval records MUST be denied (or detected at Stop and the approval revoked).
- REQ-3: An escalation approval MUST NOT override a deny from any other gate.
- REQ-4: Escalation MUST run only on PreToolUse.
- REQ-5: Escalation MUST be wired to a real handler when the operator configures one, with a bounded timeout and deny on timeout or transport failure.
- REQ-6: Release detection MUST cover the script form of version-bump, `gh release create`, tag pushes and forced default-branch refspecs, and MUST NOT escalate read-only tag listing.
- REQ-7: Architect self-approval MUST be allowed only when the operator opts in (config flag); otherwise the orchestrator halts with needs-input unless an approved issue plan exists.

## Acceptance Criteria
- [ ] Setting `profile: autonomous` in `state.json` or the hook payload does not change the active profile.
- [ ] `echo {} > .along/.session/<slug>/state.json` through the shell gate is denied.
- [ ] A containment deny stays a deny when an escalation handler returns allow.
- [ ] Without the opt-in flag, an orchestrated issue without an approved plan stops after the architect with needs-input.
- [ ] Regression tests cover each criterion and fail on the old code; `python .along/scripts/test.py` is green.
