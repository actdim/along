---
protocol: along
protocol_version: "4.5.1"
slug: along-webdev-runner
type: feat
status: in-progress
priority: medium
created: 2026-10-22
updated: 2026-11-21
agent: antigravity
tags: [webdev, browser, cft, playwright, cdp, runner, verification, provider-agnostic]
blocked_by: []
related: [feat--along-storage-providers, feat--along-report-engine, feat--automated-ui-screenshots-and-visual-verification]
plan_status: approved
milestone: v5.0.0-agent-run-protocol-and-observability
---

# Self-Contained WebDev and Browser Execution Substrate

## Goal
Implement a provider-agnostic, self-contained web development, browser execution, and test automation substrate (`along-webdev`). The runner provisions a dedicated Portable Chrome for Testing (CfT) instance with zero external host setup, executes full Playwright scripts or declarative YAML scenarios in a single pass (avoiding slow and fragile micro-CLI roundtrips), captures real-time CDP runtime diagnostics (console errors, network failures), and emits structured execution payloads for direct consumption by the `along-report-engine`.

Added 2026-11-14: the substrate must let ANY agent (Claude, Gemini, DeepSeek, Codex, OpenCode, Antigravity) run a complete manual-verification pass over UI tickets - start the app, sign in through a dev-only path, drive the UI at exact viewports and themes, assert on DOM geometry, console and network, keep screenshot evidence, and record a PASS / FAIL / NOT RUN table - without depending on a harness's built-in browser tools.

## Problem
Current browser automation in agent runtimes is fragmented:
- Claude Code, OpenAI Codex, Antigravity, and OpenCode each have disparate, proprietary, or missing browser tools, especially in headless or Linux environments.
- Attempting to drive browsers via atomic CLI granules (e.g. issuing separate commands for click, fill, goto) causes excessive LLM token overhead, high latency, context clutter, and cannot be committed as reproducible CI tests.
- When frontend tests fail, standard test runners report selector timeouts without detailing what failed inside the browser runtime (uncaught JS errors, React hydration mismatches, failed 500 API responses).
- Browser processes easily orphan in headless environments, leaking memory and locking ephemeral user profile directories.

Observed failure (2026-11-14, a downstream web app repository): plans executed by models without a browser tool (DeepSeek Flash, Gemini) skipped every browser verification step across 8 closed UI tickets. The pass was then done by hand with the Claude Desktop browser pane (JS eval, screenshots, network log, viewport emulation). Verification that only one harness can perform is verification that silently does not happen. In the same manual pass a coordinate-based click landed off-layout and opened a third-party (Google) sign-in page - coordinates are not a safe default targeting mode.

## Reference Workload
The manual pass this issue must make reproducible by any agent. Each item maps to a requirement below.

| # | Need | Concrete instance from the pass | REQ |
| :--- | :--- | :--- | :--- |
| 1 | App lifecycle | start frontend + backend via package scripts, wait for readiness, tell crashes from noisy warnings, stop afterwards; start a static file server on a second origin for a CORS check | REQ-1 |
| 2 | Session / auth | open a localhost dev-login page, click "Dev sign-in"; never type real passwords; never drift to third-party sign-in | REQ-2, REQ-3 |
| 3 | Viewports and themes | 375x812, 390x844, 900x800, 1440x900; prefers-color-scheme light/dark; app theme stored in localStorage/app settings that ignores the media query | REQ-4 |
| 4 | Interaction | click, type, Shift+Enter, Escape, upload generated files through `input[type=file]`, menus, bottom sheets, back/forward, reload | REQ-5 |
| 5 | Assertions | JS eval returning JSON: composer above the fixed footer, `elementFromPoint` to find what covers a button, horizontal overflow, textarea auto-grow height, aria attributes, audio element state, spy on `navigator.mediaSession.setPositionState`; console errors; network requests with status and body, auth headers redacted, noise filtered | REQ-6, REQ-7 |
| 6 | Evidence | full, element/region screenshots per viewport and theme, stable folder and names, linked from a results table, never committed by default | REQ-8 |
| 7 | Scripting | deterministic re-runnable scenario AND natural-language checklist compiled by an agent into steps; PASS/FAIL/NOT RUN table; failures become issues | REQ-9, REQ-10, REQ-11 |
| 8 | Limits | mobile virtual keyboard, OS media flyout, stopping a shared backend mid-test: NOT RUN with reason, or emulate (offline, throttle, route interception returning 500) | REQ-12 |
| 9 | Provider independence | same commands from the `along` CLI and from MCP; `.env` secrets never printed | REQ-13, REQ-14 |

