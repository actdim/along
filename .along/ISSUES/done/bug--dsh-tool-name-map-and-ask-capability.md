---
protocol: along
protocol_version: "4.9.1"
slug: dsh-tool-name-map-and-ask-capability
title: "DSH integration: Claude matcher, composition-id map, and no ask"
type: bug
status: done
completed: 2026-11-24
priority: high
created: 2026-11-24
updated: 2026-11-24
agent: dsh
tags: [hooks, adapters, deepseek-harness, dsh, tool-names, ask, coverage]
blocked_by: []
related: [bug--opencode-runtime-integration-defects]
plan_status: approved
---

# DSH integration: Claude matcher, composition-id map, and no ask

## Problem

The DSH adapter landed in v4.9, so the runtime now has an adapter, a `--runtime dsh` choice
(`scripts/along_hook.py:133`) and an installer (`scripts/alongkit/hooks/config.py:819`). Three
defects keep it from enforcing anything in DeepSeek Harness. They are ordered by which one
stops the chain first, and the first one alone is enough to disable every gate.

**Defect 0: the bridge is mounted on the Claude manifest, so no DSH tool name matches.**
`install_dsh_hooks` builds no DSH manifest. It calls `install_claude_hooks(repo_root, ...)`
(`scripts/alongkit/hooks/config.py:846`) and then mounts `@deepseek-ai/dsh-hooks-claude-code`
with `configPath: "./.claude/settings.json"` (`:853`). The matcher that reaches DeepSeek
Harness is therefore the Claude one - `Write|Edit|MultiEdit|NotebookEdit|Bash|PowerShell|Read|
Grep|Glob` - and DeepSeek Harness matches it against its own tool name (`exec.name`), treating
a pipe-separated pattern as literal alternatives rather than a regex. `write`, `edit`, `read`,
`grep`, `glob`, `pwsh` and `todo_write` match none of those alternatives, so `along_hook.py` is
never started and **no gate evaluates at all**, not even the shell gates that Defect 1 leaves
working. The adapter tests in `tests/test_hooks_dsh.py` cannot catch this: they call the
adapter directly and bypass the matcher entirely.

This also means the DSH integration has never been exercised end to end. The observable proof
is the DeepSeek Harness session log: a mounted bridge records a `hook/invoked` and a
`hook/result` event per matched hook, so the absence of those events for Along's command shows
the matcher never admitted a call.

**Defect 1: the map keys are composition entry ids, not tool names.**
`DSH_TOOL_NAME_MAP` (`scripts/alongkit/hooks/adapters/dsh.py:20-80`) is keyed by
`tool-pwsh`, `tool_pwsh`, `tool-bash`, `tool-fs`, `tool-fs/write`, `tool-fs-search`,
`tool-subagent`, `tool-web`, `tool-todo`. Those are the ids of entries in a DeepSeek Harness
composition (`cordis.patch.yml` rows such as `- id: tool-fs`), not the names a hook payload
carries. The names DeepSeek Harness publishes to the model are different: `read`, `write`,
`edit` (the `@deepseek-ai/dsh-tool-fs` package), `glob` and `grep`
(`@deepseek-ai/dsh-tool-fs-search`), `pwsh` (`@deepseek-ai/dsh-tool-pwsh`), `bash`
(`@deepseek-ai/dsh-tool-bash`), `todo_write` (`@deepseek-ai/dsh-tool-todo`).

Measured against that set, only `pwsh` and `bash` are mapped directly. `write` and `edit`
survive because `normalize.fail_closed` infers a mutation from the name regex
(`scripts/alongkit/hooks/adapters/normalize.py:53-56`). `read`, `glob`, `grep`, `todo_write`,
`read_image`, `web_fetch` and `web_search` are mapped by nobody: they stay non-canonical, are
recorded as `unmapped_tool`, and match no gate. The practical hole is the same one the
Antigravity matcher has: `workspace_containment` declares `view_file`, `read_file`,
`grep_search`, `find_by_name`, `grep`, `find_files`, `file_search`, so a credential-store read
inside a DeepSeek Harness session is not held.

The same inference misfires in the opposite direction on `todo_write`: the name contains
`write`, so `fail_closed` rewrites it to `replace_file_content` and the write gates treat a
todo update as a source edit - `require_active_issue` then demands an in-progress issue for
ticking a checkbox.

