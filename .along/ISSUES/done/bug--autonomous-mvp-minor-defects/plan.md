# Living Plan: autonomous-mvp-minor-defects

## Revision 2 (2026-10-29T23:22:00Z, plan revise: post-prerequisite re-check)
- Prerequisites verified done: autonomous-container-build-and-firewall, autonomous-gate-residual-holes, telegram-poll-error-classification.
- TimeoutError duplicate already removed from hooks/escalation.py by residual-holes.
- DEFAULT_EGRESS_ALLOWLIST in environment.py is retained as parity source-of-truth for test_docker_scripts.py.
- New TelegramConflictError and TelegramRateLimitError in daemon.py move to alongkit/telegram.py alongside TelegramClient and re-exported.

## Revision 1 (2026-10-29T12:14:24Z, plan approve --plan-file)

# Living Plan: bug--autonomous-mvp-minor-defects

Execution Mode: Role-Based (about 14 files across packaging, daemon / feedback, env, handoff and hooks; each step is small and reviewable on its own)

## Context

Low-risk leftovers from the review of commits 49894bf..e4e91ee. Three other tickets touch the same files and
run BEFORE this one:

- `bug--autonomous-container-build-and-firewall` rewrites YAML generation and docker error handling in
  `environment.py` / `commands/env.py`.
- `bug--autonomous-gate-residual-holes` edits `hooks/escalation.py` (its Step 4 removes the duplicate
  `TimeoutError`) and the phase check in `predicates.check_mutation_authorization`.
- `task--telegram-poll-error-classification` adds `TelegramConflictError` / `TelegramRateLimitError` to
  `daemon.TelegramClient`; moving the Telegram code here must carry them along.

Facts the steps rely on (verified 2026-10-29):

- `pyproject.toml`: extra `telemetry` lists `opentelemetry-api` and `opentelemetry-sdk`;
  `all = ["actdim-along[dash,telemetry]"]`. Every file in `scripts/alongkit/telemetry/*.py` imports only the
  stdlib and relative modules (`otlp.py` uses `urllib` and `json`).
- `[telemetry]` is described as an OpenTelemetry extra in README.md (lines 36-37, 145), `.along/VISION.md`
  (lines 48-49, 55) and ADR `along-core-and-modular-extras` (Decision item 2). ADRs are not rewritten; the
  precedent for superseding is `ADR-2026-08-26--code-graph-mcp-and-hybrid-kb-search.md` (`status: superseded`,
  `superseded_by:`; the newer ADR has `supersedes: [..]`). `along decision create` has no supersede flag.
- `daemon.py`: `TelegramAuthError`, `TelegramClient` (`get_updates`; `send_message` returns bool, truncates to
  4000); `resolve_daemon_config` precedence: `~/.along/config.json` `transports.telegram` < repo
  `.along/config.json` (also holds the `daemon` section) < env `TELEGRAM_BOT_TOKEN` or
  `ALONG_TELEGRAM_BOT_TOKEN` (`TELEGRAM_*` first); chat ids unioned global, local, env (comma-separated);
  unreadable files ignored. `tests/test_daemon.py` subclasses `daemon.TelegramClient`.
- `diagnostics.ConfigManager.load_config` deep-merges `GLOBAL_CONFIG_FILE` (module constant, overridden by
  `test_feedback`) with the repo `.along/config.json`; env only `ALONG_TELEGRAM_*`, and setting one also sets
  `enabled=True`; with no config files it mutates the nested dicts of `DEFAULT_CONFIG` (shallow `dict(...)`).
- `along_feedback.TelegramTransport.send` repeats the `sendMessage` POST and treats HTTP 200 as success; the
  `test_04` mock `read()` returns a MagicMock.
- The container `secrets.env` and `docs/topic--autonomous-environment.md` use unprefixed `TELEGRAM_BOT_TOKEN` /
  `TELEGRAM_CHAT_ID`.
- `tests/test_alongkit.py::TestNoDuplicateHelpers` rejects a module-level name defined in two engines
  (`scripts/*.py`, `dashboard/`, `tests/`) and any engine redefining a name from `scripts/alongkit/`: new
  helpers go in the package only, and tests must not define the same names.
