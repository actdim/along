---
protocol: along
protocol_version: "4.9.1"
slug: opencode-runtime-integration-defects
title: "OpenCode/DSH runtime integration: dead Stop gates, broken runner CLI, false mechanical status"
type: bug
status: in-progress
priority: high
created: 2026-11-24
updated: 2026-11-24
agent: opencode
tags: [opencode, runtime, hooks, runner, deepseek, audit]
blocked_by: []
related: [bug--opencode-runtime-v2-hardening, bug--opencode-shell-env-runner-fix, feat--opencode-runtime-integration, feat--deepseek-runtime-adapter, feat--deepseek-harness-bridge, bug--runtime-adapters-invented-cli-contracts]
plan_status: approved
---

# OpenCode/DSH runtime integration: dead Stop gates, broken runner CLI, false mechanical status

Aggregate ticket for the 2026-11-24 audit of every closed issue that touched the OpenCode,
DeepSeek Harness (DSH) and DeepSeek runner integration. Each finding below was reproduced
against the code and the tools installed on this machine, not inferred from the closed
tickets' acceptance checkboxes.

Environment used for verification: OpenCode `2.3.2`, Python suite at `1998 tests OK`
(12 skipped), typography clean, working tree clean before the audit.

## Problem Statement

The closed tickets claim a working mechanical integration: `along doctor` reports
`[OK] Gate enforcement: mechanical` for `opencode`, and three tickets are marked done with
every box ticked. In practice the lifecycle coverage is partial, the headless runner cannot
start, and the doctor signal is produced by a substring match. An agent running under
OpenCode today gets tool-level gates but no Stop gates, while the operator is told the
runtime is mechanically enforced.

Two independent failure classes exist:

1. The OpenCode plugin targets hook names that OpenCode 2.3.2 does not trigger, and the
   fallback subscription uses the V1 callback contract instead of the V2 async-iterator
   contract.
2. The headless runner and the runtime registry disagree: `along run opencode` builds a
   command line that 2.3.2 rejects, and `along run deepseek|dsh` is not reachable at all
   even though `RUNNER_MAP` and `ORCHESTRATOR_RUNTIMES` contain it.

## Findings

### P0 - Stop gates never evaluate under OpenCode 2.3.2

`scripts/alongkit/hooks/opencode_plugin.js:313-318` registers
`ctx.session.hook("idle")` and `ctx.session.hook("stop")`.

The OpenCode 2.3.2 binary (`%LOCALAPPDATA%\mise\installs\opencode\2.3.2\opencode.exe`)
enumerates these session hook triggers:
`experimental.idle`, `experimental.model.resolve`, `experimental.ws.handshake`,
`experimental.ws.receive`, `experimental.ws.send`, `fork`, `http.request`,
`http.response`, `model.request`, `prompt`, `retry`, `title`.

There is no `idle` trigger and no `stop` trigger. The idle hook is `experimental.idle`
with payload `{ sessionID, background }` (the built-in Goal plugin registers exactly that
name). OpenCode has no stop hook at all.

Evidence from this repository:

- `.along/diagnostics/hooks_audit.jsonl` contains 100 `Stop` entries and every one has
  `conversation_id: "ses-1"` (the Node contract test payload). No real session ever
  produced a `Stop` entry.
- The real OpenCode session `ses_df2945772ffehbopt9n6kv1lc9` produced `read`, `glob`,
  `webfetch`, `run_command` and `skill` entries only.
- `.along/.session/prompts/opencode--ses_df2945772ffehbopt9n6kv1lc9.json` was written on
  2026-11-24, so `ctx.session.hook("prompt")` does fire. The dead part is idle/stop only.

Impact: `test_before_stop`, `wrap_before_stop`, `projection_sync_before_stop` and the
`require_plan_approval` Stop evaluation never run in an OpenCode session.

### P0 - `along run opencode` cannot start on OpenCode 2.x

`scripts/alongkit/runner/opencode.py:75-95` builds
`opencode run --format json --dir <repo_root> ...`, and `cli_version` is pinned to
`1.18.32`.

