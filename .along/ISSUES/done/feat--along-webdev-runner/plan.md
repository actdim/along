# Plan: feat--along-webdev-runner

- Issue: `feat--along-webdev-runner`
- Status: approved by the user on 2026-11-15 (`along plan approve`); milestone `v5.0.0-agent-run-protocol-and-observability`. The design decisions below are settled.
- Execution Mode: Role-Based - the scope crosses a new engine package, the CLI router, the installer (MCP registration), lint checks, wrap/verify gates, scaffold, a new skill and the KB. Run it through `along-team`. Each phase below is one step loop, ends green, and is committed separately via `/along-commit` bound to `along-webdev-runner`.
- Verification Policy: `required` (full suite via `python .along/scripts/test.py`). Real-browser tests are an opt-in integration tier (see "Test strategy"); the default suite stays hermetic and network-free.

## Context

The ticket states the reference workload (a manual browser verification pass over 8 UI tickets that no-browser agents skipped), the gap analysis and REQ-1..REQ-14. This plan says how to deliver them.

What exists and must be reused, not duplicated:

- `scripts/alongkit/proc.py`:
  - `run_capture`, `child_env(extra=None, base=None)` - always build child envs with `child_env`;
  - `spawn_group_kwargs()` (~322) and `kill_process_tree(popen, grace)` (~329) - process groups / Job Objects and tree kill for services and the browser.
