---
protocol: along
protocol_version: "4.4.2"
slug: cli-safety-heredoc-gaps
type: bug
status: done
completed: 2026-10-01
priority: high
created: 2026-10-01
updated: 2026-10-01
agent: claude-code
tags: [gates, cli-safety]
milestone: v4.5.0-multi-user-merge-automation
blocked_by: []
related: [bug--claude-hook-manifest-flat-schema]
---

# cli_safety runs in shadow mode and misses quoted heredocs and PowerShell here-strings

## Problem
- `DEFAULT_GATE_MODES` in `alongkit/hooks/config.py` sets `cli_safety` to `shadow`, so even with
  working hooks a heredoc only prints a warning. AGENTS.md states the rule as mandatory.
- The heredoc pattern matches only `<<EOF` / `<<'EOF'`; `<<'PY'`, `<< "END"`, `<<-TXT` pass.
- PowerShell here-strings (`@'...'@`, `@"..."@`) piped or redirected into files, and
  `Set-Content` / `Out-File` with inline content, are not detected.

## Requirements
- REQ-1: `cli_safety` enforces by default (overridable via `.along/config.json` or `ALONG_HOOK_MODE`).
- REQ-2: Any heredoc delimiter (`<<[-~]?\s*['"]?\w+`) is flagged; `<<<` here-strings of bash are not.
- REQ-3: PowerShell here-strings and inline `Set-Content`/`Out-File`/`Add-Content` writers are flagged.
- REQ-4: Git commit messages passed via heredoc stay allowed only through `along commit`.

## Acceptance Criteria
- [ ] Test matrix covers the delimiter variants and PowerShell writers
- [ ] Automated tests passing