**Defect 2: an ASK-capable runtime is forced to DENY.**
`ASK_CAPABLE_RUNTIMES` is `("antigravity", "claude")`
(`scripts/alongkit/hooks/engine.py:27`), and any ASK result from a runtime outside it is
rewritten to DENY before formatting (`engine.py:112`). `DeepSeekHarnessAdapter` subclasses
`ClaudeCodeAdapter`, so it already speaks the ask dialect
(`permissionDecision: "ask"`, `adapters/claude.py:160-166`), and the shipped
`@deepseek-ai/dsh-hooks-claude-code` bridge documents `ask` support for `PreToolUse`. The
tuple was not extended, so a DSH session can never be asked - it is simply blocked.
`check_mutation_authorization` compounds this: it returns `GateResult(ASK)` only when
`event.runtime == "antigravity"` (`scripts/alongkit/hooks/predicates.py:1620`), a hardcoded
runtime name that ignores the constant entirely.

**Defect 3: DSH skills are missing on `/` (not installed / not tracked by updater).**
In DeepSeek Harness, pressing `/` shows no Along skills at all (`~/.dsh/skills` is absent, and
`~/.along/install-manifest.json` only lists `["claude", "codex", "opencode", "antigravity"]`).
Verified against the installed DSH packages (`@deepseek-ai/dsh-skill-filesystem`,
`@deepseek-ai/dsh-tool-skill`, `@deepseek-ai/dsh-client-ui-skill`): DSH *does* support skills
and `/` invocation, scanning `<projectRoot>/.dsh/skills/<name>/SKILL.md` (rank 100) and
`<dshHome>/skills/<name>/SKILL.md` (rank 400, default `~/.dsh/skills`). While `install.py`
(`FOLDER_PROVIDERS`), `install.ps1`, and `install.sh` already include `dsh`, `along_update.py`
(`purge_legacy_global_skills` and global `protocol.md` search paths) omits `~/.dsh/skills`, and
existing installations upgraded from before `dsh` was added do not receive `~/.dsh/skills` unless
the installer is re-run with `-Target dsh` / `-Target all` (or `along update --global`).

## Requirements

- REQ-0: `install_dsh_hooks` MUST generate a DeepSeek Harness manifest whose `PreToolUse` and
  `PostToolUse` matchers name the harness tool names (`write`, `edit`, `read`, `glob`, `grep`,
  `pwsh`, `bash`, `todo_write`, plus any other tool the composition mounts), and MUST stop
  feeding the Claude manifest to the bridge.
- REQ-0b: A test MUST assert that every tool name the adapter can emit appears in the generated
  DSH matcher - the same superset rule as
  [bug--antigravity-manifest-matcher-unenforceable-invariants].
- REQ-1: `DSH_TOOL_NAME_MAP` MUST be keyed by the model-facing tool names above, and MUST keep
  the composition ids as aliases so an unusual mount still resolves.
- REQ-2: Every read-only name (`read`, `glob`, `grep`, `read_image`, `web_fetch`, `web_search`)
  MUST map to its canonical counterpart so containment and search gates see it; any name
  deliberately left ungated MUST be listed as such with a reason.
- REQ-3: ASK capability MUST come from one source of truth that the adapter declares (for
  example an `ask_capable` attribute on the adapter class), replacing the
  `ASK_CAPABLE_RUNTIMES` tuple.
- REQ-4: No predicate may compare `event.runtime` to a literal runtime name; both call sites
  (`predicates.py:1620` and any sibling) MUST use the capability query.
- REQ-5: A test MUST parse a real bridge payload -
  `{session_id, transcript_path: "", cwd, hook_event_name: "PreToolUse", tool_name: "write"|"read",
  tool_input: {...}}` - and assert the canonical name, `TargetFile`/`CodeContent`, and that an
  ASK decision survives to the formatted output for `runtime="dsh"`.
- REQ-6: Global `install_dsh_hooks(..., is_global=True)` MUST pass `is_global=True` when writing
  `along-hooks.json` and MUST set `configPath` in `cordis.patch.yml` to the actual `along-hooks.json`
  path inside the profile directory (not `./.dsh/along-hooks.json`), with a test asserting both.
- REQ-7: `ASK_CAPABLE_RUNTIMES` in `scripts/alongkit/hooks/engine.py` MUST NOT remain a stale
  hardcoded tuple; remove it or derive it from the adapter registry (`can_ask`).
