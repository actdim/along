---
protocol: along
protocol_version: "4.5.3"
slug: runtime-adapters-invented-cli-contracts
type: bug
status: open
priority: high
created: 2026-10-23
updated: 2026-10-23
agent: claude-code
tags: [runner, claude-code, codex, opencode, autonomous]
blocked_by: []
related: [feat--agent-runtime-adapters-claude-codex-opencode, spike--headless-runtimes-on-linux]
---

# Runtime adapters use nonexistent CLI flags and output schemas

## Problem

Review of commit 4e0cea6 (`feat--agent-runtime-adapters-claude-codex-opencode`),
`scripts/alongkit/runner/`. The spike `spike--headless-runtimes-on-linux` was desk research with
no recorded CLI versions or runs; the adapters and their tests inherited its guesses.

- `codex.py` passes `--non-interactive`, which `codex exec` does not accept; `exec` also defaults
  to a read-only sandbox, so an implementer cannot write. The JSONL parser matches event names
  that `codex exec --json` does not emit.
- `opencode.py` passes `--yes`, which `opencode run` does not accept; `--format json` emits JSONL,
  and the greedy `\{.*\}` regex never parses it.
- `claude.py` reads `tool_calls`, `cost` and `status: needs-input`, none of which the
  `--output-format json` result carries (cost is `total_cost_usd`); file extraction and
  needs-input detection are dead. Default role args pass `--dangerously-skip-permissions` twice,
  and to codex/opencode too when a config only sets `runtime`.
- `base.py`: on timeout only the direct child is killed, so npm `.cmd` shims on Windows and tool
  subprocesses on Linux survive and keep the pipes open (second `communicate()` hangs);
  `git status --porcelain` lines are `strip()`ped before slicing (`" M foo.py"` becomes
  `"oo.py"`); the whole `os.environ` (Telegram token, every provider key) goes to every runtime;
  the brief is passed as an argument (cmd.exe 8191-char limit and re-parsing on Windows), and
  stdin is inherited.
- `AntigravityRunner` became selectable as an orchestrator runtime although the spike ruled out a
  headless Antigravity CLI.
- Tests assert the invented flags and payloads.

## Requirements
- REQ-1: Each adapter's command line MUST use only flags verified against a recorded CLI version (`<tool> --version` and `--help` output kept as test fixtures).
- REQ-2: The codex implementer MUST run with a sandbox that allows workspace writes.
- REQ-3: Each parser MUST read the real output schema of its CLI, verified against captured sample output kept as fixtures.
- REQ-4: Timeouts MUST kill the whole process tree (process group on POSIX, `taskkill /T` or a job object on Windows).
- REQ-5: Changed-file detection MUST parse porcelain lines without corrupting paths.
- REQ-6: Runtimes MUST receive an allowlisted environment (PATH, HOME, locale, plus the keys that runtime needs), never the full parent environment.
- REQ-7: The brief MUST be passed on stdin; stdin MUST otherwise be closed.
- REQ-8: Antigravity MUST NOT be offered as an orchestrator runtime.
- REQ-9: Role default args MUST be runtime-specific and not duplicated.

## Acceptance Criteria
- [ ] Fixtures hold real `--help` and sample output for claude, codex and opencode with their versions.
- [ ] A test with a child that spawns a grandchild proves the timeout kills both.
- [ ] `" M foo.py"` yields `foo.py`.
- [ ] An adapter run does not see `ALONG_TELEGRAM_BOT_TOKEN` or another runtime's API key.
- [ ] A 20 KB brief runs on Windows through a `.cmd` shim.
- [ ] Regression tests cover each criterion and fail on the old code; `python .along/scripts/test.py` is green.
