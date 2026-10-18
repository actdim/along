---
protocol: along
protocol_version: "4.4.16"
date: 2026-10-18
slug: agents-md-core-slimming
agent: claude-code
branch: main
commit: 535896a
summary: Slim AGENTS.md managed block to a 4.9 KB core (state locations, issue anchoring, gate list, judgment rules); full procedure moved to managed on-demand docs/topic--along-protocol.md rendered by along init/update; marker-based profile sections; update honours active profile
milestone: v4.6.0-structured-state-and-blackboard-engine
issues_advanced: []
issues_completed: [debt--agents-md-core-slimming]
decisions: []
risks_logged: []
spikes_conducted: []
---

# Session: Agents md core slimming

## Summary
Slim AGENTS.md managed block to a 4.9 KB core (state locations, issue anchoring, gate list, judgment rules); full procedure moved to managed on-demand docs/topic--along-protocol.md rendered by along init/update; marker-based profile sections; update honours active profile

## Decisions
- None (confirmed at wrap: no architectural decisions).

## Blackboard Record

Execution mode: direct; plan revision 1; approved: true.

### Attributed Files

| Path | Kind | Edits | Last edit | Sessions |
| --- | --- | --- | --- | --- |
| `.along/GLOSSARY.md` | state | 1 | 2026-10-18T01:27:06Z | claude--0e35f0d2-5afb-45a1-8219-c9d84f9259e2 |
| `.along/ISSUES/debt--agents-md-core-slimming.md` | state | 1 | 2026-10-18T01:36:13Z | claude--0e35f0d2-5afb-45a1-8219-c9d84f9259e2 |
| `docs/topic--cli-reference.md` | docs | 2 | 2026-10-18T01:26:47Z | claude--0e35f0d2-5afb-45a1-8219-c9d84f9259e2 |
| `docs/topic--runtime-hooks-and-gates.md` | docs | 2 | 2026-10-18T01:27:00Z | claude--0e35f0d2-5afb-45a1-8219-c9d84f9259e2 |
| `docs/topic--setup-and-workflow.md` | docs | 1 | 2026-10-18T01:26:47Z | claude--0e35f0d2-5afb-45a1-8219-c9d84f9259e2 |
| `install.ps1` | source | 1 | 2026-10-18T01:21:47Z | claude--0e35f0d2-5afb-45a1-8219-c9d84f9259e2 |
| `install.sh` | source | 1 | 2026-10-18T01:21:48Z | claude--0e35f0d2-5afb-45a1-8219-c9d84f9259e2 |
| `scripts/along_init.py` | source | 4 | 2026-10-18T01:20:57Z | claude--0e35f0d2-5afb-45a1-8219-c9d84f9259e2 |
| `scripts/along_update.py` | source | 4 | 2026-10-18T01:21:13Z | claude--0e35f0d2-5afb-45a1-8219-c9d84f9259e2 |
| `scripts/alongkit/budget.py` | source | 1 | 2026-10-18T01:22:09Z | claude--0e35f0d2-5afb-45a1-8219-c9d84f9259e2 |
| `scripts/alongkit/install.py` | source | 1 | 2026-10-18T01:21:20Z | claude--0e35f0d2-5afb-45a1-8219-c9d84f9259e2 |
| `scripts/alongkit/scaffold.py` | source | 5 | 2026-10-18T01:27:34Z | claude--0e35f0d2-5afb-45a1-8219-c9d84f9259e2 |
| `skills/along-init/SKILL.md` | source | 1 | 2026-10-18T01:26:39Z | claude--0e35f0d2-5afb-45a1-8219-c9d84f9259e2 |
| `skills/along-init/protocol-reference.md` | source | 2 | 2026-10-18T01:31:15Z | claude--0e35f0d2-5afb-45a1-8219-c9d84f9259e2 |
| `skills/along-init/protocol.md` | source | 2 | 2026-10-18T01:19:37Z | claude--0e35f0d2-5afb-45a1-8219-c9d84f9259e2 |
| `tests/test_context_budget.py` | source | 1 | 2026-10-18T01:22:09Z | claude--0e35f0d2-5afb-45a1-8219-c9d84f9259e2 |
| `tests/test_docs.py` | source | 1 | 2026-10-18T01:22:41Z | claude--0e35f0d2-5afb-45a1-8219-c9d84f9259e2 |
| `tests/test_installers.py` | source | 1 | 2026-10-18T01:21:28Z | claude--0e35f0d2-5afb-45a1-8219-c9d84f9259e2 |
| `tests/test_scaffold_profiles.py` | source | 1 | 2026-10-18T01:23:27Z | claude--0e35f0d2-5afb-45a1-8219-c9d84f9259e2 |
| `tests/test_skills_and_scripts.py` | source | 3 | 2026-10-18T01:22:29Z | claude--0e35f0d2-5afb-45a1-8219-c9d84f9259e2 |

