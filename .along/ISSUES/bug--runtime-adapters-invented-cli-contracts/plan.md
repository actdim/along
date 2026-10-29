# Living Plan: runtime-adapters-invented-cli-contracts

## Revision 1 (2026-10-29T12:14:21Z, plan approve --plan-file)

# Living Plan: bug--runtime-adapters-invented-cli-contracts

Execution Mode: Role-Based (more than 3 files; crosses runner, orchestrator, proc, commands, tests and docs)

## Context

Commit 4e0cea6 built the claude, codex and opencode adapters from desk research: some flags do not exist,
the parsers match no real output, and the base supervisor leaks the parent environment, kills only the
direct child on timeout, corrupts porcelain paths and passes the brief on argv. This plan grounds every
adapter in recorded CLI help and captured sample output, hardens `BaseRunner.execute_run`, and removes
Antigravity from the orchestrator runtimes.

Facts the steps rely on (verified 2026-10-29):

- Installed: `claude --version` = `2.1.228 (Claude Code)` (`~/.local/bin/claude.exe`); `codex --version` =
  `codex-cli 0.158.0` (`C:\nvm4w\nodejs\codex.cmd`, npm `.cmd` shim); `opencode --version` = `1.18.32`
  (`C:\ProgramData\chocolatey\bin\opencode.exe`, a chocolatey shim that spawns a child).
- claude `--help`: `-p, --print`; `--output-format` text (default) | json (single result) | stream-json;
  `--model <model>`; `--permission-mode` acceptEdits | auto | bypassPermissions | manual | dontAsk | plan;
  `--dangerously-skip-permissions`; `--no-session-persistence` (only with `--print`); no cwd flag. Reading the
  prompt from stdin when `-p` has no prompt argument is not stated: Step 1 verifies it.
- codex `exec --help`: `[PROMPT]` "If not provided as an argument (or if `-` is used), instructions are read
  from stdin"; `--json` (JSONL events); `-s, --sandbox` read-only | workspace-write | danger-full-access;
  `-m, --model`; `-C, --cd <DIR>`; `--skip-git-repo-check`; `--ephemeral`; `--color never`;
  `-o, --output-last-message <FILE>`. No `--non-interactive`.
- opencode `run --help`: `message` positional (array); `--format` default | json (raw JSON events);
  `-m, --model` provider/model; `--dir`; `-f, --file`; `--auto` (auto-approve permissions not explicitly
  denied). No `--yes`. Stdin is not documented: Step 1 verifies it.
- Output schemas need a model call to observe; until Step 1 captures fixtures these are expectations only:
  claude json keys `type, subtype, is_error, result, total_cost_usd, usage{...}, num_turns, session_id` (no
  `tool_calls`, `cost`, `status`); codex JSONL `thread.started, turn.started, item.started|item.completed
  {item{type: agent_message|reasoning|command_execution|file_change{changes[{path,kind}]}}},
  turn.completed{usage}, turn.failed, error`; opencode JSONL `{type: step_start|text|tool_use|step_finish|error,
  part{...}}`.
- `scripts/alongkit/runner/base.py`: `BaseRunner.build_env` copies `dict(os.environ)`; `execute_run` uses
  `subprocess.Popen(cmd, ...)` with inherited stdin and no process group, then `kill()` and an unbounded
  `communicate()` on timeout; `_snapshot_git_status` does `line.strip()` then `line[3:]`
  (`" M foo.py"` -> `oo.py`).
- Adapters: `claude.py:build_command` hardcodes `--dangerously-skip-permissions`; `codex.py:build_command`
  passes `--non-interactive` and `build_env` sets an invented `OPENAI_MODEL`; `opencode.py` passes `--yes` and
  parses with a greedy `\{.*\}`; `generic.py:build_command` appends the prompt to argv.
- `scripts/alongkit/runner/__init__.py:RUNNER_MAP` includes `antigravity` and `agy`;
  `commands/ops.py:handle_run_command` uses `AntigravityRunner` directly for `along run antigravity`.
- `scripts/alongkit/orchestrator.py`: `DEFAULT_ROLES` sets `args: ["--dangerously-skip-permissions"]` for
  every role (so it reaches codex/opencode when only the runtime is overridden); `_instantiate_runner` passes
  `extra_args`, not the role; `DEFAULT_TIMEOUT = 1800` and `_role_timeout` exist (e8edb81).
  `commands/orchestrator.py` takes `--scout/--architect/--implementer/--reviewer` as free strings.
- `proc.run_capture` supports `stdin_text`. Every role writes files (`research.md`, `plan.md`, code,
  `reviews/step-N.md`), so every role needs write permission.
