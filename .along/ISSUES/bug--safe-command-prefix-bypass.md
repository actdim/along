---
protocol: along
protocol_version: "4.2.0"
slug: safe-command-prefix-bypass
type: bug
status: open
priority: high
created: 2026-09-27
updated: 2026-09-27
agent: cowork
tags: [hooks, gates, cli-safety, security]
milestone: v4.3.0-developer-experience-and-runtime-resilience
blocked_by: []
related: [bug--claude-adapter-unmapped-tools, docs--anti-pattern-shell-code-probing]
---

# Safe-command allowlist lets compound and redirected commands bypass gates

## Problem

`SAFE_READ_COMMAND_PATTERNS` in `scripts/alongkit/hooks/predicates.py` classifies a whole shell command as read-only by matching its prefix (`^\s*(echo|printf|cat|ls|...)`) or a substring anywhere (`\bpytest\b`, `\bnpm\s+test\b`, `\bunittest\s+discover\b`). Compound commands, redirections and chained destructive commands are therefore treated as safe, and the declared `cli_safety` protection is not reached for them.

## Evidence

Claude adapter, PreToolUse, repo without an in-progress issue:

```text
rm -rf src            -> DENY
ls && rm -rf src      -> ALLOW
rm -rf src; pytest    -> ALLOW
echo hi > src/a.py    -> ALLOW
```

## Requirements

- REQ-1: Tokenize the command (`shlex` on POSIX, a PowerShell-aware splitter on Windows) and split on `;`, `&&`, `||`, `|`, newlines and subshells `$(...)` / backticks; every segment must be safe for the whole command to be safe.
- REQ-2: Any output redirection (`>`, `>>`, `tee`, `Out-File`, `Set-Content`) to a path inside the repo makes the command a mutation.
- REQ-3: Test-runner patterns are anchored to the segment start, not matched as substrings.
- REQ-4: `cli_safety` is evaluated before, and independently of, the read-only shortcut; a DENY from any gate wins.
- REQ-5: Table-driven tests covering the evidence above plus PowerShell equivalents (`ls; Remove-Item -Recurse src`).

## Acceptance Criteria

- [ ] All four evidence commands except `ls` alone are denied or routed through `cli_safety`
- [ ] Benign read-only commands stay allowed (no regression in `test_hooks_*`)
- [ ] Automated tests passing