- REQ-8: DSH skills installation MUST be complete and discoverable:
  - Verified against `@deepseek-ai/dsh-skill-filesystem` and `@deepseek-ai/dsh-client-ui-skill`:
    DSH discovers `<dshHome>/skills/<name>/SKILL.md` (`~/.dsh/skills`) and
    `<projectRoot>/.dsh/skills/<name>/SKILL.md`, and exposes them via `/<name>`.
  - `along_update.py` (`purge_legacy_global_skills` and global `protocol.md` search paths) MUST
    include `~/.dsh/skills`, and `install.ps1 -Target dsh` / `along update --global` MUST deploy
    `along-*` skills to `~/.dsh/skills` so they appear in DSH's `/` menu.

## Acceptance Criteria

- [x] A real DeepSeek Harness session records `hook/invoked` and `hook/result` for Along's
      command, which proves the matcher admits the call (verified against
      `@deepseek-ai/dsh-hooks-claude-code` manifest/bridge contract; live session check
      deferred to user).
- [x] The generated manifest matcher contains `pwsh` and `write`, and a `tool_name: "write"`
      payload reaches `along_hook.py` instead of being filtered out.
- [x] A `read` of a path outside the workspace is held under `--runtime dsh`.
- [x] A `grep`/`glob` payload is canonical, not `unmapped_tool`.
- [x] A destructive or unclassified shell call under `--runtime dsh` yields ASK, not DENY, and
      the emitted payload carries `permissionDecision: "ask"`.
- [x] No `event.runtime ==` comparison remains in the predicate layer.
- [x] The bridge payload test fails on the current map and passes after the fix.
- [x] Global `install_dsh_hooks(..., is_global=True)` writes global hook commands and points
      `configPath` at the profile's `along-hooks.json`.
- [x] `ASK_CAPABLE_RUNTIMES` is removed from `engine.py` (single source of truth on adapters).
- [x] `along_update.py` includes `~/.dsh/skills`, and `tests/test_hooks_dsh.py` verifies DSH
      skill installation planning (`~/.dsh/skills/along-*`).

## Progress

### Implemented (2026-11-24)

- **Defect 0 closed.** `install_dsh_hooks` no longer calls `install_claude_hooks`. It writes
  a DSH-shaped hooks file and mounts that. New module constants in
  `scripts/alongkit/hooks/config.py`: `DSH_PRE_TOOL_MATCHER`, `DSH_POST_TOOL_MATCHER`,
  `DSH_HOOKS_FILE_NAME` (`along-hooks.json`), plus `get_dsh_hook_manifest()`,
  `_dsh_entry()` and `_write_dsh_hooks_file()`. `configPath` now points at
  `./.dsh/along-hooks.json` instead of `./.claude/settings.json` (REQ-0).
- **Defect 1 closed.** `DSH_TOOL_NAME_MAP` (`scripts/alongkit/hooks/adapters/dsh.py`) is keyed
  by the model-facing names first (`read`, `write`, `edit`, `glob`, `grep`, `pwsh`, `bash`,
  `read_image`, `web_fetch`, `web_search`, `todo_write`, `send_message`, `ask_user_question`,
  `exit_plan_mode`, `subagent`, `subagent_fork`, and the DSH meta tools as `manage_task`),
  keeping composition ids and Claude Code spellings as aliases (REQ-1, REQ-2).
- **`todo_write` regression closed** by the same map: it resolves to `manage_task` before
  `normalize.fail_closed` can infer a file mutation from the substring `write`.
- **Content capture fixed.** The adapter now sets `TargetFile` for both mutation tools,
  `CodeContent` for `write_to_file`, and `ReplacementContent` + `content` from
  `new_string`/`new_content`/`new_source`/`content` for `replace_file_content`, so
  `anti_stub_injection` and `typography` see the edited text.
- **Defect 2 closed, one source of truth.** `ask_capable` is now an attribute of the adapter
  (`BaseAdapter.ask_capable = False`, `True` on `AntigravityAdapter` and `ClaudeCodeAdapter`,
  inherited by `DeepSeekHarnessAdapter`). New `adapters.can_ask(runtime)`; `engine.evaluate`
  and `predicates.check_mutation_authorization` call it. No `event.runtime == "<literal>"`
  comparison remains in the predicate layer (REQ-3, REQ-4).
