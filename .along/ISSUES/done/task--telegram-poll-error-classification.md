---
protocol: along
protocol_version: "4.5.4"
slug: telegram-poll-error-classification
type: task
status: done
completed: 2026-10-29
priority: medium
created: 2026-10-29
updated: 2026-10-29
agent: claude-code
tags: [daemon, telegram, reliability]
blocked_by: []
related: [bug--runner-daemon-lifecycle-safety]
parent: feat--agent-execution-gate-telegram
plan_status: approved
---

# Daemon polling: jittered backoff, Telegram retry_after, bounded 409 conflict window

## Problem

Part of `feat--agent-execution-gate-telegram` (acceptance criterion: "an HTTP 409 Conflict from
`getUpdates` is reported as 'another consumer uses this bot token' instead of an endless backoff").

`RunnerDaemon.run` (`scripts/alongkit/daemon.py`, since `bug--runner-daemon-lifecycle-safety`) treats every
poll error except 401/404 the same: exponential backoff capped at 300 s, forever. That is right for
transient errors and wrong for the rest:

- HTTP 409 means another `getUpdates` consumer or a webhook holds the bot token (Telegram allows one
  receiver per bot). While it lasts the daemon looks alive but never receives a command. A short 409
  burst is normal after a fast restart, while the previous long poll (up to 20 s) is still open.
- HTTP 429 carries `parameters.retry_after`; the daemon ignores it and uses its own delay.
- The delay has no jitter, so restarted processes retry in lockstep.

## Requirements
- REQ-1: Transient poll errors (network, timeouts, HTTP 5xx, other non-auth statuses) MUST back off exponentially with jitter, capped at 300 s, and reset after a successful poll.
- REQ-2: HTTP 429 MUST wait the `retry_after` seconds Telegram returns (falling back to the backoff when absent).
- REQ-3: HTTP 409 MUST be retried with backoff only within a bounded window (default 60 s, longer than one long poll); a 409 that outlasts the window MUST stop the daemon with exit code 78 after logging and sending to the allowed chats "another consumer uses this bot token (another daemon or a webhook)".
- REQ-4: The bot token MUST NOT appear in any log line or message these paths produce.

## Acceptance Criteria
- [x] Three transient errors sleep within `[d/2, d]` of 5, 10, 20 s (jitter bounds) and the counter resets after success.
- [x] A 429 with `retry_after: 7` sleeps 7 s.
- [x] A 409 that clears inside the window lets polling continue; a 409 that persists past it exits 78 and the allowed chats receive the conflict message.
- [x] Regression tests cover each criterion and fail on the old code; `python .along/scripts/test.py` is green.