## Gap Analysis (state on 2026-11-14)
What the original design below already covers: portable CfT bootstrap, process isolation and teardown of the BROWSER, a Playwright-over-CDP bridge, a YAML scenario format with `navigate / fill / click / assert_visible / screenshot`, console + 4xx/5xx network harvesting, step screenshots, a `run-result.json` for the report engine, and a CLI.

What is missing for the reference workload:
1. **No app lifecycle.** Nothing starts, probes, watches or stops the app's own dev servers or side helpers; only the browser is managed. `along-dev` (`.along/scripts/dev.py`) runs this repo's own dev stack in the foreground and has no readiness probe, no background mode and no stop.
2. **No interactive mode.** The design is batch-only. A verification pass is exploratory (look, then decide the next step); an agent needs a persistent browser session it can issue steps into and later save as a scenario. Batch-only pushes weak agents back to skipping the check.
3. **Targeting policy undefined.** CSS selectors only; no role/text/label locators, no rule that coordinate clicks are opt-in.
4. **No navigation guard.** Nothing stops a step from leaving the allowed origins (the Google sign-in drift).
5. **No dev-auth contract.** No declared dev-login step, no rule against typing real credentials, no handling of secrets from `.env`.
6. **No emulation.** No viewport/DPR/touch/user-agent, no `prefers-color-scheme` / reduced-motion, no storage seeding before page scripts run, no offline/throttle, no route interception.
7. **Thin step vocabulary.** No keys/chords, file upload with generated files, hover, select, history navigation, reload, waits on selector/network/function.
8. **Thin assertions.** Only `assert_visible`. No `eval` returning JSON, no geometry helpers, no init-script spies on browser APIs, no console/network assertions with noise filters, no response-body capture with redaction.
9. **Evidence handling.** `.along/artifacts/` is git-ignored in THIS repo, but `along init` does not add it in consumer repos and `check_untracked_exports` (`scripts/alongkit/repochecks.py`) does not cover it; no naming scheme; no element/region shots; no results-table linkage.
10. **No checklist layer.** No natural-language checklist format, no compile-to-steps contract, no PASS/FAIL/NOT RUN result model, no failure-to-issue path.
11. **No explicit limits model.** No NOT RUN status with a mandatory reason, no list of known-unverifiable surfaces.
12. **No MCP surface.** Along ships no MCP server of its own (`scripts/configure_mcp.py` only registers `code-review-graph`), so agents whose harness prefers tools over shell have no entry point.
13. **No protocol hook.** Nothing ties a UI issue's acceptance criteria to a browser run, so a plan's "verify in browser" step can still be skipped silently.

## Requirements

