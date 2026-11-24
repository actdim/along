---
protocol: along
protocol_version: "4.9.1"
slug: issue-bound-draft-plans
type: feat
status: open
priority: high
created: 2026-11-24
updated: 2026-11-24
agent: antigravity
tags: [cli, planning, subprojects, protocol]
blocked_by: []
related: []
---

# Issue-bound draft plans and nested subproject plan approval

## Problem
Agents write draft plans to scratch or temp directories and pass `--plan-file <scratch>` to `along plan approve` because `AGENTS.md` and CLI error messages steer toward `--plan-file` and there is no `along plan draft` command. Additionally, `along plan approve` and `along plan approve --from <dir>` only call `entities.find_issue_by_slug(repo_root, ...)` and fail on issues inside nested subprojects.

## Requirements
- REQ-1: `along plan draft <slug>` MUST scaffold or validate `.along/ISSUES/<key>/plan.md` and set `plan_status: needs-approval` (reusing `PLAN_STATUSES` without adding a duplicate `proposed` status).
- REQ-2: `along plan approve <slug>` MUST approve `.along/ISSUES/<key>/plan.md` in place without requiring `--plan-file`, and `[gate: require-plan-approval]` MUST allow writing `.along/ISSUES/<key>/plan.md` before approval.
- REQ-3: `along plan approve <slug>`, `along plan approve --from <dir>`, `along plan draft <slug>`, `along plan revise`, and `along plan rework` MUST resolve issues across nested subprojects via subproject discovery rather than failing when invoked from the root.
- REQ-4: `AGENTS.md` (managed block / `along-init`) and `along plan` CLI messages MUST instruct agents to write plans directly into `.along/ISSUES/<key>/plan.md` (`needs-approval`), show that path to the user, approve in place after their yes, and never keep plans in temp or scratch directories.

## Acceptance Criteria
- [ ] `along plan draft <slug>` sets `plan_status: needs-approval` and `along plan approve <slug>` approves `.along/ISSUES/<key>/plan.md` in place
- [ ] `along plan approve` and `along plan approve --from <dir>` resolve issues in nested subprojects
- [ ] `[gate: require-plan-approval]` permits writing `.along/ISSUES/<key>/plan.md` prior to approval while still blocking `plan_status: approved` forgery
- [ ] `AGENTS.md` and `along plan` CLI help/error messages document `.along/ISSUES/<key>/plan.md` as the single draft location
- [ ] Automated tests covering `along plan draft`, in-place approval, and nested subproject resolution pass
