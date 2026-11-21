# Implementation Plan: Webdev Session Create Browser Helper & Improvements

## Execution Mode
Direct

## Context
When running `along webdev session start`, `daemon.py` calls `session.create_browser_session(...)`, which was missing from `scripts/alongkit/webdev/session.py`. Additionally, `daemon.py` teardown should cleanly close Playwright and browser process resources, and `pyproject.toml` should declare the `webdev` dependency group.

## Proposed Changes

### 1. `scripts/alongkit/webdev/session.py`
- Add `create_browser_session(repo_root=None, headed=False, allowed_origins=None)`:
  - Launches CfT browser via `browser.launch_cft(headless=not headed, repo_root=repo_root)`.
  - Connects Playwright via `browser.connect_playwright(bp)`.
  - Creates a new page instance.
  - Attaches `setup_origin_guard(page, allowed_origins)` if `allowed_origins` is provided.
  - Returns `(bp, (pw, page))`.

### 2. `scripts/alongkit/webdev/daemon.py`
- Enhance `BrowserDaemon.stop()` to safely close `page`, stop Playwright context `pw`, and terminate browser process `b_proc`.
- Read `defaults.origins` from `.along/webdev.json` if available and pass to `create_browser_session`.

### 3. `pyproject.toml`
- Add `webdev = ["playwright>=1.40.0"]` to `[project.optional-dependencies]`.
- Include `actdim-along[webdev]` in `all`.

### 4. Tests
- Add unit tests in `tests/test_webdev_subsystems.py` verifying `create_browser_session` structure and arguments.
- Run `python .along/scripts/test.py` to ensure all tests pass.

## Verification
- Run `python scripts/along_webdev.py session start --headed` to confirm browser launches and daemon responds on 127.0.0.1.
- Run `python scripts/along_webdev.py session stop` to verify clean teardown.