- REQ-1: **App lifecycle (`along webdev serve`)**
  - Services are declared per repository in `.along/webdev.yaml` (or `along.yaml` section `webdev:`), never in harness-specific launch configs. Each service names a command that runs a package script (`pnpm --filter web dev`, `npm run dev`, `uv run ...`), a `cwd`, optional `env` (values may reference `.env` keys by name), and a readiness probe: `http` (URL + expected status range + timeout), `log` (regex on stdout/stderr), or `port` (TCP open).
  - `serve up [<name>...]` starts services detached in a process group / Job Object, writes PID, port, log path and state to `.along/.session/webdev/services.json`, and returns only after every probe passes or a deadline expires (exit 1 with the last 40 log lines).
  - Crash vs noise: a service is `crashed` when its process exits or its probe fails after having passed; log lines matching configurable `noise:` regexes are counted but never fail a run; lines matching `fatal:` regexes fail it.
  - `serve status`, `serve logs <name> [--tail N] [--grep RE]`, `serve down [<name>...]` (tree kill with grace period, reusing `alongkit.proc.kill_process_tree`). Services left running at session end are reported by the stop gate, not silently killed.
  - Side helpers are ordinary services, plus a built-in `static` kind (`kind: static`, `root:`, `port:`) for a second-origin file server used in CORS checks.
  - Reuse: if a declared port already answers the probe, attach instead of starting a duplicate, and do not stop what Along did not start.

- REQ-2: **Navigation guard and targeting policy**
  - Every session has an origin allowlist (default: origins of declared services plus `about:blank`). A top-level navigation or popup to any other origin aborts the step as FAIL with reason `blocked-origin <origin>` and a screenshot; third-party sign-in hosts are never in the default allowlist.
  - Locators default to accessibility semantics: `role` + `name`, `label`, `text`, `placeholder`, `test_id`; CSS/XPath allowed explicitly. Coordinate actions require `at: {x, y}` plus `allow_coordinates: true` on the step and are reported as such in the result.
  - A locator that matches 0 or more than 1 element fails with the candidate list (role, name, bounding box), not a bare timeout.

- REQ-3: **Dev-auth contract**
  - A scenario or checklist may declare `auth:` as a named step sequence (e.g. open `/dev-login`, click role=button name="Dev sign-in", wait for URL `/app`). Its storage state (cookies, localStorage) is cached per session in `.along/.session/webdev/auth/<name>.json` (git-ignored) and reused across checks.
  - The runner refuses to `fill` a field of `type=password` unless the value comes from a declared test-credential source (project seed/fixture file or `.env` key listed under `webdev.test_credentials`), and only on an allowlisted origin.
  - Values pulled from `.env` are passed by reference (`${env:KEY}`); they are never echoed in step logs, results, console/network captures, or errors (masked as `***KEY***`).

- REQ-4: **Emulation**
  - Viewport: `width x height`, `device_scale_factor`, `is_mobile`, `has_touch`, optional user agent; named presets (`mobile-375x812`, `mobile-390x844`, `tablet-900x800`, `desktop-1440x900`) plus custom sizes. Set per scenario, per check, or as a matrix.
  - Media: `prefers-color-scheme` (light/dark), `prefers-reduced-motion`, `forced-colors`.
  - App state: `storage:` seeding of localStorage/sessionStorage/cookies applied before any page script runs (init script), so app-level theme settings that ignore the media query can be forced; plus `reload` after change.
  - Matrix runs: `matrix: {viewport: [...], theme: [...]}` expands one check into N runs with distinct evidence names.

- REQ-5: **Step vocabulary**
  - `goto`, `back`, `forward`, `reload`, `click`, `dblclick`, `hover`, `fill`, `type` (with delay), `press` (keys and chords: `Shift+Enter`, `Escape`, `Control+A`), `select`, `check`, `scroll_into_view`, `upload` (to `input[type=file]`, from repo paths or generated fixtures: `generate: {kind: png|jpg|txt|wav|bin, size_kb:, name:}` created in a temp dir), `wait_for` (locator state, URL, network idle, response matching URL/status, JS predicate), `sleep` (discouraged, capped).
  - Menus, popovers and bottom sheets are driven by the same locators; `press Escape` and click-outside are first-class steps.

