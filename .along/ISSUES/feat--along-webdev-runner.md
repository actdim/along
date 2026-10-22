---
protocol: along
protocol_version: "4.5.1"
slug: along-webdev-runner
type: feat
status: open
priority: medium
created: 2026-10-22
updated: 2026-10-22
agent: antigravity
tags: [webdev, browser, cft, playwright, cdp, runner]
blocked_by: []
related: [feat--along-storage-providers, feat--along-report-engine]
---

# Self-Contained WebDev and Browser Execution Substrate

## Goal
Implement a provider-agnostic, self-contained web development, browser execution, and test automation substrate (`along-webdev`). The runner provisions a dedicated Portable Chrome for Testing (CfT) instance with zero external host setup, executes full Playwright scripts or declarative YAML scenarios in a single pass (avoiding slow and fragile micro-CLI roundtrips), captures real-time CDP runtime diagnostics (console errors, network failures), and emits structured execution payloads for direct consumption by the `along-report-engine`.

## Problem Statement
Current browser automation in agent runtimes is fragmented:
- Claude Code, OpenAI Codex, Antigravity, and OpenCode each have disparate, proprietary, or missing browser tools, especially in headless or Linux environments.
- Attempting to drive browsers via atomic CLI granules (e.g. issuing separate commands for click, fill, goto) causes excessive LLM token overhead, high latency, context clutter, and cannot be committed as reproducible CI tests.
- When frontend tests fail, standard test runners report selector timeouts without detailing what failed inside the browser runtime (uncaught JS errors, React hydration mismatches, failed 500 API responses).
- Browser processes easily orphan in headless environments, leaking memory and locking ephemeral user profile directories.

## Architecture & Interfaces

### 1. Portable Chrome for Testing (CfT) Bootstrap (`scripts/alongkit/webdev/cft.py`)
- Automated, zero-config provisioning:
  - Checks global user runtime cache: `~/.along/runtimes/cft/<version>/`.
  - If missing, downloads official standalone Chrome for Testing zip archive from Google Storage API using standard Python `urllib.request` and unpacks it via `zipfile`.
  - No Node.js, npm, pip, or venv required on the host for the browser bootstrap.
- Platform support:
  - Windows: `chrome-win64`
  - Linux: `chrome-linux64`
  - macOS: `chrome-mac-x64` / `chrome-mac-arm64`
- Process isolation and safety:
  - Launches with `--remote-debugging-port=0` (ephemeral port parsed from `DevToolsActivePort`).
  - Strict profile isolation: `--user-data-dir=%TEMP%/along-cft-session-<uuid>`, purged on exit.
  - Process group / Job Object binding ensuring zero zombie processes on abort or timeout.

### 2. Script-Driven Execution Model
Instead of sequential micro-CLI commands, `along-webdev` executes whole test scripts or scenarios in one local run:
- **Playwright Test Runner**:
  - Connects to the running CfT instance via `chromium.connectOverCDP(wsEndpoint)`.
  - Executes project tests (TypeScript/JavaScript via Node runner or Python Playwright).
  - Benefits from native auto-waiting, resilient locators, and trace capture.
- **Declarative YAML Scenario Runner**:
  - For lightweight agent-authored verification flows without writing boilerplate code:
    ```yaml
    scenario: "User Authentication Flow"
    url: "http://localhost:5173"
    steps:
      - action: navigate
        url: "/login"
      - action: fill
        selector: "input[type='email']"
        value: "admin@example.com"
      - action: click
        selector: "button[type='submit']"
      - action: assert_visible
        selector: ".dashboard-header"
      - action: screenshot
        label: "Authenticated Dashboard"
    ```

### 3. Real-Time CDP Diagnostics Harvester
- While the script executes, a background listener hooks into the Chrome DevTools Protocol session:
  - **Console Domain**: Captures all `Runtime.consoleAPICalled` and `Runtime.exceptionThrown` events.
  - **Network Domain**: Intercepts `Network.responseReceived` to identify all failed requests (HTTP 4xx/5xx) with URLs, status codes, and error bodies.
- When an assertion fails, the diagnostics harvester includes this runtime context in the final error report, allowing agents to immediately see the underlying root cause.

### 4. Output Contract for Along Report Engine
- On scenario completion, generates:
  - Step screenshots in optimized format (WebP/compressed PNG).
  - `run-result.json` matching the `ReportPayload` contract of `feat--along-report-engine`.
  - Optional publication trigger: `--publish <sharepoint|s3|local>`.

### 5. CLI Interface
```bash
# Provision or inspect Portable CfT status:
along webdev bootstrap [--status]

# Run a Playwright test script against dev server:
along webdev run tests/e2e/checkout.spec.ts --url http://localhost:5173 --issue feat--checkout

# Run a declarative YAML scenario and publish report to SharePoint:
along webdev run scenarios/login.yaml --issue feat--auth --publish sharepoint

# Quick visual proof capture of a running web route:
along webdev shot --url http://localhost:5173/dashboard --out .along/artifacts/dash.webp --issue feat--dash
```

## Acceptance Criteria
- [ ] Portable CfT downloader and version resolver implemented in pure Python (`scripts/alongkit/webdev/cft.py`).
- [ ] Browser process launcher with ephemeral ports, temporary user data directory, and clean teardown.
- [ ] Playwright CDP bridge and execution runner implemented.
- [ ] Declarative YAML scenario parser and runner implemented.
- [ ] CDP diagnostics listener capturing console errors and HTTP 4xx/5xx network failures.
- [ ] Step screenshot capture with WebP/PNG compression.
- [ ] Structured `run-result.json` output conforming to `feat--along-report-engine` schema.
- [ ] CLI command `along webdev` implemented in `scripts/along_webdev.py` and routed via `along_exec.py`.
- [ ] Hermetic tests covering bootstrap logic, scenario parsing, and teardown.