- Tests asserting invented contracts: `tests/test_runtime_adapters.py` (`test_claude_command_line_and_flags`,
  `test_codex_command_line_and_flags` with `--non-interactive`, `test_opencode_command_line_and_flags` with
  `--yes`, `test_claude_json_output_parsing` with `cost` / `tool_calls`, `test_claude_needs_input_parsing`,
  `test_codex_jsonl_events_parsing`, `test_opencode_json_output_parsing`, `TestRunRecordSynthesis`);
  `tests/test_orchestrator.py:test_load_from_json_config` uses runtime `antigravity`.

## Steps

- [ ] Step 1: Record real CLI contracts as fixtures (REQ-1, REQ-3)
  - Create `tests/fixtures/runtimes/<tool>/<version>/` for `claude/2.1.228`, `codex/0.158.0`,
    `opencode/1.18.32`, each with `version.txt` and `help.txt` (`claude --help`, `codex exec --help`,
    `opencode run --help`), captured by stdout redirection.
  - Capture samples in a scratch git repo outside tracked files (`git init` in the scratchpad), tiny prompts.
    These are paid model calls: tell the user before running them.
    - `echo Reply with the single word OK. | claude -p --output-format json --no-session-persistence > claude/2.1.228/sample-ok.json`
    - same with `--dangerously-skip-permissions` and "Create a file hello.txt containing hi." -> `sample-write.json`
    - `echo Reply with the single word OK. | codex exec --json --sandbox workspace-write --ephemeral --color never -C <scratch> - > codex/0.158.0/sample-ok.jsonl`
    - same with the hello.txt prompt -> `sample-write.jsonl` (must show a `file_change` item)
    - `echo Reply with the single word OK. | opencode run --format json --dir <scratch> > opencode/1.18.32/sample-ok.jsonl`
    - same plus `--auto` with the hello.txt prompt -> `sample-write.jsonl`
  - `tests/fixtures/runtimes/README.md`: the exact commands, date, and whether each tool read the prompt from
    stdin (the reply says OK). If opencode ignores stdin, fall back to a temp file with `-f <file>` and a fixed
    short message, recorded with `along plan revise`.
  - Scrub absolute user paths, tokens and emails from samples before committing; keep the JSON valid.

- [ ] Step 2: Contract test harness (REQ-1)
  - Each runner class gets `cli_version: str` (e.g. `CodexRunner.cli_version = "0.158.0"`) and `fixture_dir()`.
  - New `tests/test_runtime_contracts.py`: for each adapter and each role in `orchestrator.SUPPORTED_ROLES`,
    build the command (with `model` set) and assert every token starting with `-` appears in that version's
    `help.txt`; assert `version.txt` contains `cli_version`. Fails on old code (`--non-interactive`, `--yes`,
    missing attribute).

