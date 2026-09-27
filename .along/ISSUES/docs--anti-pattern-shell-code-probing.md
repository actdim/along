---
protocol: along
protocol_version: "4.1.0"
slug: anti-pattern-shell-code-probing
type: docs
status: open
priority: low
created: 2026-09-27
updated: 2026-09-27
agent: antigravity
tags: [protocol, agents-md, anti-pattern, documentation, rules]
milestone: v4.3.0-developer-experience-and-runtime-resilience
blocked_by: []
blocks: []
related: [feat--dev-environment-setup-and-editable-install]
---

# Documentation Rule: Anti-Pattern Shell Code Probing

## Problem

Agents encountering test regressions or missing symbols occasionally attempt exploratory inline shell execution (e.g. `python -c "import ...; print(dir(...))"`). In Along repositories, internal engine packages are not installed globally, and ad-hoc shell probing produces confusing error traces instead of actionable information.

## Requirements

1. **Protocol Rule in AGENTS.md**: Document an explicit prohibition in `AGENTS.md` and `skills/along-team/SKILL.md`:
   - Agents must never use `python -c` or inline shell commands to probe internal module symbols or inspect functions.
   - Agents must use static file tools (`view_file`, `grep_search`), AST tools (`code-review-graph`), or official CLI subcommands (`along <command> --help`).
2. **Knowledge Base Documentation**: Add guidance in `docs/topic--troubleshooting.md` or `docs/topic--contributing.md` explaining the internal packaging structure of Along.
