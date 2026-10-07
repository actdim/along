---
protocol: along
protocol_version: "4.4.6"
slug: protocol-friction-cleanup
type: debt
status: open
priority: low
created: 2026-10-07
updated: 2026-10-07
agent: claude
tags: [protocol, kb-search, tests]
milestone: v4.5.0-multi-user-merge-automation
blocked_by: []
related: [feat--plan-approval-exit-plan-mode, feat--kb-search-archive-scope-default]
---

# Protocol friction cleanup: plan approval wording, literal kb-search, quiet test noise

Small frictions observed on 2026-10-06/07.

## Requirements

- REQ-1: Plan approval wording. The protocol block and gate messages say "Claude Code:
  ExitPlanMode". Outside plan mode the tool fails ("You are not in plan mode"). State the
  fallback: outside plan mode, write the plan to a file and run
  `along plan approve --plan-file <path>` after the user's explicit yes.
- REQ-2: Literal kb-search. `fast-retrieval` blocks grep over `.along/` and `docs/`, but
  `along kb-search` has no exact / literal mode: a slug search (`monorepo-update-gate-friction`)
  returned 0 matches while the slug appeared in blackboard and session data. Add
  `--literal` (substring, all scopes incl. session logs and archived issues).
- REQ-3: Quiet test noise. `python .along/scripts/test.py -q` prints fixture migration output
  ("Backup written to ...", "All Along v4.4.6 migrations ... completed") and an extra
  `Ran 0 tests in 0.000s` line; quiet mode prints only the summary and failures.

## Acceptance Criteria
- [ ] Protocol block and gate messages carry the fallback
- [ ] `along kb-search --literal` finds slugs in all scopes
- [ ] Quiet run output limited to dots, summary and failures
- [ ] Automated tests passing
