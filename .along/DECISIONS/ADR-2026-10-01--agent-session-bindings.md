---
protocol: along
slug: agent-session-bindings
type: decision
title: "Agent-Session Issue Bindings and Plan Approval"
date: 2026-10-01
status: accepted
tags: [adr, architecture, decision]
---

# ADR-2026-10-01--agent-session-bindings - Agent-Session Issue Bindings and Plan Approval

- Date: 2026-10-01
- Status: accepted
- Context: Several agent sessions work in one repository. The repository-level .along/.session/state.json made the last writer decide which issue and approval every session's gates saw, and a purged session left plan_approved: true behind for the next one. along start also approved the plan by itself.
- Decision: Each agent session is bound to one issue through .along/.session/bindings/<runtime>--<session_id>.json in the outermost .along/ of the workspace, with a context field for subproject issues. Gates resolve the issue from the event's own session id; with no binding they use the single in-progress blackboard not bound elsewhere, and refuse when ambiguous. Plan approval is per session: Claude Code ExitPlanMode or along plan approve after the user's yes; along start no longer approves. The repository-level state.json is read only for runtimes without a session id.
- Consequences: Parallel sessions get independent gate decisions. Runtimes must pass a session id (hook payload or CLAUDE_CODE_SESSION_ID / ALONG_SESSION_ID) for isolation. Scripted runs use along start --approved. Stale bindings need along session gc.