Live check: `opencode run --help` on 2.3.2 has no `--dir` flag and fails with
`ERROR Unrecognized flag: --dir in command opencode run`. The recorded fixture
`tests/fixtures/runtimes/opencode/1.18.32/help.txt` does contain `--dir`, so the adapter
matches a version that is no longer installed, and nothing validates the live CLI version
before building the command.

`tests/test_runtime_adapters.py:107` asserts `--dir` in the built command, so the test suite
locks in the broken flag instead of catching the drift.

### P0 - `along run deepseek|dsh` is not reachable from the CLI

`scripts/alongkit/runner/__init__.py:24-33` registers `deepseek`, `deepseek-harness` and
`dsh` in `RUNNER_MAP`, and `scripts/alongkit/orchestrator.py:40-48` lists them in
`ORCHESTRATOR_RUNTIMES`. `scripts/alongkit/commands/ops.py:278` only accepts
`("claude", "claude-code", "codex", "opencode", "generic")`.

Result: `along run deepseek --dry-run` does not reach the runner. It falls through to the
lifecycle command proxy, tries to execute `deepseek --dry-run` as an external command and
dies with `WinError 2`. `along run --help` likewise omits the runtime.

The acceptance criterion "`deepseek` is accepted as a valid runtime by `along run`" in
`feat--deepseek-runtime-adapter` is therefore false.

### P0 - `along doctor` reports mechanical enforcement for a half-dead plugin

`scripts/alongkit/runtime.py:200-205` returns `True` for `opencode` when the installed
plugin text contains both `along-gates` and `setup`. `enforcement_level` then returns
`MECHANICAL` without checking:

- that the registered hook names are valid for the installed OpenCode version,
- that a Stop or idle hook ever fired (only a generic heartbeat exists),
- that no stale duplicate plugin is loaded.

Observed: `along doctor` prints
`[OK] Gate enforcement: mechanical. Along hooks are registered for opencode; gates block
violations.` followed by `Last opencode hook run ... (0m ago)`, even though Stop gates are
dead. The heartbeat is refreshed by `PreToolUse`, so freshness proves nothing about
lifecycle coverage.

### P1 - The V2 event-subscription fallback uses the V1 contract

`scripts/alongkit/hooks/opencode_plugin.js:326` calls
`ctx.event.subscribe(async (evt) => { ... })`.

In 2.3.2 the context exposes
`event.subscribe({ types }) -> async iterable` (the plugin proxy wraps
`e.event.subscribe({ types: o?.types })`). Passing a callback registers nothing and the
returned stream is never consumed, so the fallback that was meant to cover idle/stop is
dead as well. It also leaves an unconsumed subscription behind.

### P1 - Duplicate stale project plugin is loaded next to the global one

`~/.local/share/opencode/log/opencode.log` shows both plugins loaded in the same run:

- `C:\Users\Admin\.config\opencode\plugins\along-gates.js` (current source, identical hash),
- `D:\Src\my\actdim\public\along\.opencode\plugins\along-gates.js` (2026-11-13, 10412 bytes,
  gitignored).

Both export `{ id, setup }`, so every tool call runs the hook twice, doubles audit entries
and prompt records, and doubles Stop work once Stop is fixed. `install_opencode_hooks`
rewrites the project copy only when run with a local target; a global install does not
prune it.

### P1 - OpenCode tool names are only partially mapped

`scripts/alongkit/hooks/adapters/generic.py:34-67` has no entries for `read`, `glob`,
`grep`, `webfetch`, `skill`, `task` or `todowrite`.

The audit log shows 51 `read`, 9 `glob`, 5 `webfetch` and 1 `skill` entries as
`unmapped_tool` (allowed in audit mode). Read-only tools can stay unmapped by decision,
but `skill` and `task` are not read-only and there is no documented decision that they are
intentionally ungated, so the map is incomplete rather than deliberate.

### P1 - `shell.hook("env")` is not a 2.3.2 hook

`opencode_plugin.js:341` registers `ctx.shell.hook("env")`. The only shell trigger in
2.3.2 is `create.before`, which the plugin also registers, so session env injection works
only through that path and only when a session id has already been cached. The `env`
registration is dead code that suggests a second, non-existent path.