- REQ-6: **Assertions and probes**
  - `eval`: runs a JS expression or async function in the page (or a frame), returns JSON-serialisable data, stored in the result; optional `expect:` with JSONPath-style comparisons (`==`, `<`, `>`, `contains`, `matches`).
  - Built-in geometry probes returning JSON: `box(locator)`, `above(a, b)` (bottom of a <= top of b), `covered_by(locator)` (elementFromPoint at the element center and corners, returns the topmost element description), `overflow_x()` (document scrollWidth > clientWidth plus offending elements), `in_viewport(locator)`.
  - Attribute and state assertions: `assert_visible`, `assert_hidden`, `assert_text`, `assert_attr` (aria-*, role, disabled), `assert_count`, `assert_url`, media element state (`paused`, `currentTime`, `src`, `readyState`).
  - Spies: `spy: {target: "navigator.mediaSession.setPositionState"}` installs an init-script wrapper that records calls (args, timestamp) into a page-global buffer; `spy_calls` reads it; works on functions defined before page scripts run.

- REQ-7: **Console and network capture**
  - Console messages and uncaught exceptions with level, text, source URL, line, timestamp; network requests with method, URL, status, timing, request/response headers and (opt-in, size-capped) bodies.
  - Redaction before anything is written or printed: `Authorization`, `Cookie`, `Set-Cookie`, `X-Api-Key` and configured headers; query params and JSON body keys matching configured patterns; any value equal to a `.env` secret.
  - Noise filters per repo (`webdev.noise.console`, `webdev.noise.network`: regexes, e.g. HMR, favicon 404, devtools hints), applied at assertion time; raw capture is still kept in the run folder.
  - Assertions: `assert_no_console_errors` (after filters), `assert_request` (URL/method matched, status range, body JSONPath), `assert_no_failed_requests`.

- REQ-8: **Evidence**
  - Screenshot kinds: viewport, full page, element (`of: locator`, with padding), region (`clip: {x, y, w, h}`); optional mask of locators (avatars, timestamps).
  - Location: `.along/artifacts/webdev/<issue-key>/<run-id>/` (run-id = UTC timestamp + short hash); names `<check-id>--<viewport>--<theme>--<step>.png`, stable across re-runs so diffs line up.
  - Never committed by default: `along init` / `along update` add `.along/artifacts/` and `.along/.session/` to `.gitignore`; `check_untracked_exports` is extended to `.along/artifacts/**`; committing evidence requires an explicit `--keep-evidence <path>` export that copies selected files to a tracked location the user chose.
  - Every run writes `results.md` (table) and `results.json` in the run folder; table rows link screenshots by relative path.

- REQ-9: **Deterministic scenario format**
  - YAML (primary) and JSON (same schema, `along webdev schema` prints the JSON Schema). A scenario has `meta` (issue key, title), `services` (REQ-1 names to bring up), `auth`, `defaults` (viewport, theme, storage, origin allowlist, noise), and `checks[]`; each check has `id`, `title`, optional `ac:` (acceptance-criterion reference in the issue), `matrix`, `steps[]`, and optional `not_run:` reason.
  - Code escape hatch: a check may point to a Playwright test (`.spec.ts` / Python) run against the same browser via `connectOverCDP`, its outcome folded into the same result table.
  - Re-runnable: `along webdev run <scenario> [--check ID ...] [--matrix viewport=mobile-375x812]`; exit 0 all PASS (NOT RUN allowed), 1 any FAIL, 2 usage/schema error.

- REQ-10: **Interactive session and natural-language checklists**
  - `along webdev session start|step|batch|save|stop`: a persistent browser (and optional services) behind a local daemon, so an agent can explore one step at a time; `batch` accepts a list of steps in one call (to keep roundtrips low); every executed step is appended to a transcript; `save --as <scenario.yaml>` turns the transcript into a deterministic scenario.
  - Checklist format: Markdown list of checks in plain language with ids (`- [ ] C3: on 375x812 the composer stays above the fixed footer after typing 5 lines`), optionally embedded in the issue under `## Browser Verification`.
  - `along webdev checklist compile <file|issue-key>` emits a scenario skeleton with one `check` per item (ids, titles, `ac:` links, matrix guesses) and `steps: []` marked TODO for the agent to fill; the agent fills steps (any provider), then `run`. A check whose steps are still empty is reported as NOT RUN `reason: not-compiled`, never as PASS.