### Plan

#### Living Plan: agents-md-core-slimming

Title: Slim AGENTS.md to a core of state locations and gates

Approved by the user via ExitPlanMode on 2026-10-18. Execution Mode: Direct.
Decision (user): moved procedure ships to consumer repos as the managed article `docs/topic--along-protocol.md`.

##### Steps
- [x] Step 1: Write `skills/along-init/protocol-reference.md` holding every relocated rule verbatim; profile sections for the light checklist, plan alignment and escalation.
- [x] Step 2: Rewrite `skills/along-init/protocol.md` to a core of at most 6 KB: state locations, issue anchoring, gate list, judgment rules, pointer.
- [x] Step 3: Replace the string-replacement profile adaptation in `alongkit.scaffold` with `render_profile_sections` (markers); add `render_protocol_reference`, `reference_action`, `reference_source_for`.
- [x] Step 4: `along init` and `along update` write the reference at FULL roots (foreign files left alone). Update renders for the active profile. Add the OpenCode helper copy in `install.py`, `install.sh` and `install.ps1`.
- [x] Step 5: Regenerate the `AGENTS.md` block and `docs/topic--along-protocol.md` through the engine; run `along kb-sync`.
- [x] Step 6: Tests: 6 KB ceilings and the 7 KB `agents_md_bytes` default; block/reference projection equality; the no-rule-lost and gate-tag coverage checks; profile rendering; update keeps Project specifics.
- [x] Step 7: Docs: runtime-hooks-and-gates (4a and 6.1), cli-reference, setup-and-workflow, along-init SKILL, glossary.

### Execution Trace

#### Execution Trace: agents-md-core-slimming
- 2026-10-18T01:18:05Z phase: planning -> execution
- 2026-10-18T01:18:05Z plan approved (ExitPlanMode) approved_via: exit-plan-mode
- 2026-10-18T01:19:11Z edit skills/along-init/protocol-reference.md
- 2026-10-18T01:19:37Z edit skills/along-init/protocol.md (x2)
- 2026-10-18T01:20:33Z edit scripts/alongkit/scaffold.py (x4)
- 2026-10-18T01:20:57Z edit scripts/along_init.py (x4)
- 2026-10-18T01:21:13Z edit scripts/along_update.py (x4)
- 2026-10-18T01:21:20Z edit scripts/alongkit/install.py
- 2026-10-18T01:21:28Z edit tests/test_installers.py
- 2026-10-18T01:21:47Z edit install.ps1
- 2026-10-18T01:21:48Z edit install.sh
- 2026-10-18T01:22:09Z edit scripts/alongkit/budget.py
- 2026-10-18T01:22:09Z edit tests/test_context_budget.py
- 2026-10-18T01:22:29Z edit tests/test_skills_and_scripts.py (x3)
- 2026-10-18T01:22:41Z edit tests/test_docs.py
- 2026-10-18T01:23:27Z edit tests/test_scaffold_profiles.py
- 2026-10-18T01:26:11Z test FAIL (along test)
- 2026-10-18T01:26:39Z edit skills/along-init/SKILL.md
- 2026-10-18T01:26:47Z edit docs/topic--cli-reference.md (x2)
- 2026-10-18T01:26:47Z edit docs/topic--setup-and-workflow.md
- 2026-10-18T01:27:00Z edit docs/topic--runtime-hooks-and-gates.md (x2)
- 2026-10-18T01:27:06Z edit .along/GLOSSARY.md
- 2026-10-18T01:27:34Z edit scripts/alongkit/scaffold.py
- 2026-10-18T01:31:15Z edit skills/along-init/protocol-reference.md
- 2026-10-18T01:36:13Z edit .along/ISSUES/debt--agents-md-core-slimming.md
