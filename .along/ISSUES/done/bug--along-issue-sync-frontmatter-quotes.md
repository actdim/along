---
protocol: along
protocol_version: "4.5.0"
slug: along-issue-sync-frontmatter-quotes
type: bug
status: done
completed: 2026-10-21
priority: high
created: 2026-10-21
updated: 2026-10-21
agent: antigravity
milestone: v4.5.1-entity-model-slimming-and-hotfixes
tags: []
blocked_by: []
related: []
---

# Fix unquoted YAML frontmatter in along-issue-sync skill

## Problem
In `skills/along-issue-sync/SKILL.md`, the `description` field in YAML frontmatter contains an unquoted string with `: ` (`protocol: along`).
Strict YAML parsers (such as Go yaml parser in Antigravity) fail to parse the frontmatter, reporting `mapping values are not allowed in this context`, which drops the skill from loaded skills.

## Acceptance Criteria
- [x] Wrap `description` string in double quotes in `skills/along-issue-sync/SKILL.md`.
- [x] YAML frontmatter parses without error via YAML parsers.
- [x] Update global skill copy in `~/.gemini/config/skills/along-issue-sync/SKILL.md`.
- [x] Automated tests passing (`python .along/scripts/test.py -q`).