- `scripts/alongkit/bootstrap.py`: `ensure_deps(dependencies, modules, ...)`, `runtime_venv_dir()`, `_build_venv(uv, venv_dir, dependencies)`, `_venv_is_current` - the `uv`-based isolated runtime venv. Core runtime deps (`RUNTIME_DEPENDENCIES = ("ruamel.yaml>=0.18",)`) must not grow.
- `scripts/alongkit/repo.py`: `state_dir`, `RUNTIME_ONLY_ENTRIES` (already lists `artifacts` and `.session`), `ensure_diagnostics_dir` (self-ignoring directory via a `*` `.gitignore`; the user's `.gitignore` is never edited).
- `scripts/alongkit/repochecks.py`: `check_untracked_exports`, `is_diagnostics_path` / `_DIAGNOSTICS_RE`.
- `scripts/alongkit/verify.py`: `VerifyPolicy`, `CHECK_NAMES` rule for `checks`, `load_effective_policy(repo_root, slug)`, `run_checks`; the approved snapshot in `.along/.session/plan-approvals.jsonl` is the only policy gates read.
- `scripts/alongkit/install.py`: `McpTarget`, `mcp_target(provider, homes)`, `MCP_SERVER_ENTRY` shape; `scripts/configure_mcp.py` as the CLI front.
- `scripts/along_exec.py`: command router (`LIFECYCLE_ACTIONS`, `_BOARD_COMMANDS`, `print_help`).
- `scripts/alongkit/commands/doctor.py`: `_doctor_*_checks(repo_root, errors, warnings)` pattern.
- `scripts/alongkit/lifecycle.py`: `execute_wrap` (~1115), lifecycle hook resolution.
- `scripts/alongkit/entities` + `frontmatter`: issue lookup and front-matter updates; `along issue create` for failure filing.
- `scripts/alongkit/sanitizer.py` / `typography.py`: ASCII-safe text for anything written into issues.
- Tests: `tests/hermetic.py` (`make_repo_fixture`, `isolated_home_env`), `tests/test_along_exec.py`, `_Fixture` in `tests/test_verify_policy.py`.

## Design decisions (proposed; confirm at approval, then do not re-open)

1. **Driver: Python Playwright in an isolated, optional runtime venv.** Answers ticket Open Question 1.
   - `bootstrap` gains a named-runtime helper: `ensure_runtime("webdev", dependencies=("playwright==<pin>", "mcp==<pin>"))` builds `~/.along/runtimes/webdev-venv/` with `uv` on first use and re-executes `along_webdev.py` inside it. Core Along keeps `ruamel.yaml` as its only dependency; repositories that never call `along webdev` pay nothing.
   - No Node requirement. Node Playwright specs remain supported as the code escape hatch (REQ-9) by connecting to the same CDP endpoint.
2. **Browser: Along-provisioned Chrome for Testing, not `playwright install`.** Answers Open Question 2.
   - `cft.py` downloads and caches CfT (`~/.along/runtimes/cft/<version>/`) with `urllib` + `zipfile`, launches it itself (`--remote-debugging-port=0`, temp `--user-data-dir`, process group), and Playwright attaches with `chromium.connect_over_cdp`. One browser cache, one owner of the process lifetime, the same endpoint for Python and Node clients.
   - `--browser-path` / `webdev.browser_path` lets a user point at an existing Chromium (offline machines, CI images).
3. **One engine, two fronts.** `scripts/alongkit/webdev/` holds all logic and returns plain dicts. `scripts/along_webdev.py` (CLI) and `along webdev mcp` (stdio MCP server, `mcp` SDK in the same runtime venv) are thin adapters with the same verb names, argument names and result JSON. Answers Open Question 3: a dedicated `along-webdev` MCP server, registered next to `code-review-graph`.
4. **Interactive session = local daemon.** `session start` spawns a detached process that owns the browser and the Playwright sync API on ONE thread (Playwright sync objects are not thread-safe) and serves a JSON request/response protocol on `127.0.0.1:<ephemeral>` guarded by a random token. Endpoint, token, PIDs live in `.along/.session/webdev/session.json` (git-ignored, mode 0600 where supported). Idle timeout (default 30 min) and `session stop` tear everything down. Batch `run` uses the same engine in-process, no daemon.
5. **Config location.** `.along/webdev.yaml` (services, origins, noise, test_credentials, presets). Parsed with `ruamel.yaml` (safe loader). Scenario files may live anywhere in the repo; the default is `.along/webdev/scenarios/` (tracked, it is source).
6. **Evidence location and tracking.** Run folders under `.along/artifacts/webdev/<issue-key>/<run-id>/`. `.along/artifacts/` becomes a self-ignoring directory (same `*` `.gitignore` pattern as diagnostics), so consumer `.gitignore` files are never edited; `check_untracked_exports` is extended to any path under `.along/artifacts/`.
7. **Gating opt-in via the verify policy.** Answers Open Question 6: `webdev` becomes a check name in `verify.checks` (issue level, approved snapshot). Wrap refuses to close an issue whose approved policy lists `webdev` while its latest run has FAIL or an unreasoned NOT RUN. Nothing is gated by tags, and nothing is on by default; attaching the `web` rule pack only makes `along plan approve` print a hint.
8. **One issue, phased.** Answers Open Question 4: no child issues; the six phases below are the step loops and commits. If a phase slips past the milestone, it is split out at that point with `along issue create` and `related:`.
9. **Redaction is a single choke point.** Every byte that leaves the engine (stdout, stderr, JSON results, MCP results, files in the run folder, issue sections) passes through `webdev/redact.py`. Tests assert by grepping all outputs for a planted secret.
10. **Safety defaults.** Origin allowlist on (declared services + `about:blank`); coordinate actions need `allow_coordinates: true`; literal values into `type=password` refused; the runner never stops a service it did not start.

## Phases

### Phase 1 - Runtime, browser and teardown (REQ-13 groundwork, original AC 1-2)
Files:
- `scripts/alongkit/bootstrap.py`: `ensure_runtime(name, dependencies, modules)` built on the existing venv helpers.
- `scripts/alongkit/webdev/__init__.py`, `cft.py` (version resolve, download, unpack, cache, `--status`), `browser.py` (launch, read `DevToolsActivePort`, `connect_over_cdp`, close + `kill_process_tree`, temp profile purge).
- `scripts/along_webdev.py` (argparse skeleton: `bootstrap`, `doctor` stub-free subset), routing in `scripts/along_exec.py` + `print_help`.
Tests (hermetic): CfT version resolution and unpack from a fake zip served by a file URL; launcher argv; teardown kills a fake child tree; runtime re-exec guard. Integration tier: launch real CfT, open `about:blank`, close, no leftover process.
Done when: `along webdev bootstrap --status` reports cache state; integration test leaves zero processes on Windows and Linux.

### Phase 2 - Services lifecycle (REQ-1)
Files: `webdev/config.py` (`.along/webdev.yaml` schema + validation), `webdev/services.py` (start detached, probes `http|log|port`, `noise:`/`fatal:` classification, attach-if-running, state file `.along/.session/webdev/services.json`, `status`, `logs`, `down`), `kind: static` helper (stdlib `http.server` on a chosen root/port), CLI verbs `serve up|status|logs|down`.
Tests (hermetic): fake service scripts (`python -c` NOT used; fixture `.py` files under `tests/fixtures/webdev/`) that become ready, crash after readiness, print noise, print a fatal line; port already bound -> attach and not stopped; `down` leaves no child; `.env` value referenced in `env:` never printed.
Done when: REQ-1 ACs pass.

### Phase 3 - Browser engine: guard, locators, emulation, steps, probes, capture (REQ-2..REQ-7)
Files:
- `webdev/session.py` (one Playwright context per session, origin guard via `page.route` + `framenavigated`/`popup` handlers, init scripts, storage seeding, viewport/media emulation, matrix cell setup);
- `webdev/locators.py` (role/name, label, text, placeholder, test_id, css; ambiguity report with candidate boxes; coordinate gate);
- `webdev/steps.py` (REQ-5 vocabulary, generated upload fixtures in a temp dir, `wait_for` variants, `route`, `network`, `throttle`, `visual_viewport`);
- `webdev/probes.js` (bundled JS: `box`, `above`, `covered_by`, `overflow_x`, `in_viewport`, spy installer) + `probes.py` loader;
- `webdev/capture.py` (console, exceptions, requests with size-capped bodies), `webdev/redact.py` (headers, query/body keys, `.env` values), noise filters.
Tests: hermetic unit tests for locator parsing, redaction, noise filtering, step schema; integration tier against static fixture pages in `tests/fixtures/webdev/pages/` (layout pass/fail pairs for each probe, dialog + Escape, textarea Shift+Enter, file input, mediaSession spy, link to a foreign origin, password field).
Done when: REQ-2..REQ-7 ACs pass in the integration tier and the hermetic units pass in the default suite.

### Phase 4 - Scenarios, evidence, results, failure filing (REQ-8, REQ-9, REQ-11, REQ-12)
Files: `webdev/schema.py` (JSON Schema, YAML/JSON loader, `along webdev schema`), `webdev/runner.py` (checks x matrix, `not_run`, Node spec escape hatch via CDP endpoint env var), `webdev/evidence.py` (run-id, deterministic names, self-ignoring `.along/artifacts/`), `webdev/results.py` (`results.json` in `ReportPayload` shape, `results.md` table, issue section replace via entities/front-matter-safe Markdown edit, ASCII sanitising), `webdev/failures.py` (`--file-failures` -> `along issue create bug ...` with template body; otherwise print the commands), `along webdev limits`; extend `repochecks.check_untracked_exports` for `.along/artifacts/**`.
Tests (hermetic where possible): schema validates the ticket's extended example; YAML == JSON results; exit codes 0/1/2; section replace is idempotent; failure filing creates exactly one issue per FAIL in a `make_repo_fixture` repo; lint flags a staged artifact.
Done when: REQ-8, 9, 11, 12 ACs pass; `run-result.json` validates against the report-engine contract as documented in `feat--along-report-engine` (contract test only; no dependency on that issue's implementation).

### Phase 5 - Interactive session and checklists (REQ-10)
Files: `webdev/daemon.py` (single-thread request loop, token check, idle timeout, transcript), CLI verbs `session start|step|batch|save|stop|status`, `webdev/checklist.py` (Markdown checklist parser for files and for an issue's `## Browser Verification` section; `checklist compile` -> scenario skeleton with `steps: []` TODO; uncompiled -> NOT RUN `not-compiled`).
Tests: daemon protocol and token rejection (hermetic, fake engine); integration: 5-step session -> `save` -> `run` reproduces statuses; compile of a 3-item checklist.
Done when: REQ-10 ACs pass.

### Phase 6 - MCP front, protocol integration, docs and skill (REQ-13, REQ-14, docs AC)
Files:
- `webdev/mcp_server.py` + `along webdev mcp` (tools mirror CLI verbs; screenshots as paths, optional base64);
- `scripts/alongkit/install.py` + `scripts/configure_mcp.py`: register `along-webdev` for providers with a verified contract, report the snippet for the rest;
- `scripts/alongkit/verify.py`: `webdev` in check names; `scripts/alongkit/lifecycle.py` (`execute_wrap`): refuse on FAIL / unreasoned NOT RUN when the approved snapshot lists `webdev`; `--force-reason` per existing bypass rules;
- `scripts/alongkit/commands/doctor.py`: `_doctor_webdev_checks` (runtime venv, CfT, MCP registration, config/probe validity);
- `scripts/alongkit/scaffold.py` / `repo.py`: create self-ignoring `.along/artifacts/` on init/update;
- `skills/along-webdev/SKILL.md` (when to run, interactive vs scenario, limits, never type real passwords), installers' skill lists, `AGENTS.md` project-specifics skill list;
- `docs/topic--webdev-verification.md` (new), `docs/topic--cli-reference.md`, `docs/topic--runtime-hooks-and-gates.md` (wrap refusal), then `along kb-sync` to rebuild `docs/INDEX.md`.
Tests: CLI vs MCP parity contract test (same scenario, identical JSON minus timings) in the integration tier, plus a hermetic parity test on a fake engine; wrap refusal in a `make_repo_fixture` repo with a recorded approval snapshot; doctor output; MCP registration per provider using `isolated_home_env`.
Done when: REQ-13, REQ-14 and docs ACs pass; `along lint --worktree` clean; full suite green.

## Test strategy

- Default suite (`python .along/scripts/test.py`): hermetic only - no network, no browser download, no real Chrome. Engine pieces are tested through fakes (fake CDP endpoint object, fake service scripts, fixture zips via file URLs).
- Integration tier: `tests/test_webdev_integration.py`, skipped unless `ALONG_WEBDEV_E2E=1` and a browser is available (CfT cache or `webdev.browser_path`). Serves `tests/fixtures/webdev/pages/` from a temp-dir static server on 127.0.0.1. Run at the end of phases 3-6 and recorded in the step review.
- CI: add a separate job (Linux headless) that sets `ALONG_WEBDEV_E2E=1` after `along webdev bootstrap`; the default job stays unchanged.
- Dogfood check before wrap: run a scenario against this repo's own dashboard (`packages/dashboard-ui`, `npm run dev`) at two viewports and both themes; attach the results table to the session log (evidence stays untracked).

## Risks and mitigations

- **Playwright/CfT version skew** (CDP protocol drift): pin both; `bootstrap --status` prints both; doctor warns on mismatch.
- **Windows process trees** (dev servers spawn grandchildren, e.g. `pnpm` -> `node` -> `esbuild`): always spawn with `spawn_group_kwargs()` and kill via `kill_process_tree`; integration test counts processes before/after.
- **Runtime venv bootstrap offline**: clear setup error (exit 2) naming `uv` and the pins; `--browser-path` for preinstalled browsers.
- **Secrets leaking through page content** (an app echoing a token into the DOM or console): redaction covers values from `.env`, not arbitrary page text; documented as a limit.
- **Flaky geometry on animated layouts**: probes accept `settle_ms` and wait for `requestAnimationFrame` x2 before measuring.
- **Scope size**: six phases, each independently shippable; if the milestone date is at risk after Phase 4, phases 5-6 split into follow-up issues (decision 8).

## Out of scope

- Visual regression diffing (pixel baselines), Firefox/WebKit, real mobile devices, OS-level surfaces listed in REQ-12 (they stay NOT RUN or emulated), publishing to SharePoint/S3 (owned by `feat--along-report-engine` and `feat--along-storage-providers`).
