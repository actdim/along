---
protocol: along
protocol_version: "4.9.0"
slug: webdev-session-create-browser-helper
type: bug
status: in-progress
priority: high
created: 2026-11-21
updated: 2026-11-21
agent: antigravity
tags: [webdev, browser, bug]
blocked_by: []
related: [feat--along-webdev-runner]
verify: {tests: required, scope: '', reason: '', tracked_by: '', checks: []}
plan_status: approved
---

# Webdev session daemon missing create_browser_session helper

## Problem
When starting an interactive browser session via `along webdev session start`, `alongkit.webdev.daemon` calls `session.create_browser_session(self.repo_root, headed=self.headed)`. However, `scripts/alongkit/webdev/session.py` does not define `create_browser_session`, causing an `AttributeError: module 'alongkit.webdev.session' has no attribute 'create_browser_session'` during non-hermetic execution.

## Requirements
- REQ-1: `alongkit.webdev.session` MUST define `create_browser_session(repo_root=None, headed=False, allowed_origins=None)` returning a tuple of `(BrowserProcess, (PlaywrightInstance, Page))` matching `daemon.py` expectations.
- REQ-2: `alongkit.webdev.session.create_browser_session` MUST attach origin guard if `allowed_origins` is provided.
- REQ-3: Unit tests in `tests/test_webdev_subsystems.py` MUST verify `session.create_browser_session` interface and integration.

## Acceptance Criteria
- [x] `create_browser_session` helper implemented in `scripts/alongkit/webdev/session.py`
- [x] `along webdev session start` initializes browser process and page without AttributeError
- [x] Automated tests pass cleanly in `test_along_webdev.py` and `test_webdev_subsystems.py`