- [ ] Step 3: Real command lines; brief on stdin (REQ-1, REQ-2, REQ-7)
  - `BaseRunner.brief_via_stdin: bool = True`; `build_command(prompt)` no longer puts the prompt in argv:
    - claude: `[bin, "-p", "--output-format", "json", "--no-session-persistence", (--model M)] + role args + extras`
    - codex: `[bin, "exec", "--json", "--color", "never", "-C", repo_root, (-m M)] + role args + extras + ["-"]`
    - opencode: `[bin, "run", "--format", "json", "--dir", repo_root, (-m M)] + role args + extras`
    - generic: `{prompt}` template substitution stays an explicit opt-in; otherwise no prompt in argv.
  - Remove `OPENAI_MODEL` from `codex.build_env` and `ANTHROPIC_MODEL` from `claude.build_env` (`--model` covers both).
  - `execute_run`: `stdin=PIPE` and `communicate(input=brief)` when `brief_via_stdin`, else `stdin=DEVNULL`;
    dry-run output shows `"stdin_bytes": len(brief)` instead of the brief.
  - Tests (`tests/test_runtime_adapters.py`): rewrite the three `*_command_line_and_flags` tests to the new argv
    (brief not in argv); `test_brief_is_sent_on_stdin` (fake Python CLI writes `len(sys.stdin.read())` and
    `sys.argv`); `test_stdin_closed_when_unused` (generic `{prompt}` template, `brief_via_stdin=False`, the
    child's `sys.stdin.read()` returns "" at once); `test_20kb_brief_through_cmd_shim`
    (`skipUnless(os.name == "nt")`: `fake.cmd` runs `"<sys.executable>" "<script>" %*`;
    `CodexRunner(binary_path=fake.cmd)` with a 20480-byte brief: exit 0, 20480 bytes on stdin, argv under
    1 KB) plus a POSIX twin with a `#!/bin/sh` shim. All fail on old code.

- [ ] Step 4: Runtime-specific role args without duplicates (REQ-2, REQ-9)
  - Classmethod `role_args(role) -> List[str]`; all roles write files, so: claude
    `["--dangerously-skip-permissions"]`; codex `["--sandbox", "workspace-write"]` (docstring: the codex
    sandbox blocks network by default); opencode `["--auto"]`; generic `[]`.
  - `BaseRunner.__init__(role=...)`; `execute_run(role=...)` sets it before `build_command`.
  - `_merge_args(base, extra)` drops an extra flag already in `base` (with its value when the flag takes one;
    each runner keeps a `VALUE_FLAGS` set).
  - `orchestrator.DEFAULT_ROLES` drops `args` (`{"runtime": "claude-code"}` per role); configured `args` are
    extras only; `_instantiate_runner` passes `role=role`; `MockRunner` in `tests/test_orchestrator.py` accepts
    it via `**kwargs`.
  - Tests: `test_runtime_override_gets_own_default_args` (`overrides={"implementer": "codex"}` -> argv has
    `--sandbox workspace-write`, no `--dangerously-skip-permissions`); `test_claude_permission_flag_not_duplicated`
    (legacy `args: ["--dangerously-skip-permissions"]` -> count 1); `test_codex_implementer_sandbox_allows_writes`.
    All fail on old code.

- [ ] Step 5: Parsers read the real schemas (REQ-3)
  - Follow the fixtures wherever they differ from the expected shapes.
  - `claude.parse_output`: `json.loads` of stdout, falling back to the last line that parses; no greedy regex;
    usage `{input_tokens, output_tokens, cost_usd: total_cost_usd}`; outcome `fail` when `is_error` or exit
    != 0; text from `result`; remove the `tool_calls` / `status` handling (changed files come from git, Step 7;
    needs-input stays with `handoff.has_open_questions`).
  - `codex.parse_output`: JSONL; sum `turn.completed.usage`; `file_change` paths from `item.completed`; join
    `agent_message` text; `fail` on `turn.failed` / `error`.
  - `opencode.parse_output`: JSONL; concatenate text parts; tokens and cost from `step_finish`; file paths from
    `tool_use` parts of edit/write tools (field per fixture); `fail` on `error`; delete the regex path.
  - Tests: replace the invented-payload parsing tests and the `tool_calls` record test with fixture-driven ones:
    claude `usage["cost_usd"] == total_cost_usd`; claude `is_error: true` with exit 0 -> `fail`; codex
    `changed_files` contains `hello.txt`; opencode text contains `OK` and usage is not None. Fail on old code.

- [ ] Step 6: Process-tree kill on timeout (REQ-4)
  - `scripts/alongkit/proc.py`: `spawn_group_kwargs()` (`{"start_new_session": True}` on POSIX,
    `{"creationflags": subprocess.CREATE_NEW_PROCESS_GROUP}` on Windows) and
    `kill_process_tree(popen, grace=5.0)` (POSIX `os.killpg(pid, SIGTERM)`, wait, `SIGKILL`, ignore
    `ProcessLookupError`; Windows `taskkill /PID <pid> /T /F` with `capture_output=True, timeout=30`, fallback
    `popen.kill()`).
  - `execute_run`: use `spawn_group_kwargs()`; on `TimeoutExpired` call `kill_process_tree`, then
    `communicate(timeout=10)`; if that times out too, close the pipes and keep partial output; exit code 124.
  - Optionally the same in `proc.run_capture`'s timeout branch, only if no existing test changes.
  - Test `test_timeout_kills_grandchild`: the child spawns a grandchild that writes its pid and sleeps 30 s
    while inheriting stdout; with `timeout=2`, `execute_run` returns within 15 s and
    `daemon.is_pid_alive(grandchild_pid)` is False (tearDown kills leftovers). Fails on old code.

- [ ] Step 7: Porcelain parsing (REQ-5)
  - `_snapshot_git_status`: `git status --porcelain=v1 -z --untracked-files=all`, split on `\0` without strip;
    status `[:2]`, path `[3:]`; for `R` / `C` the next record is the source path, keep the destination.
  - Tests: `proc.git` patched to return `" M foo.py\0?? bar.txt\0R  new.py\0old.py\0"` -> keys
    `{"foo.py", "bar.txt", "new.py"}`; a real hermetic repo with committed then modified `foo.py` -> key
    `foo.py`, not `oo.py`. Fail on old code.

- [ ] Step 8: Allowlisted environment (REQ-6)
  - `BaseRunner.ENV_ALLOW`: `PATH, PATHEXT, HOME, USERPROFILE, HOMEDRIVE, HOMEPATH, APPDATA, LOCALAPPDATA,
    PROGRAMDATA, SYSTEMROOT, SYSTEMDRIVE, WINDIR, COMSPEC, TEMP, TMP, TMPDIR, LANG, LANGUAGE, TZ, TERM,
    XDG_CONFIG_HOME, XDG_DATA_HOME, XDG_CACHE_HOME, XDG_STATE_HOME, HTTP_PROXY, HTTPS_PROXY, NO_PROXY,
    SSL_CERT_FILE, NODE_EXTRA_CA_CERTS`, plus prefix `LC_`.
  - `RUNTIME_ENV_ALLOW`: claude `ANTHROPIC_API_KEY, ANTHROPIC_AUTH_TOKEN, ANTHROPIC_BASE_URL,
    CLAUDE_CONFIG_DIR`, prefix `CLAUDE_CODE_`; codex `OPENAI_API_KEY, OPENAI_BASE_URL, CODEX_HOME`; opencode
    `OPENAI_API_KEY, OPENAI_BASE_URL`, prefix `OPENCODE_`; generic none. Case-insensitive on Windows.
  - Role config `env_passthrough: [names]` adds explicit extras (wired through `_instantiate_runner`); then
    `UTF8_CHILD_ENV`, the `ALONG_*` run variables and `env_overrides`.
  - Test `test_runtime_env_is_allowlisted`: with `ALONG_TELEGRAM_BOT_TOKEN`, `ANTHROPIC_API_KEY`,
    `OPENAI_API_KEY` set, `CodexRunner.build_env()` lacks the token and `ANTHROPIC_API_KEY` but has
    `OPENAI_API_KEY` and `PATH`; `ClaudeCodeRunner.build_env()` lacks `OPENAI_API_KEY`; generic lacks all three;
    a fake-CLI run dumping `os.environ` confirms it. Fails on old code.

- [ ] Step 9: Antigravity out of the orchestrator (REQ-8)
  - Remove `antigravity` and `agy` from `RUNNER_MAP` (the class stays exported for `along run antigravity`).
  - `orchestrator.ORCHESTRATOR_RUNTIMES = ("claude", "claude-code", "codex", "opencode", "generic")`;
    `CrossRuntimeOrchestrator.__init__` validates every role runtime (`ValueError` naming the role and allowed
    values); `commands/orchestrator.py` uses `choices=ORCHESTRATOR_RUNTIMES`; fix the `ops.py` usage text.
  - Change `test_load_from_json_config` to `opencode`; add `test_antigravity_rejected_as_orchestrator_runtime`
    and `get_runner("antigravity")` raises `ValueError`. Fail on old code.

- [ ] Step 10: Docs, full suite, regression proof, commit, wrap
  - `docs/topic--agent-run-protocol.md` (runner section): per-runtime argv, verified versions, fixture
    location, stdin brief, env allowlist and `env_passthrough`, process-tree kill, Antigravity only via
    `along run`. `docs/topic--cli-reference.md`: `along run` / `along orchestrate`. Check `write_policy` first;
    if `manual`, stop and ask.
  - Run `tests/test_runtime_adapters.py`, `tests/test_runtime_contracts.py`, `tests/test_orchestrator.py`, then
    the full suite via `python .along/scripts/test.py`: green.
  - Regression proof: `git stash push -- scripts/` (keeps tests and fixtures), run the new tests and record
    that each fails, `git stash pop`, rerun green; paste the summary into the session log.
  - `along sanitize`; `git diff --stat`; tick the acceptance criteria; commit via `/along-commit`;
    `along wrap runtime-adapters-invented-cli-contracts --summary "..." --no-decisions`.

## Out of scope

- Rewriting `AntigravityRunner` / `along run antigravity` beyond removing it from `RUNNER_MAP` and the orchestrator.
- claude `stream-json`, live streaming via `runner/stream.py`, cost budgets.
- Codex sandbox network access and Windows codex sandbox maturity (documented as limits only).
- Windows job objects (`taskkill /T /F` meets REQ-4); the daemon's own `terminate_pid`.

## Rules for the executing agent

- Tests stay hermetic: never call the real claude / codex / opencode from tests; use fake CLIs and fixtures.
  The only real model calls are the Step 1 captures, announced to the user first.
- Deviations within the ticket (a fixture schema that differs, opencode without stdin):
  `along plan revise runtime-adapters-invented-cli-contracts --plan-file <path> --reason "..."`, continue.
- A requirement that cannot be met: `along plan rework runtime-adapters-invented-cli-contracts --reason "..."`,
  stop, ask the user.
- File content only through file tools (no heredocs, no `python -c`); ASCII only; never hand-edit
  `.along/rules/**` or projections. Report `along` CLI errors verbatim.
