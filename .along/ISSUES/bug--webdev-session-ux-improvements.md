---
protocol: along
protocol_version: "4.9.1"
slug: webdev-session-ux-improvements
type: bug
status: in-progress
priority: high
created: 2026-11-21
updated: 2026-11-21
agent: antigravity
tags: [webdev, ux, cli]
blocked_by: []
related: []
plan_status: approved
---

# Fix dual browser window, Ctrl+C traceback, and CMD step argument parsing

Interactive session execution has 3 usability issues:
1. Two browser windows/tabs open simultaneously upon start: Chrome opens an initial tab, and Playwright opens a second blank tab.
2. The session server runs indefinitely as intended, but exiting via Ctrl+C produces an ugly KeyboardInterrupt traceback in bootstrap re-exec and daemon worker.
3. Passing JSON steps from Windows Command Prompt (cmd.exe) fails with unrecognized arguments because cmd.exe does not treat single quotes as string delimiters.

## Requirements
- REQ-1: `create_browser_session` MUST reuse the existing page in `browser_instance.contexts[0].pages` if present, opening a new page only when none exist.
- REQ-2: `bootstrap.py` and `alongkit/webdev/daemon.py` MUST catch `KeyboardInterrupt` gracefully and exit with clean console messages without traceback.
- REQ-3: `along_webdev.py` and `daemon.py` MUST accept step arguments flexibly, supporting unquoted/single-quoted JSON cleanup, `@file.json` references, and `--goto <url>` convenience shortcut flags.

## Acceptance Criteria
- [x] Only one browser window/tab is opened when starting a headed session.
- [x] Ctrl+C during `session start` or `session _worker` cleanly shuts down without unhandled Python stack traces.
- [x] Step execution accepts JSON with single quotes, `@file.json`, and direct `--goto` parameters.
- [x] Automated tests pass in test_webdev_interactive.py and test_webdev_playwright.py.
