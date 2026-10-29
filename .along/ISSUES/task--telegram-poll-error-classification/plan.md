# Living Plan: telegram-poll-error-classification

## Revision 1 (2026-10-29T11:52:35Z, ExitPlanMode)

# Task: daemon polling error classification (`task--telegram-poll-error-classification`, parent `feat--agent-execution-gate-telegram`)

Execution Mode: Direct (one module `scripts/alongkit/daemon.py`, its tests, one doc section)

## Context
The runner daemon now backs off exponentially on every poll error except a rejected token. That is
right for transient errors and wrong for HTTP 409 (another `getUpdates` consumer or a webhook holds the
bot token): the daemon then looks alive but never receives a command. The parent feature's acceptance
criterion asks for 409 to be reported instead of an endless backoff. Standard practice: classify
errors first, retry transient ones with jittered exponential backoff, honor the server's `retry_after`
for 429, and fail fast with a clear report on permanent ones; 409 gets a bounded window because a
short burst is normal after a fast restart.

## Changes - `scripts/alongkit/daemon.py`
1. **Error types.** Next to `TelegramAuthError` add `TelegramConflictError(RuntimeError)` and
   `TelegramRateLimitError(RuntimeError)` with a `retry_after: Optional[float]`.
   `TelegramClient.get_updates`: `HTTPError` 409 -> `TelegramConflictError`; 429 -> read the error body
   JSON `parameters.retry_after` (ignore parse failures) -> `TelegramRateLimitError`. Messages carry the
   status only, never the URL (it holds the token).
2. **Jittered backoff.** Helper `_backoff_delay(failures) -> float`: `d = min(poll_interval * 2**(failures-1),
   MAX_POLL_BACKOFF_SECONDS)`, returns `d / 2 + random.uniform(0, d / 2)` (equal jitter, so the delay
   stays within `[d/2, d]`).
3. **Run loop.**
   - Transient (`URLError`, `OSError`, `ValueError`, `RuntimeError`, `TimeoutError`, other HTTP): as now,
     but sleep `_backoff_delay(failures)`.
   - 429: sleep `retry_after` when present, else `_backoff_delay(failures)`; counts as a failure.
   - 409: remember `conflict_since = time.monotonic()` on the first one; while
     `time.monotonic() - conflict_since < CONFLICT_WINDOW_SECONDS` (60, new constant; overridable via
     `daemon.conflict_window` / `ALONG_DAEMON_CONFLICT_WINDOW` like `max_command_age`) back off as above;
     past it, log ERROR, `_broadcast_telegram("Runner daemon stopped: another consumer uses this bot token
     (another daemon or a webhook). Stop the other consumer or delete the webhook, then restart.")`
     (outbound `sendMessage` works during an inbound conflict), and exit with `EXIT_CONFIG` (78).
   - A successful poll resets `failures` and `conflict_since`.
   - Remove the old "409 in str(poll_exc)" hint.

## Tests - `tests/test_daemon.py` (each checked to fail on the old code)
- Jitter: with `random.uniform` patched to return its upper bound, three transient errors sleep
  `[5, 10, 20]`; with it patched to the lower bound, `[2.5, 5, 10]`; after a successful poll the next
  error sleeps 5 again. (Replaces the exact-value assertion in
  `test_poll_errors_back_off_and_a_bad_token_exits_78`, which keeps its 401 -> 78 part.)
- 429: `TelegramRateLimitError(retry_after=7)` -> sleep 7.
- 409 transient: two conflicts within the window, then updates -> the update is processed, `run()` keeps
  going until stopped, exit 0.
- 409 persistent: `time.monotonic` patched to advance past the window -> `run()` returns 78 and every
  allowed chat received the conflict message.
- Client mapping: `get_updates` with `urlopen` raising `HTTPError` 409 / 429 (body
  `{"ok":false,"parameters":{"retry_after":7}}`) raises the matching error, and its message has no token.

