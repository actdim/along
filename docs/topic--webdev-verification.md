---
protocol: along
protocol_version: "4.9.0"
slug: webdev-verification
title: WebDev & Browser Execution Substrate
type: reference
curated: true
created: 2026-11-21
updated: 2026-11-21
tags: [webdev, browser, playwright, cft, verification, testing, runner]
---

# WebDev & Browser Execution Substrate

The Along WebDev substrate provides a self-contained, provider-agnostic browser execution environment for automated UI verification, exploratory agent sessions, and visual proof capture.

---

## 1. Architecture Overview

The system is organized into modular layers:
- **Runtime & CfT Manager (`cft.py`, `browser.py`)**: Provisions isolated Python Playwright dependencies and portable Chrome for Testing (CfT) binaries without requiring global installs or harness-specific browser tools.
- **Services Lifecycle (`services.py`, `config.py`)**: Spawns, monitors, and terminates background dev servers and mock backends with HTTP/port readiness probes and secret redaction.
- **Engine & Probes (`session.py`, `locators.py`, `steps.py`, `probes.js`)**: Executes semantic actions using accessibility roles, labels, and text locators; measures in-page geometry and spatial relationships (`above`, `covered_by`, `overflow_x`); filters diagnostic noise.
- **Interactive Session Daemon (`daemon.py`)**: Runs a persistent browser behind a local token-authenticated HTTP service on 127.0.0.1, recording exploratory steps into reusable scenario transcripts.
- **Natural-Language Checklist Compiler (`checklist.py`)**: Compiles Markdown verification checklists from files or issue descriptions into declarative scenario skeletons.
- **Scenario Runner & Failure Filing (`runner.py`, `evidence.py`, `results.py`, `failures.py`)**: Expands checks across viewport and theme matrices, writes deterministic evidence to self-ignoring `.along/artifacts/webdev/`, updates issue verification tables, and auto-files reproducible bug tickets on failures.
- **Model Context Protocol (MCP) Server (`mcp_server.py`)**: Exposes stdio MCP tools mapping 1:1 to CLI verbs.

---

## 2. Configuration (`.along/webdev.json`)

Declare application services, viewports, origins, and noise filters:

```json
{
  "services": {
    "web": {
      "command": "npm run dev",
      "cwd": "packages/web",
      "probe": {"http": "http://localhost:5173", "status": [200, 304], "timeout_seconds": 30}
    },
    "api": {
      "command": "python server.py",
      "probe": {"port": 8000, "timeout_seconds": 15}
    }
  },
  "defaults": {
    "origins": ["http://localhost:5173", "http://localhost:8000"],
    "viewport": "desktop-1440x900",
    "theme": "light"
  }
}
```

---

## 3. CLI Commands Reference

### Service Management
- `along webdev serve up [services...]`: Start declared services and wait for readiness probes.
- `along webdev serve status`: Inspect running services and health status.
- `along webdev serve logs [services...] [--tail N] [--grep REGEX]`: Harvest log excerpts.
- `along webdev serve down [services...]`: Gracefully terminate spawned service process trees.

### Interactive Exploratory Sessions
- `along webdev session start [--issue SLUG] [--headed]`: Launch daemon and persistent browser session.
- `along webdev session step --step '<json-or-yaml>'`: Execute single exploratory step.
- `along webdev session batch --batch '<json-or-yaml>'`: Execute multiple steps sequentially.
- `along webdev session save --as <scenario.yaml>`: Save recorded transcript as a reusable scenario.
- `along webdev session status`: Check daemon health and recorded step count.
- `along webdev session stop`: Terminate browser and daemon.

### Scenario Execution & Verification
- `along webdev run <scenario.yaml> [--issue SLUG] [--check ID] [--file-failures]`: Run verification checks.
- `along webdev shot --url <url> --out <path> [--viewport VP] [--theme light|dark]`: Capture quick visual proof.
- `along webdev checklist compile <file|slug> [--out <scenario.yaml>]`: Compile checklist to scenario skeleton.
- `along webdev limits`: Display declared unverifiable surfaces and emulation substitutes.
- `along webdev mcp`: Run stdio MCP server for agent integration.

---

## 4. Verification Policy & Wrap Gate

When an issue declares `webdev` in its `verify.checks` policy:
```yaml
verify:
  tests: required
  checks: [webdev]
```

The wrap gate (`along wrap`) enforces:
1. The issue must contain a valid `## Browser Verification Results` section.
2. All executed checks must report `PASS` (or `NOT RUN` with an approved `platform-limit:<name>` reason).
3. Any check with `FAIL` or unreasoned `NOT RUN` blocks issue wrap unless `--force-reason` is explicitly supplied.