- `--port` placeholder: `commands/daemon.py` (`build_parser` `start --port`, the custom help line,
  `port=parsed.port`); `daemon.start_daemon(port=..)` forwarding `--port`; `RunnerDaemon.__init__(port)` /
  `self.port` and the state key `"port"` in `run()`; three `"port"` keys in `get_daemon_status`; `"port": None`
  in `resolve_daemon_config`. No docs mention it. `check_unknown_args` exits 2 on extra args.
- `environment.py`: unused `DEFAULT_EGRESS_ALLOWLIST`, `DEFAULT_VOLUMES`, `import json`, `Tuple`, the `repo`
  import and the `env_dir` parameter of `generate_compose_yaml`; raw `subprocess.run` in
  `get_docker_compose_cmd`, `get_container_status`, `env_up`, `env_down`, `env_update`; `get_container_status`
  maps any status containing "up" to running, so "Up 5m (Paused)" reads as running.
  `commands/env.py::build_parser` is never called.
- `handoff.create_question` auto-ids as `q-{len(*.md)+1}`: after a deletion, or next to an explicit `q-3`, it
  collides and `write_text` overwrites a question. `tests/test_handoff_entities.py` expects the first auto id
  `q-1`.
- `hooks/escalation.py` lists `TimeoutError` again after the dedicated `except TimeoutError`.
- `session.SESSION_PHASES = ("inquiry", "planning", "execution")`, enforced by `set_session_phase` /
  `update_state`; `"implementation"` / `"review"` appear only in `hooks/predicates.py` (from a8ea884) and
  nothing can set them (`orchestrator.py`'s "reviewer" is a run phase, not a session phase).
- `commands/brief.py`: a missing slug, a missing `--role` and an unsupported role `return 1`; `Optional` and
  `repo` imported but unused; unknown flags already exit 2 through argparse.

## Steps

- [x] Step 1: Re-verify every item after the prerequisite tickets landed (all REQs)
  - Confirm the three prerequisite tickets are done (`along issue show <key>`); if one is not, stop and tell
    the user.
  - Re-grep every fact above. Expected: the `TimeoutError` duplicate is gone (residual-holes Step 4; then drop
    it from Step 7); the `predicates.py` phase tuple may be rewritten (residual-holes Step 1; re-locate it);
    raw `subprocess.run`, YAML generation and `generate_compose_yaml(env_dir)` may be reworked (container
    ticket; keep only leftovers); the new poll error classes in `daemon.py` must move with `TelegramClient`.
  - Record the deltas: `along plan revise autonomous-mvp-minor-defects --plan-file <path> --reason "post-prerequisite re-check"`.

- [x] Step 2: Telemetry is stdlib Core; drop the `[telemetry]` extra (REQ-1)
  - `pyproject.toml`: delete the `telemetry` extra and its comment; `all = ["actdim-along[dash]"]` with the
    comment "kept as a stable alias" (pip / uv only warn on an unknown extra, so old commands keep working).
  - Wording in README (install block, extras list), `.along/VISION.md` (sections 2 and 3) and
    `docs/topic--agent-run-protocol.md`: telemetry (tracer, redactor, spool, OTLP/HTTP JSON exporter) is part
    of Core and uses only the stdlib.
  - ADR: `along decision create along-core-and-dash-extra --title ... --context ... --decision ...
    --consequences ...` restating items 1 and 3 of the old ADR unchanged; item 2: the only extra is `[dash]`,
    `[all]` is an alias, telemetry is stdlib Core. Front matter `supersedes: [along-core-and-modular-extras]`;
    the old ADR gets front matter `status: superseded`, `superseded_by: along-core-and-dash-extra` and its
    "- Status:" line updated (the precedent above). Then `along decision sync` and `along decision sync --check`.
    Superseding (not a README-only change) because an accepted ADR naming a `[telemetry]` extra would stay a
    binding constraint in CONSTRAINTS.md.
  - Test `test_extras_install_only_imported_packages` in `TestPackagingContract` (`tests/test_alongkit.py`):
    no `opentelemetry` in `pyproject.toml` and no `telemetry =` extra; every top-level import under
    `alongkit/telemetry/` is in `sys.stdlib_module_names`, `__future__` or relative; README and VISION do not
    contain `actdim-along[telemetry]`. Fails on old code.

- [x] Step 3: One Telegram helper `scripts/alongkit/telegram.py` (REQ-2)
  - Contents (stdlib plus `repo`): `API_BASE`; `MAX_MESSAGE_CHARS = 4000`;
    `TOKEN_ENV_VARS = ("TELEGRAM_BOT_TOKEN", "ALONG_TELEGRAM_BOT_TOKEN")` and `CHAT_ENV_VARS` in the same order;
    dataclass `TelegramSettings(bot_token, chat_ids, enabled)` with property `primary_chat_id` (the first id
    from the highest-precedence source that set any); pure `settings_from_sections(sections, environ)`
    (sections in rising precedence); `resolve_settings(repo_root=None, environ=None, global_config=None)`
    (global file, default `expanduser("~/.along/config.json")` at call time, then the repo config, then env;
    unreadable files ignored; `enabled` = the last section's flag OR any token / chat from env);
    `send_message(bot_token, chat_id, text, *, base_url, timeout=10) -> (ok, detail)` (truncates; success is
    HTTP 200 with JSON `ok: true`; the error detail gives the status or `URLError.reason`, never the token);
    `TelegramAuthError`, the poll-error classes and `TelegramClient` moved verbatim from `daemon.py`
    (`TelegramClient.send_message` returns `send_message(...)[0]`).
  - `daemon.py`: import those names from `.telegram` and keep them in `__all__` (tests and patches keep
    working); `resolve_daemon_config` takes `bot_token` / `chat_ids` from `telegram.resolve_settings` and still
    reads the `daemon` section and `ALONG_DAEMON_*` itself.
  - `diagnostics.ConfigManager.load_config`: start from `copy.deepcopy(DEFAULT_CONFIG)`; keep the file
    deep-merge for other keys; replace the `ALONG_TELEGRAM_*` block with
    `telegram.resolve_settings(repo_root, global_config=GLOBAL_CONFIG_FILE)` writing `bot_token`,
    `chat_id = primary_chat_id` and `enabled` into `transports.telegram`.
  - `along_feedback.TelegramTransport.send`: keep the summary builder, call `telegram.send_message`; messages
    "Successfully dispatched diagnostic summary to Telegram channel." / "Failed to send Telegram message:
    <detail>"; drop `urllib` from the engine if `WebhookTransport` no longer needs it.
  - Tests (new `tests/test_telegram.py`, no module-level names clashing with the package): precedence (global
    token A / chat 1 < local B / 2 < env `TELEGRAM_BOT_TOKEN=C`, `ALONG_TELEGRAM_CHAT_ID="3,4"` -> token C, ids
    `[1, 2, 3, 4]`, primary `"3"`); `ConfigManager.load_config` with only `TELEGRAM_BOT_TOKEN` /
    `TELEGRAM_CHAT_ID` (the container case) is enabled with the token (fails on old code); `load_config` with
    env and then without env and no files leaves the token empty the second time (fails on old code:
    `DEFAULT_CONFIG` mutation); `send_message` with `HTTPError(401)` returns False and the detail lacks the
    token; `api.telegram.org` and `sendMessage` appear under `scripts/` only in `alongkit/telegram.py` (fails on
    old code). Update `tests/test_feedback.py::test_04` so the mock `read()` returns `b'{"ok": true}'`.

- [x] Step 4: Remove the `along daemon --port` placeholder (REQ-3)
  - Delete it from `build_parser`, the help line and the `start_daemon` call; the `port` parameter and
    forwarding in `start_daemon`; the `RunnerDaemon` parameter, `self.port` and the state key; the three
    `get_daemon_status` keys; `"port"` in `resolve_daemon_config`. Old `daemon.json` files holding `port` stay
    harmless.
  - Tests (`tests/test_daemon.py`, fail on old code): `handle_daemon_command(root, ["--help"])` stdout and
    `build_parser()` help for `start` contain no `--port`; `handle_daemon_command(root, ["start", "--port", "1"])`
    raises `SystemExit(2)` (patch `daemon.start_daemon` so nothing starts).

- [x] Step 5: Dead code and docker calls in env (REQ-3)
  - Remove whatever Step 1 found still present: the two constants, unused imports, the unused `env_dir`
    parameter (and its call site), `commands/env.py::build_parser` and imports only it used.
  - Move every remaining docker call to `proc.run_capture`; `env_up/down/update` keep their result dicts with
    `res.stderr.strip()` as the error text.
  - `get_container_status`: `docker ps -a --filter name=^/<n>$ --format {{.State}}`; empty -> `not_created`;
    `exited` / `dead` -> `stopped`; other states (running, paused, created, restarting) passed through;
    non-zero return code -> `unknown`.
  - Tests (`tests/test_along_env.py`): `environment.shutil.which` patched to a fake path and
    `environment.proc.run_capture` to `Result(cmd, 0, "paused\n", "")` -> `"paused"`; also `"running"`,
    `"exited"` -> `stopped`, `""` -> `not_created` (old code returns `unknown`: fails); an AST check that
    `environment.py` makes no `subprocess.run` call (fails on old code).

- [x] Step 6: Question ids stay unique after deletions (REQ-4)
  - `handoff._next_question_id(q_dir)`: `n = max(highest numeric suffix of q-<n>.md, int in
    questions/.last-id) + 1`; write `.last-id` atomically through `textio`; return `q-<n>` (not a `.md` file, so
    `list_questions` ignores it; confirm). Used when `qid` is not given; the first id stays `q-1`.
  - Tests (`tests/test_handoff_entities.py`, fail on old code): three auto questions, delete `q-2.md`, create
    -> `q-4` and `q-3` unchanged; delete `q-4` (the max), create -> `q-5`; after an explicit `qid="q-7"` the
    next auto id is `q-8`.

- [x] Step 7: Escalation duplicate, session phases, `along brief` exit codes (REQ-3, REQ-5)
  - `hooks/escalation.py`: drop the second `TimeoutError` if still there.
  - Phases: add `session.EDIT_PHASES: tuple = ("execution",)` next to `SESSION_PHASES` and make the predicate
    check `phase in session.EDIT_PHASES` (nothing produces `implementation` / `review`); grep `scripts/`,
    `skills/`, `docs/` for phase literals.
  - Tests (`tests/test_autonomous_gate_profile.py`, standard profile): plan approved via `session.approve_plan`,
    then `phase: "review"` via `save_state` -> a source write is denied with `require-plan-approval` (fails on
    old code); `set(session.EDIT_PHASES) <= set(session.SESSION_PHASES)`.
  - `commands/brief.py`: return 2 for a missing slug, a missing `--role` and an unsupported role; remove the
    unused imports. Tests (`tests/test_handoff_entities.py`): `[slug]`, `["--role", "implementer"]`,
    `[slug, "--role", "bogus"]` each return 2 (fail on old code).

- [x] Step 8: Docs, full suite, old-code check, commit, wrap
  - `docs/topic--autonomous-environment.md` (daemon section: Telegram config precedence, env names, `--port`
    removed); `skills/along-feedback/SKILL.md` (`TELEGRAM_*` accepted); `docs/topic--cli-reference.md` if it
    lists `along brief` exit codes; then `along kb-sync` and `along sanitize`.
  - `python .along/scripts/test.py` on each touched test file, then the full suite: green.
  - Old-code check: stash the source changes only (keep tests), confirm each new test fails, `git stash pop`.
  - `git diff --stat`; commit via `/along-commit`;
    `along wrap autonomous-mvp-minor-defects --summary "..." --decisions along-core-and-dash-extra`.

## Out of scope

- A real OpenTelemetry SDK integration; OTLP export semantics.
- Firewall, Dockerfile and YAML escaping (container ticket); escalation routing and profile trust
  (residual-holes); poll backoff (poll-error task).
- Overwrite protection for an explicit `qid`; webhook transport changes; renaming the Telegram env vars.

## Rules for the executing agent

- Deviations within the ticket: `along plan revise autonomous-mvp-minor-defects --plan-file <path> --reason "..."`.
- A requirement that cannot be met (for example, a prerequisite reshaped the code so a REQ conflicts with it):
  `along plan rework autonomous-mvp-minor-defects --reason "..."`, stop, ask the user.
- Never edit `.along/rules/**`, projections or the body of an accepted ADR; ASCII only; file content through
  file tools only, never through a shell.