## Docs and bookkeeping
- `docs/topic--autonomous-environment.md`, runner daemon section: error classes (transient backoff with
  jitter, 429 `retry_after`, 409 window then exit 78 with a chat message, 401/404 exit 78).
- Tick the parent's AC ("Inbound updates are received by a single daemon per bot token via long polling;
  an HTTP 409 ...") in `feat--agent-execution-gate-telegram`; the parent stays open.
- Full suite (`python .along/scripts/test.py -q`), `along sanitize`, `/along-commit`,
  `along wrap telegram-poll-error-classification --no-decisions` (closes the task only).

## Revision 2 (2026-10-29T12:14:20Z, plan approve --plan-file)

# Living Plan: task--telegram-poll-error-classification

Execution Mode: Direct (one module `scripts/alongkit/daemon.py`, its tests, one doc section)

## Context

Part of `feat--agent-execution-gate-telegram` (its acceptance criterion: an HTTP 409 from `getUpdates` is
reported as "another consumer uses this bot token" instead of an endless backoff). Since
`bug--runner-daemon-lifecycle-safety`, `RunnerDaemon.run` backs off exponentially (capped at 300 s) on
every poll error except a rejected token (401/404 -> `TelegramAuthError` -> exit 78). Standard practice is
to classify errors first: retry transient ones with jittered exponential backoff, honor the server's
`retry_after` for 429, and fail fast with a clear report on permanent ones. 409 is permanent while another
receiver holds the token (Telegram allows one `getUpdates` consumer or one webhook per bot), but a short
burst is normal after a fast restart while the previous long poll (up to 20 s) is still open, so it gets a
bounded window.

Facts the steps rely on (verified 2026-10-29):

- `scripts/alongkit/daemon.py`: constants `MAX_POLL_BACKOFF_SECONDS = 300.0`, `EXIT_CONFIG = 78`,
  `DEFAULT_MAX_COMMAND_AGE`; `class TelegramAuthError(RuntimeError)`; `TelegramClient.get_updates` maps
  `urllib.error.HTTPError` 401/404 to `TelegramAuthError` and every other status to
  `RuntimeError("getUpdates HTTP <code>")` (the URL holds the token and is never reported).
- `RunnerDaemon.run`: `failures` counter reset on a successful poll; the generic `except` computes
  `min(poll_interval * 2 ** (failures - 1), MAX_POLL_BACKOFF_SECONDS)`, logs a "409" hint found by
  substring, and waits with `self._sleep(delay)` (an `Event.wait`, interruptible by stop).
- `RunnerDaemon._broadcast_telegram(text)` sends to every allowed chat; outbound `sendMessage` works during
  an inbound 409.
- `resolve_daemon_config` reads `daemon.*` keys from `.along/config.json` and `ALONG_DAEMON_*` env
  overrides (pattern: `max_command_age` / `ALONG_DAEMON_MAX_COMMAND_AGE`).
- Tests: `tests/test_daemon.py`, class `TestDaemonLifecycleSafety`, helper `SequencedTelegramClient`
  (raises queued exceptions, calls queued callables, `idle` hook) and `_daemon(...)` factory;
  `test_poll_errors_back_off_and_a_bad_token_exits_78` asserts exact sleeps `[5, 10, 20]`.

## Steps

- [x] Step 1: Classify Bot API errors in the client (REQ-2, REQ-3, REQ-4)
  - Add `TelegramConflictError(RuntimeError)` and `TelegramRateLimitError(RuntimeError)` (attribute
    `retry_after: Optional[float]`) next to `TelegramAuthError`.
  - `TelegramClient.get_updates`: HTTP 409 -> `TelegramConflictError("getUpdates HTTP 409: another consumer
    uses this bot token (another daemon or a webhook)")`; HTTP 429 -> parse the error body JSON
    `parameters.retry_after` (ignore parse errors) -> `TelegramRateLimitError`. Messages carry the status
    only; raise `from None` so the URL never reaches a traceback or log.
  - Export the new names in `__all__`.
  - Tests: `urlopen` patched to raise `HTTPError(url, 409, ...)` -> `TelegramConflictError`; 429 with body
    `{"ok":false,"parameters":{"retry_after":7}}` -> `TelegramRateLimitError` with `retry_after == 7`; no
    message contains the bot token.