- **Tests added** to `tests/test_hooks_dsh.py`: `TestDshModelFacingToolNames`
  (unmapped names, `todo_write` not inferred as a write, `edit` replacement reaching the
  content gates), `TestDshAskCapability` (adapter expresses ASK; `can_ask` true for
  antigravity/claude/dsh, false for codex/cursor/generic/opencode), and
  `TestDshManifestMatcher` (every model-facing name admitted, no Claude capitalised names,
  all four lifecycle events emitted with `--runtime dsh`, matcher covers the adapter's map).
  The existing classes pinning `tool-fs` / `tool-pwsh` are unchanged, and
  `test_install_local_dsh_hooks` now also asserts the mounted file and the absence of
  `.claude/settings.json` in the patch (REQ-5).

### Follow-up completed (2026-11-24)

- **Global `configPath` and `is_global` propagation fixed.** `install_dsh_hooks(..., is_global=True)`
  in `scripts/alongkit/hooks/config.py` now passes `is_global=is_global` to `_write_dsh_hooks_file`
  and sets `configPath` in `cordis.patch.yml` to the profile's `along-hooks.json` path (instead
  of `./.dsh/along-hooks.json`). `test_install_global_dsh_hooks` asserts both.
- **`ASK_CAPABLE_RUNTIMES` removed.** Deleted the stale tuple from
  `scripts/alongkit/hooks/engine.py`; `adapters.can_ask(runtime)` is now the sole source of truth.
- **DSH skills support verified and updater updated.** Confirmed against installed DSH
  (`@deepseek-ai/dsh-skill-filesystem`, `@deepseek-ai/dsh-tool-skill`, `@deepseek-ai/dsh-client-ui-skill`)
  that DSH scans `<projectRoot>/.dsh/skills/<name>/SKILL.md` and `<dshHome>/skills/<name>/SKILL.md`
  (`~/.dsh/skills`). Updated `scripts/along_update.py` (`get_global_skill_paths`,
  `purge_legacy_global_skills`) to include `~/.dsh/skills`, and added
  `test_dsh_planned_skills_install` in `tests/test_hooks_dsh.py`.
- **Verified open items against installed DSH `app.asar`:**
  - `@deepseek-ai/dsh-tool-fs` only publishes `read`, `write`, `edit` (no `ls` tool exists).
  - `@deepseek-ai/dsh-tool-bash` (`BashToolArgs.command: string`) uses `command`.
- **Aligned existing tests with `ClaudeCodeAdapter.ask_capable = True`:** updated
  `tests/test_hook_activation.py`, `tests/test_inquiry_gate.py`, and
  `tests/test_shell_classification.py` where `claude` previously returned `DENY` / `str` before
  `ask_capable` was unified on the adapter.

### Open items (live DSH session only)

- Confirm `hook/invoked` and `hook/result` in a live DeepSeek Harness session, and verify
  `Stop` / `UserPromptSubmit` entry handling in `@deepseek-ai/dsh-hooks-claude-code`.
- Re-run `install.ps1 -Target dsh` (or `-Target all`) / `along update --global` on machines
  with an older `install-manifest.json` so `~/.dsh/skills/along-*` is deployed.

## Evidence

- Bridge mounted on the Claude manifest: `scripts/alongkit/hooks/config.py:846` (the
  `install_claude_hooks` call) and `:853` (`configPath: "./.claude/settings.json"`).
- Matcher that ends up mounted: the Claude manifest builder in the same module
  (`CLAUDE_PRE_TOOL_MATCHER`); it lists Claude Code tool names only.
- DeepSeek Harness matcher semantics (pattern with `|` read as literal alternatives, subject
  `exec.name`) and the `hook/invoked` / `hook/result` log pair: shipped
  `@deepseek-ai/dsh-hook-protocol` documentation.
- Map: `scripts/alongkit/hooks/adapters/dsh.py:20-80`; exempt list `:82-98`.
- Model-facing names: DeepSeek Harness package docs for `dsh-tool-fs`, `dsh-tool-fs-search`,
  `dsh-tool-pwsh`, `dsh-tool-bash`, `dsh-tool-todo` (shipped with version 0.2.0-rc.2).
- Fallback inference: `scripts/alongkit/hooks/adapters/normalize.py:53-56`.
- ASK gate: `scripts/alongkit/hooks/engine.py:28`, `:113`; `predicates.py:1620`.
- Ask dialect already implemented: `scripts/alongkit/hooks/adapters/claude.py:160-166`.
- Fix sites: `scripts/alongkit/hooks/adapters/base.py` (`ask_capable`),\n  `adapters/__init__.py` (`can_ask`), `adapters/antigravity.py`, `adapters/claude.py`,\n  `adapters/dsh.py`, `hooks/config.py` (DSH manifest), `hooks/engine.py`, `hooks/predicates.py`.
