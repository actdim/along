---
protocol: along
protocol_version: "4.4.6"
date: 2026-10-06
slug: subcommand-help-as-argument
agent: claude-code
branch: main
commit: dec9a6e
summary: Completed bug--subcommand-help-as-argument
milestone: v4.5.0-multi-user-merge-automation
issues_advanced: []
issues_completed: [bug--subcommand-help-as-argument]
decisions: []
risks_logged: []
spikes_conducted: []
---

# Session: Subcommand help as argument

## Summary
Completed bug--subcommand-help-as-argument

## Blackboard Record

Execution mode: direct; plan revision 1; approved: true.

### Attributed Files

| Path | Kind | Edits | Last edit | Sessions |
| --- | --- | --- | --- | --- |
| `.along/ISSUES/bug--subcommand-help-as-argument.md` | state | 1 | 2026-10-06T18:41:33Z | claude--316b8d3c-a95f-4b65-84b2-83dfe7b417da |
| `docs/topic--cli-reference.md` | docs | 1 | 2026-10-06T18:41:33Z | claude--316b8d3c-a95f-4b65-84b2-83dfe7b417da |
| `scripts/along_exec.py` | source | 12 | 2026-10-06T18:37:32Z | claude--316b8d3c-a95f-4b65-84b2-83dfe7b417da |
| `tests/test_subcommand_help.py` | source | 4 | 2026-10-06T18:33:32Z | claude--316b8d3c-a95f-4b65-84b2-83dfe7b417da |

### Plan

#### Living Plan: subcommand-help-as-argument

##### Revision 1 (2026-10-06T18:31:58Z, plan approve --plan-file)

#### Plan: bug--subcommand-help-as-argument

Execution Mode: Direct

##### Root cause
Routers in `scripts/along_exec.py` check `-h/--help` only in `args[0]`; anything after the
subcommand is parsed as a slug (ADR `----help`, blackboard `.along/.session/--help/`).

##### Steps
1. Central help interception in `main()`: native router map (issue, milestone, start, session,
   plan, decision, scratch, worktree, git, gates, rules, budget, patch, circuit, telemetry,
   status, doctor). If `-h`/`--help` appears in the args (before `--`), call the router with
   `["--help"]`, print the `Usage:` line plus the named subcommand's lines (full usage when none
   match). Exit 0, no writes. `run`, `kb`, `graph`, tool scripts and lifecycle hooks are not
   intercepted (passthrough).
2. Usage for `status` and `doctor`.
3. Reject entity names starting with `-` (exit 2): decision create, milestone create, session
   create, scratch <sub> <slug>, worktree create, start <slug>, issue rename.
4. Test `tests/test_subcommand_help.py` (hermetic): sweep every router x subcommand with
   `--help`/`-h` (also after a slug): exit 0, `Usage` in stdout, fixture tree hash unchanged;
   dash-names rejected without files; `run` not intercepted.
5. Wrap: along test, diff review, docs blast radius, close issue, wrap, sync, HISTORY.

### Execution Trace

#### Execution Trace: subcommand-help-as-argument
- 2026-10-06T18:29:52Z denied [require_plan_approval] run_command: Inquiry Read-Only Invariance [gate: require-plan-approval]: No approved plan for issue 'subcommand-help-as-argument' (phase: 'planning', plan_approved: false...
- 2026-10-06T18:31:58Z plan recorded: revision 1 (plan approve --plan-file)
- 2026-10-06T18:31:58Z plan approved (along plan approve)
- 2026-10-06T18:32:46Z edit scripts/along_exec.py (x10)
- 2026-10-06T18:33:32Z edit tests/test_subcommand_help.py (x4)
- 2026-10-06T18:37:09Z test FAIL (along test)
- 2026-10-06T18:37:32Z edit scripts/along_exec.py (x2)
- 2026-10-06T18:41:09Z test FAIL (along test)
- 2026-10-06T18:41:18Z denied [fast_retrieval] grep_search: Manual Search Rejected [gate: fast-retrieval]: Manual directory search across 'D:\Src\my\actdim\public\along\docs' is forbidden to prevent latency and LLM to...
- 2026-10-06T18:41:33Z edit docs/topic--cli-reference.md
- 2026-10-06T18:41:33Z edit .along/ISSUES/bug--subcommand-help-as-argument.md
- 2026-10-06T18:41:46Z denied [test_before_stop] : Turn Completion Rejected [gate: test-before-stop]: Source files were modified in this session, but automated tests have not been executed afterward. Run test...
- 2026-10-06T18:44:51Z test FAIL (along test)
- 2026-10-06T18:48:26Z test pass (along test)
- 2026-10-06T18:48:30Z archived by issue done

## Decisions
- None (confirmed at wrap: no architectural decisions).