### P1 - The DeepSeek runner is DSH, not DeepSeek, and the API path is unimplemented

`scripts/alongkit/runner/deepseek.py` implements `DeepSeekHarnessRunner` around the `dsh`
binary (`default_binary = "dsh"`, `cli_version = "0.2.0"`), not the DeepSeek HTTP API
described by `feat--deepseek-runtime-adapter` (`deepseek-chat`/`deepseek-reasoner`,
`--model`, endpoint parameter).

- `along run deepseek --base-url ...` never reaches the runner (see the P0 above), and
  `DeepSeekHarnessRunner` has no endpoint flag, so `--base-url` has no effect.
- There are no recorded `dsh --help` fixtures, and `dsh` is not installed on this machine,
  so `cli_version = "0.2.0"` is unverified.
- `format_usage_summary` is used only by `tests/test_runtime_adapters.py:481`, never by
  `along run`, `along wrap` or `along doctor`.
- `get_opencode_session_tokens` (`runner/opencode.py:209`) has no caller and no test.

### P1 - Plugin SDK pin does not track the runtime

`~/.config/opencode/package.json` pins `@opencode-ai/plugin` to `1.17.12` while the
installed runtime is `2.3.2`. The V2 types in that package expose only the domain hooks
(`agent`, `aisdk`, `catalog`, `command`, `integration`, `plugin`, `reference`, `skill`) and
do not describe `tool.hook`, `session.hook` or `shell.hook`, so the typings cannot catch an
invalid hook name. The pin should follow the runtime, and the plugin should be validated
against the live binary, not against stale types.

### P2 - Closed-ticket acceptance criteria that are still false

- `feat--opencode-runtime-integration` REQ-8: no `along doctor entities` check compares
  `ISSUES.md` plan annotations with front matter `plan_status` (no such code in
  `scripts/alongkit/commands/doctor.py`).
- `feat--opencode-runtime-integration` REQ-9: `along issue lint` does not warn about a
  `plan.md` whose free-text header contradicts `plan_status` (no `Status: proposed`
  detection anywhere in `scripts/alongkit/`).
- `bug--opencode-runtime-v2-hardening` REQ-8: the doctor validates neither V2 syntax nor
  hook names; the substring check is the whole implementation.
- `feat--deepseek-harness-bridge`: the DSH bridge is documented and an installer exists,
  but the "verified across PreToolUse and Stop events" claim cannot be reproduced because
  `dsh` is not installed; `along doctor` only string-matches `cordis.patch.yml`.
- `bug--runtime-adapters-invented-cli-contracts`: the OpenCode half regressed back to an
  invented flag for the installed version (`--dir`).

### P2 - `along issue find` prints an empty title for legacy issues

`along issue find <slug>` prints `Title:` with no value. The discovery payload built for
`find` does not carry the title, while `along issue show` reads it correctly from front
matter (`scripts/alongkit/commands/issue.py:811` vs `:615`). It stays empty even for a file
that has `title:`. Cosmetic, but the protocol tells agents to use `find` for discovery, and
the output looks broken.

### P2 - Remaining test-suite cleanup and history noise

Carried over from the verification of `debt--test-suite-paper-compliance-cleanup`:

