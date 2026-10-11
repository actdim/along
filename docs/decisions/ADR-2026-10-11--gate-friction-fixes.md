---
protocol: along
slug: gate-friction-fixes
type: decision
title: "Gate friction fixes of 2026-10-11"
date: 2026-10-11
status: accepted
tags: [adr, architecture, decision, gates, entities, tests, budget]
---

# ADR-2026-10-11--gate-friction-fixes - Gate friction fixes of 2026-10-11

- Date: 2026-10-11
- Status: accepted
- Context: A field report from a workspace with a nested subproject ([task--field-report-fixes]) and one session of observed friction showed gates that contradicted each other or blocked without cause: entity-reference-integrity rejected the cross-context `parent` that subproject-boundary demands; the commit test gate could not pass a project without tests and misread colour output; the Stop gate demanded a write that plan mode forbade; read-only compounds were denied. Meanwhile agent-usable bypass flags (`--no-verify`, `--force-reason`, `start --approved`, `plan approve`) were mostly unrecorded, so bypassing became routine instead of a human decision. Four decisions, one per area.
- Decision:
  1. Cross-context references [bug--cross-context-parent-dangling]: reference fields resolve locally, then in every enclosing `.along/` context up to the outermost one below home (`repo.context_chain`), crossing `.git` and submodule boundaries; ISSUES/ and ISSUES/done/ count. Commit snapshot checks add the working-tree keys of contexts above the git top. A `parent` equal to the issue's own key resolves only in enclosing contexts, else it is an "invalid self-parent reference". `root:<key>` resolves only in the outermost context. subproject-boundary decides from the target path and the binding, never the shell cwd, and walks the parent chain at any depth.
  2. Gate tiers and bypass [feat--gate-friction-and-bypass-accountability], [bug--plan-approval-self-and-lost]: reads never block (read-only subcommands listed, compounds judged per segment); mechanical fixups run in the hook (a stale ISSUES.md is recompiled at Stop). Invariant gates (workspace_containment, no_tracked_secrets, projection_protection, rule_pack_protection, circuit_breaker) always enforce and ignore shadow/disable overrides and bypass flags; advisory gates always shadow; the rest are process gates. A UserPromptSubmit hook records the user's last message time: CLI plan approvals are refused when the plan changed after it, and bypass flags need `--reason` plus a failure of that gate followed by a user reply. Without recorded messages both pass, marked unverified. Every bypass goes to the session trace, `hooks_audit.jsonl` (`decision: bypass`) and an `Along-Bypass:` commit trailer; `along gates stats` and doctor report bypass ratios.
  3. Declared test policy [bug--test-gate-no-tests-policy]: `.along/config.json` `verify.tests` is `required` (default) or `none`. required: tests must run, zero executed tests fail, a hook that cannot start is "misconfigured". none: needs `reason` and an existing `tracked_by` issue and runs the declared checks (build, lint, typecheck hooks); doctor, status and the dashboard show it. Counting strips ANSI codes; the generator drops `--silent`; docs/state-only commits skip tests with a note.
  4. AGENTS.md budget [debt--agents-md-budget-project-specifics]: `agents_md_bytes` (14336) measures AGENTS.md without its Project specifics section; `project_specifics_bytes` (4096) only warns and suggests moving details to `docs/topic--*.md`; both are configurable in `.along/config.json` `budget`.
- Consequences: Multi-subproject umbrellas work across submodules and a dangling key is still reported. A bypass costs one human reply instead of being free; scripted runs pass `--reason`; runtimes without a prompt hook keep working, unverified. Repo configs can no longer silence invariant gates. Projects without tests stay honest: missing tests remain visible debt. The hard AGENTS.md check guards what Along owns. Gate quality becomes measurable from the audit log.
