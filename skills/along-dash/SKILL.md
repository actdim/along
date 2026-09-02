---
name: along-dash
description: Launch the Along dynamic executive dashboard, inspect entity DAG dependency graph, search Knowledge Base, or view OpenAPI Swagger docs. Use when the user requests a dashboard, status overview, repository metrics, or invokes /along-dash.
---

# Along Dashboard & Knowledge Base Engine (`/along-dash`) [v2.2.17]

Inspect, visualize, and analyze repository status across all `.along/` entities (`ISSUES`, `MILESTONES`, `RISKS`, `SPIKES`, `CHECKLISTS`, `SESSIONS`, `KB`, and ADR decisions) with live FastAPI backend, Swagger contracts, Knowledge Base search engine, and React 19 UI.

---

## When to Use

1. The user asks for a dashboard, status report, project analytics, or DAG dependency graph (e.g., "покажи дашборд", "запусти дашборд", "generate repo report", `/along-dash`).
2. Reviewing milestone progress, active blockers, risk mitigation status, and completed accomplishments.
3. Searching the structured Knowledge Base (`docs/`, `DECISIONS.md`) interactively.

---

## Standard Agent Workflow for `/along-dash`

When `/along-dash` is invoked (or the user asks for the dashboard), agents MUST:

1. **Execute CLI Summary**:
   Run `uv run scripts/along_dash.py . --cli` (or `python scripts/along_dash.py . --cli`).
   This parses entities on the fly and prints clean summary tables without polluting git status.

2. **Present Executive Summary & Active Issues in Chat**:
   Directly output the key statistics table and active issues list in the chat response.

3. **Launch the Live Web Dashboard in Background**:
   Start the interactive FastAPI web server as a background daemon task (`run_command` with `IsDaemon: true`):
   ```bash
   uv run scripts/along_dash.py . --web --no-browser
   ```

4. **Provide Direct Clickable Links & Controls**:
   - **Live Interactive Dashboard**: [**http://127.0.0.1:8765**](http://127.0.0.1:8765) (React 19 + Cytoscape DAG + Knowledge Base Explorer).
   - **OpenAPI Swagger UI**: [**http://127.0.0.1:8765/docs**](http://127.0.0.1:8765/docs) (Interactive API explorer).
   - **Server Control**: Note that the server runs in the background and can be stopped at any time by asking *"останови дашборд"* / *"stop dashboard"*.

---

## Execution Modes

### Mode 1: Terminal Summary (CLI - Instant On-the-Fly Scan)
```bash
uv run scripts/along_dash.py . --cli
```

### Mode 2: Interactive Local Web Dashboard (FastAPI + Swagger + React UI)
```bash
uv run scripts/along_dash.py . --web
```
- Serves live dashboard at `http://127.0.0.1:8765`.
- Real-time updates via Server-Sent Events (SSE) on file changes in `.along/`.
- Interactive Swagger docs at `http://127.0.0.1:8765/docs`.

### Mode 3: Development Mode (Vite HMR on 5173 + FastAPI Backend on 8765)
```bash
uv run scripts/along_dash.py --dev
```
*(Or `uv run .along/scripts/dev.py` / `/along-dev`)*
- Runs Vite dev server with Hot Module Replacement on `http://localhost:5173`.
- Proxies `/api`, `/docs`, `/openapi.json` to FastAPI on `http://127.0.0.1:8765`.

### Mode 4: Standalone Static HTML Report (Only When Requested)
```bash
uv run scripts/along_dash.py . --export .along/dashboard.html
```
