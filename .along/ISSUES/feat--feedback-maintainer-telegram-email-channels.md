---
protocol: along
protocol_version: "4.8.1"
slug: feedback-maintainer-telegram-email-channels
type: feat
status: open
priority: low
created: 2026-11-11
updated: 2026-11-11
agent: claude-code
tags: [feedback, telegram, email]
blocked_by: []
related: [feat--feedback-github-pr-transport]
---

# Feedback maintainer channels: fixed Telegram bot and email

Deferred: do not implement until the maintainer provides the bot and channel details.

## Problem

The target set of feedback channels is: GitHub PR (see `feat--feedback-github-pr-transport`, via `gh` or the website), a Telegram bot, and email. Today the Telegram transport in `scripts/along_feedback.py` sends to whatever bot/chat the user configures in `~/.along/config.json` or env vars, so an ordinary user has nowhere to send feedback to. The maintainer will create a dedicated Along feedback Telegram bot and channel and provide its identifiers; feedback must then go to that specific channel out of the box.

## Open questions
- How to ship a default bot without exposing a token that allows abuse (send-only bot scoped to one channel; rate limiting; accept that the token is public, or use a deep link `t.me/<bot>?start=...` that the user sends themselves).
- Email: `mailto:` link with pre-filled subject/body (opens the user's mail client, no SMTP credentials) vs. SMTP send. Default: `mailto:`.
- Where the maintainer-provided identifiers live (built-in defaults in `alongkit`, overridable by config/env).

## Requirements
- REQ-1: The Telegram transport MUST target the maintainer's Along feedback channel by default once its identifiers are provided, while config/env overrides keep working.
- REQ-2: An `email` channel MUST be available, defaulting to a pre-filled `mailto:` link to the maintainer's address.
- REQ-3: Both channels MUST reuse the existing redaction and MUST NOT dispatch without the user's explicit confirmation.

## Acceptance Criteria
- [ ] Maintainer provides bot username/ID, channel ID and email address
- [ ] Telegram default target and `email` channel implemented in `scripts/along_feedback.py`
- [ ] `skills/along-feedback/SKILL.md` lists GitHub PR, Telegram and email
- [ ] Automated tests passing