- `tests/test_docs.py:25-92` is unchanged despite being listed in scope.
- `tests/test_skills_and_scripts.py:1757-1768` and `:1977` are unchanged.
- `tests/test_system_comparisons.py:64-69` uses `^```(\w*)` to count fences, which also
  matches closing fences; the document it guards has zero fences, so the test is vacuous.
- Git history contains duplicate commit pairs for each of the three verified issues. Not
  functional, but it obscures the real fix commits.

## Requirements

- REQ-1: `opencode_plugin.js` MUST register `ctx.session.hook("experimental.idle", ...)`
  for idle/Stop evaluation and MUST NOT register the non-existent `idle` or `stop` names.
- REQ-2: Stop evaluation MUST be wired to a real 2.3.2 signal; when the runtime offers no
  stop hook, the plugin MUST document and use `experimental.idle` (or the V1 `event` hook)
  and MUST pass `sessionID` from the payload.
- REQ-3: The event fallback MUST use the V2 contract
  (`for await (const event of ctx.event.subscribe({ types }))`) or be removed.
- REQ-4: `OpenCodeRunner.build_command` MUST NOT pass `--dir`; it MUST set the working
  directory through `cwd` and MUST validate the live `opencode --version` against a
  supported range before building the command.
- REQ-5: `along run` MUST accept `deepseek`, `deepseek-harness` and `dsh` from the CLI, or
  the registry entries MUST be removed; the two lists MUST come from one source.
- REQ-6: `DeepSeekHarnessRunner` MUST be described as DSH-only, and the DeepSeek HTTP API
  runner either implemented or dropped from the issue's claims; `--base-url` MUST reach the
  adapter that uses it.
- REQ-7: `along doctor` MUST report `mechanical` for `opencode` only after validating the
  hook names against the installed runtime and observing a lifecycle heartbeat that is not
  `PreToolUse` only; otherwise it MUST report `advisory` with the reason.
- REQ-8: The plugin installer MUST prune stale project copies of `along-gates.js` on a
  global install, and `along doctor` MUST warn when the same plugin id is loaded twice.
- REQ-9: `TOOL_NAME_MAP` MUST cover every non-read-only OpenCode tool name, and read-only
  names MUST be listed explicitly as intentionally ungated.
- REQ-10: `install_opencode_hooks` MUST refuse to install a plugin whose registered hook
  names are not in the target runtime's trigger list, or emit a warning naming them.
- REQ-11: `feat--opencode-runtime-integration` REQ-8 and REQ-9 MUST be implemented or the
  closed ticket MUST be reopened and its criteria corrected.
- REQ-12: `along issue find` MUST carry the front matter `title` (falling back to the H1
  heading) in its discovery payload.
- REQ-13: Tests MUST assert against recorded live `--help` output for the installed version
  and MUST fail when a flag disappears; the vacuous fence test MUST be replaced with one
  that counts real opening fences.
- REQ-14: `format_usage_summary` and `get_opencode_session_tokens` MUST be wired into
  `along run`, `along wrap` or `along doctor`, or removed.

## Acceptance Criteria

- [ ] A real OpenCode 2.3.2 session produces at least one `Stop` (or idle) audit entry with
  the real `ses_...` id, not `ses-1`.
- [ ] `along run opencode --dry-run` produces a command line that `opencode run` accepts on
  2.3.2, and the run completes a trivial prompt.
- [ ] `along run dsh --dry-run` and `along run deepseek --dry-run` reach
  `DeepSeekHarnessRunner`, not the command proxy.
- [ ] `along doctor` reports `advisory` (with the dead-hook reason) for the current plugin,
  and `mechanical` only after the fixed plugin is installed and an idle hook has fired.
- [ ] The project `.opencode/plugins/along-gates.js` no longer loads next to the global
  copy, or doctor warns about the duplicate.
- [ ] No OpenCode session produces `unmapped_tool` for `skill` or `task`; the read-only
  decision is documented.
- [ ] `along issue lint` flags a `plan.md` with `Status: proposed` under an approved
  `plan_status`; `along doctor entities` flags a projection that disagrees with front
  matter.
- [ ] `tests/test_runtime_adapters.py` fails if `opencode run --help` loses a flag the
  adapter uses.
- [ ] `tests/test_system_comparisons.py` fence check fails on an unclosed fence in the
  guarded document.
- [ ] `along sanitize` is clean and `python .along/scripts/test.py` is green.

## Verification notes

- `bug--opencode-plugin-test-hermeticity`: verified fixed (16 tests pass with a dirty
  tracked file and an untracked file; no new `ses-1` Stop entries from the suite).
- `debt--test-suite-paper-compliance-cleanup`: partial, see the P2 test section.
- `task--opencode-deepseek-cache-configuration-audit`: mostly not done (no audit document,
  no reachable CLI flag, no timeout safety net, no wrap/doctor token metrics).
- Working tool hooks confirmed: `tool.execute.before` and `session.hook("prompt")` fire in
  a real 2.3.2 session; the defects above are about the missing lifecycle half and the
  runner/doctor layer.