- [x] Step 2: Jittered backoff and 429 handling in the run loop (REQ-1, REQ-2)
  - Helper `RunnerDaemon._backoff_delay(failures) -> float`: `d = min(poll_interval * 2 ** (failures - 1),
    MAX_POLL_BACKOFF_SECONDS)`; return `d / 2 + random.uniform(0, d / 2)` (equal jitter, within `[d/2, d]`).
  - Transient errors (`URLError`, `OSError`, `ValueError`, other `RuntimeError`, `TimeoutError`): sleep
    `_backoff_delay(failures)`. Remove the substring "409" hint.
  - `TelegramRateLimitError`: increment `failures`; sleep `retry_after` when present, else the backoff.
  - Tests: with `random.uniform` patched to return its upper bound, three transient errors sleep
    `[5, 10, 20]`; with the lower bound `[2.5, 5, 10]`; after a successful poll the next error sleeps 5
    again (update the exact-value assertion in `test_poll_errors_back_off_and_a_bad_token_exits_78`, keep
    its 401 -> 78 part); a 429 with `retry_after=7` sleeps 7.

- [x] Step 3: Bounded 409 conflict window (REQ-3)
  - New `DEFAULT_CONFLICT_WINDOW = 60.0`; config `daemon.conflict_window` and env
    `ALONG_DAEMON_CONFLICT_WINDOW` (same pattern as `max_command_age`); `RunnerDaemon(conflict_window=...)`.
  - On `TelegramConflictError`: set `conflict_since = time.monotonic()` if unset; while
    `time.monotonic() - conflict_since < conflict_window`, count a failure and back off; past the window,
    log ERROR, `_broadcast_telegram("Runner daemon stopped: another consumer uses this bot token (another
    daemon or a webhook). Stop the other consumer or delete the webhook, then restart.")`, set
    `exit_code = EXIT_CONFIG` and leave the loop. A successful poll resets `conflict_since`.
  - Tests: two conflicts within the window, then an update -> the update is processed and `run()` exits 0
    when stopped; `time.monotonic` patched to advance past the window -> `run()` returns 78 and every
    allowed chat received the conflict message.

- [x] Step 4: Docs, parent criterion, closeout
  - `docs/topic--autonomous-environment.md`, "Runner daemon" section: transient errors back off with jitter
    up to 300 s; 429 honors `retry_after`; 409 is retried for `conflict_window` (default 60 s), then the
    daemon tells the allowed chats and exits 78; 401/404 exit 78; `RestartPreventExitStatus=78`.
  - Tick the parent's criterion "Inbound updates are received by a single daemon per bot token via long
    polling; an HTTP 409 ..." in `feat--agent-execution-gate-telegram`; the parent stays open.
  - Confirm every new test fails on the code before this task (stash the source change, run, restore).
  - `python .along/scripts/test.py -q` green; `along sanitize`; commit via `/along-commit`;
    `along wrap telegram-poll-error-classification --summary "..." --no-decisions` (closes this task only).

## Out of scope

- Webhook delivery, callback queries and status cards: the rest of `feat--agent-execution-gate-telegram`.
- Sharing the Telegram client with feedback/diagnostics: `bug--autonomous-mvp-minor-defects`.

## Rules for the executing agent

- Deviations that still meet the ticket's requirements and acceptance criteria: resolve and record with
  `along plan revise telegram-poll-error-classification --plan-file <path> --reason "..."`.
- A requirement that cannot be met or must change: `along plan rework telegram-poll-error-classification
  --reason "..."`, stop, and ask the user.
