---
protocol: along
protocol_version: "4.5.3"
slug: autonomous-mvp-minor-defects
type: bug
status: open
priority: low
created: 2026-10-23
updated: 2026-10-23
agent: claude-code
tags: [cleanup, packaging, daemon, docker]
blocked_by: []
related: [debt--along-core-extras-split, feat--vps-runner-daemon, feat--isolated-environment-docker, feat--cross-runtime-handoff-entities]
---

# Minor defects from the autonomous MVP review

## Problem

Low-risk leftovers from the review of commits 49894bf..e4e91ee.

- `pyproject.toml` extra `[telemetry]` installs `opentelemetry-api` / `opentelemetry-sdk`, but no
  code imports them: `alongkit/telemetry/otlp.py` is a stdlib OTLP serializer. The README and ADR
  `ADR-2026-10-23--along-core-and-modular-extras` describe it as an OpenTelemetry integration.
- `daemon.TelegramClient` and `resolve_daemon_config` duplicate the config/env merge and
  `sendMessage` code in `scripts/along_feedback.py` and `alongkit/diagnostics.py`.
- `along daemon --port` is a placeholder flag that does nothing.
- `environment.py` / `commands/env.py`: unused `DEFAULT_EGRESS_ALLOWLIST`, `DEFAULT_VOLUMES`,
  imports and parameters; an unused `build_parser()`; raw `subprocess.run` instead of
  `proc.run_capture`; `get_container_status` reads a paused container as running.
- `handoff.create_question` auto-ids as `q-{count+1}`, which reuses an id after a deletion.
- `hooks/escalation.py` lists `TimeoutError` twice; phases `implementation` / `review` used in
  gates are not in `session.SESSION_PHASES`; `along brief` exits 1 on usage errors (CLI rule: 2).

## Requirements
- REQ-1: The `[telemetry]` extra MUST either be removed or list only packages the code imports, and the README/ADR wording MUST match.
- REQ-2: Telegram config resolution and sending MUST live in one alongkit helper used by the daemon and feedback.
- REQ-3: Placeholder flags and dead code listed above MUST be removed.
- REQ-4: Question ids MUST be unique even after deletions.
- REQ-5: Usage errors in `along brief` MUST exit 2; gate phases MUST be declared in `SESSION_PHASES`.

## Acceptance Criteria
- [ ] `pip install actdim-along[telemetry]` installs nothing the code does not use.
- [ ] One Telegram helper; daemon and feedback tests pass through it.
- [ ] `along daemon --help` lists no placeholder flags.
- [ ] Regression tests where behavior changes; `python .along/scripts/test.py` is green.