- REQ-11: **Result model and failure follow-up**
  - Per check per matrix cell: status `PASS | FAIL | NOT RUN`, reason (mandatory for FAIL and NOT RUN), evidence links, captured eval values, filtered console/network excerpt, duration.
  - `results.md` table columns: Check, AC, Viewport, Theme, Status, Reason, Evidence.
  - `along webdev run ... --issue <key>` updates (replaces) a `## Browser Verification Results` section in the issue with the summary table and run-id; evidence links stay pointing at the git-ignored run folder.
  - Failures: `--file-failures` creates one `bug--<issue-slug>-<check-id>` issue per FAIL from a template (steps to reproduce = the check's steps, expected = assertion, actual = observed value, evidence paths, `related:` parent issue); without the flag, prints the ready-to-run `along issue create` commands.
  - The result JSON conforms to the `ReportPayload` contract of `feat--along-report-engine`.

- REQ-12: **Declared limits and emulation substitutes**
  - Known unverifiable surfaces are listed in docs and in `along webdev limits`: mobile virtual keyboard and its viewport resize, OS-level media flyout / lock-screen controls, native file pickers and OS dialogs, push notifications, real device sensors, cross-device behaviour. Checks touching them are NOT RUN with `reason: platform-limit:<name>` unless a substitute is declared.
  - Substitutes are explicit steps: `network: offline|online`, `throttle: {latency_ms, down_kbps, up_kbps}`, `route: {url: RE, fulfill: {status, body, headers}}` or `route: {abort: failed}` to simulate a server error instead of stopping a shared backend, `visual_viewport: {height}` resize to approximate a virtual keyboard, `spy` on `navigator.mediaSession` to verify what the OS flyout would receive. Results mark these checks `PASS (emulated: <how>)`.
  - Destructive actions on shared infrastructure (stopping a backend other sessions use) are never performed by the runner; only services the run itself started may be stopped mid-test.

- REQ-13: **Provider independence: CLI and MCP parity**
  - One engine (`scripts/alongkit/webdev/`) behind two thin fronts: `along webdev ...` (CLI, `--json` for machine output, stdout data / stderr logs per `rules/platforms/cli.md`) and an `along-webdev` MCP server (stdio) whose tools map 1:1 to the CLI verbs (`serve_up`, `serve_status`, `serve_down`, `session_start`, `step`, `batch`, `run`, `checklist_compile`, `screenshot`, `eval`, `console`, `network`, `session_stop`) with the same argument names and the same JSON results.
  - Registration via the existing installer path (`configure_mcp.py` / `alongkit.install`) for every provider whose MCP config contract is verified; others get the snippet.
  - Works headless on Linux CI and headed on desktops (`--headed`); no dependency on any harness's browser tools; returns screenshots as file paths (plus optional base64 for MCP clients that render images).

- REQ-14: **Protocol integration**
  - A plan for an issue tagged `ui` (or whose verify policy names `webdev`) must declare its browser checks (checklist or scenario path); `along wrap` refuses to close such an issue while its latest webdev result has FAIL or has checks never run, unless each NOT RUN carries a reason; `--force-reason` follows the usual bypass rules.
  - `along doctor` reports webdev readiness: CfT present/version, Playwright driver available, MCP server registered, declared services and probes valid.

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
- Added 2026-11-14: batch stays the default for committed scenarios; the interactive session of REQ-10 is the exploratory front that records into the same format.

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

### 6. Extended Scenario Example (added 2026-11-14)
Illustrative shape for REQ-1..REQ-12; field names are a proposal, fixed by `along webdev schema` at implementation time.

```yaml
meta: {issue: feat--chat-composer-layout, title: "Composer and player layout pass"}
services: [api, web, cors-static]
auth:
  dev:
    - {goto: "/dev-login"}
    - {click: {role: button, name: "Dev sign-in"}}
    - {wait_for: {url: "/app"}}
defaults:
  origins: ["http://localhost:5173", "http://localhost:8000", "http://localhost:8099"]
  storage: {localStorage: {"app.theme": "system"}}
checks:
  - id: C1
    title: Composer stays above the fixed footer while growing
    ac: AC-3
    matrix: {viewport: [mobile-375x812, mobile-390x844, desktop-1440x900], theme: [light, dark]}
    steps:
      - {use_auth: dev}
      - {goto: "/app/chat"}
      - {fill: {role: textbox, name: "Message"}, value: "one"}
      - {press: "Shift+Enter", repeat: 4}
      - {eval: "above('[data-testid=composer]', 'footer')", expect: {"$": true}}
      - {eval: "covered_by({role: 'button', name: 'Send'})", expect: {"$.self": true}}
      - {eval: "overflow_x()", expect: {"$.overflow": false}}
      - {screenshot: {of: {test_id: composer}}}
  - id: C2
    title: Upload error is shown when the server fails
    steps:
      - {route: {url: "/api/upload", fulfill: {status: 500}}}
      - {upload: {label: "Attach"}, generate: {kind: png, size_kb: 200, name: "a.png"}}
      - {assert_text: {role: alert}, contains: "failed"}
  - id: C3
    title: Media session position reaches the OS flyout
    not_run: "platform-limit:os-media-flyout"
```

### 7. Module Layout (proposal)
- `scripts/alongkit/webdev/cft.py` - browser provisioning (existing design).
- `scripts/alongkit/webdev/services.py` - REQ-1 lifecycle, probes, crash/noise classification.
- `scripts/alongkit/webdev/session.py` - browser session daemon, origin guard, emulation, transcript.
- `scripts/alongkit/webdev/steps.py`, `probes.py` (geometry/spy JS bundle), `capture.py` (console/network/redaction), `evidence.py`, `results.py`, `checklist.py`, `schema.py`.
- `scripts/along_webdev.py` - CLI front; `scripts/along_webdev_mcp.py` - MCP front; both call the same engine functions.

## Acceptance Criteria
- [x] Portable CfT downloader and version resolver implemented in pure Python (`scripts/alongkit/webdev/cft.py`).
- [x] Browser process launcher with ephemeral ports, temporary user data directory, and clean teardown.
- [x] Playwright CDP bridge and execution runner implemented.
- [x] Declarative YAML scenario parser and runner implemented.
- [x] CDP diagnostics listener capturing console errors and HTTP 4xx/5xx network failures.
- [x] Step screenshot capture with WebP/PNG compression.
- [x] Structured `run-result.json` output conforming to `feat--along-report-engine` schema.
- [x] CLI command `along webdev` implemented in `scripts/along_webdev.py` and routed via `along_exec.py`.
- [x] Hermetic tests covering bootstrap logic, scenario parsing, and teardown.
- [x] REQ-1: `along webdev serve up` starts two declared services plus a `static` helper on a second origin, returns only after all probes pass; a service that exits after readiness is reported `crashed`; a `noise:`-matched warning does not fail the run; `serve down` leaves no child process (tested with a fake server script, no network).
- [x] REQ-1: an already-running service on a declared port is attached, not duplicated, and not stopped by `serve down`.
- [x] REQ-2: a click that navigates to a non-allowlisted origin fails the step with `blocked-origin` and a screenshot; a role/name locator matching 2 elements fails with both candidates listed; a coordinate click without `allow_coordinates: true` is a schema error.
- [x] REQ-3: filling a `type=password` field from a literal value is refused; a `${env:KEY}` value never appears in stdout, stderr, `results.json`, captured console/network or error text (test asserts by searching all outputs for the secret).
- [x] REQ-4: a check with `matrix: {viewport: [375x812, 1440x900], theme: [light, dark]}` produces 4 result rows; inside the page `innerWidth`, `matchMedia('(prefers-color-scheme: dark)').matches` and a seeded localStorage key read back the requested values before the first app script runs.
- [x] REQ-5: fixture page tests cover `press Shift+Enter` (newline, no submit), `press Escape` closing a dialog, `upload` of a generated file reaching the `change` handler with the right name and size, `back`/`forward`/`reload`.
- [x] REQ-6: `above`, `covered_by`, `overflow_x`, `box` return correct JSON on fixture pages built to pass and to fail each probe; a `spy` on `navigator.mediaSession.setPositionState` records calls made by page scripts.
- [x] REQ-7: `Authorization` / `Cookie` headers and configured body keys are redacted in every written artifact; noise filters suppress a configured favicon 404 at assertion time while the raw log still contains it.
- [x] REQ-8: evidence lands under `.along/artifacts/webdev/<issue>/<run-id>/` with deterministic names; `along init` adds the ignore rule in a fresh repo; `along lint` fails when a file under `.along/artifacts/` is staged.
- [x] REQ-9: `along webdev schema` prints a JSON Schema that validates the extended example above; YAML and JSON forms of the same scenario produce identical results; exit codes 0/1/2 as specified.
- [x] REQ-10: an interactive session of 5 steps followed by `save` yields a scenario whose `run` reproduces the same statuses; `checklist compile` on a 3-item Markdown checklist yields 3 checks with ids and `ac:` links; an uncompiled check reports NOT RUN `not-compiled`.
- [x] REQ-11: `run --issue <key>` replaces (not appends) the `## Browser Verification Results` section; `--file-failures` creates one bug issue per FAIL with reproduction steps and evidence paths, and creates none on an all-PASS run.
- [x] REQ-12: `route` fulfil-500, `network: offline` and `throttle` work on a fixture page; a check with `not_run:` reason appears as NOT RUN with that reason; `along webdev limits` lists the known platform limits; `serve down` refuses to stop a service the run did not start.
- [x] REQ-13: a contract test runs the same scenario through the CLI (`--json`) and through the MCP server and gets byte-identical result JSON (timings excluded); MCP registration is written for providers with a verified contract and reported for the rest.
- [x] REQ-14: `along wrap` on a `ui`-tagged issue with a FAIL or an unreasoned NOT RUN in its latest result is refused with a message naming the checks; `along doctor` shows webdev readiness.
- [x] Docs: `docs/topic--webdev-verification.md` (new) covers config, scenario schema, checklist flow, limits and emulation substitutes; `docs/topic--cli-reference.md` lists the `webdev` verbs.

## Open Questions
Resolved 2026-11-15: answers to 1-4 and 6 are the settled "Design decisions" of the approved issue plan (Python Playwright in an isolated runtime venv; Along-provisioned CfT; dedicated `along-webdev` MCP server; one issue in six phases; `webdev` opt-in via `verify.checks`). 5: milestone `v5.0.0-agent-run-protocol-and-observability`. Kept below for the record.

1. Driver dependency: Python `playwright` package (pip, brings its own driver) vs Node Playwright (needs Node in the target repo) vs raw CDP over a websocket (stdlib has no websocket client; would add a small dependency). Along's runtime dependency today is only `ruamel.yaml`; which footprint is acceptable?
2. Should the CfT download be replaced by `playwright install chromium` when option 1 is chosen, to avoid maintaining a second browser cache?
3. MCP server: a new `along-webdev` server, or one general `along` MCP server where webdev is the first tool group?
4. Size: split into child issues (substrate + CfT; services lifecycle; scenario/checklist/results; MCP front; protocol integration) under this one as umbrella, or keep one issue with phased plans?
5. Milestone: this issue is unscheduled. Which milestone should carry it (v5.0.0 agent-run-protocol-and-observability looks closest), so a plan can be written?
6. REQ-14 gating: tag-based (`ui`) or verify-policy-based opt-in, and should it be on by default for repositories with the `web` rule pack attached?
