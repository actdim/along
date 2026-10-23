---
protocol: along
slug: issue-plans-approved-ahead
type: decision
title: "Issue plans live with the ticket; only the CLI approves them"
date: 2026-10-23
status: accepted
tags: [adr, architecture, decision]
---

# ADR-2026-10-23--issue-plans-approved-ahead - Issue plans live with the ticket; only the CLI approves them

- Date: 2026-10-23
- Status: accepted
- Context: Users want to plan an issue in detail, approve the plan once, and start it later (by hand, by the agent, or by the orchestrator/runner daemon) with no second approval. The plan lived only in the git-ignored blackboard and was dropped at wrap, and approval belonged to one session. The earlier attempt (issue front-matter plan_approved: true, a8ea884) let an agent approve its own plan (bug--plan-approval-self-approval-bypass).
- Decision: An issue's plan is a committed artifact next to its ticket: .along/ISSUES/<key>/plan.md, one living file (approved baseline, then revisions with reasons) that moves with the ticket and that blackboards and along-team read and write via session.plan_path. The ticket's plan_status (needs-approval | approved | needs-rework) records where it stands; approved is set only by along plan approve after the user's yes, which also logs an event in the machine-local .along/.session/plan-approvals.jsonl. along start and the orchestrator run an approved plan without asking only when that event exists on this machine; otherwise they ask again. File-tool edits that set approved are denied, shell writes are reported at Stop, the log is closed to file tools. No hashes and no staleness tracking: agents correct the plan during work and record revisions; only a problem the ticket cannot absorb goes to the user (along plan rework).
- Consequences: Plans are kept in Git and reviewable after the work. An approval does not travel between machines: on another machine (e.g. the VPS daemon) the user confirms once in the current channel. A plan edited after approval stays approved (accepted: whoever can edit plans can edit tickets). The guard is bar-raising, not absolute: an agent with a shell can still forge the log; only isolation prevents that.
