---
protocol: along
protocol_version: "3.9.5"
slug: dashboard-architecture-graph-and-pages-publish
type: feat
status: done
completed: 2026-09-22
priority: high
created: 2026-09-22
updated: 2026-09-22
agent: antigravity
tags: [dashboard, architecture, github-pages, vite, cytoscape]
milestone: v4.0.0-dashboard-and-knowledge-base
blocked_by: []
related: [debt--dashboard-ui-type-safety-and-security]
---

# Aggregated Architecture Graph and Automated GitHub Pages Dashboard Publication

## Problem Description

Currently, the Along Dashboard (`packages/dashboard-ui` and `dashboard/app.py`):
1. **Lacks Code Architecture Visualization**: The DAG Graph view only displays protocol entities (issues, milestones, risks, spikes, decisions, and KB articles). It does not visualize the high-level codebase architecture, module boundaries, or coupling between subsystems discovered by code-review-graph.
2. **Cannot Run as a Static Web Application on GitHub Pages**: The UI is tightly coupled to an active FastAPI backend (`/api/data`), throwing `Failed to Connect to Dashboard API` when accessed statically. Vite assets are built with root `base: '/'`, causing 404s when hosted under `/along/dashboard/`.
3. **No Automated CI/CD Deployment**: The GitHub Pages workflow (`.github/workflows/pages.yml`) only builds MkDocs and does not compile `@along/dashboard-ui` or export static data snapshots (`data.json`). There is no navigation link in MkDocs to access the dashboard.

## Required Changes

1. **Architecture Graph Integration**:
   - Save initial architecture communities snapshot from `code-review-graph` in `.along/architecture.json`.
   - Update `dashboard/core/graph.py` to ingest `.along/architecture.json` (with lightweight directory/package fallback) and inject architecture modules and cross-module coupling edges into the Cytoscape graph.
   - Extend `packages/dashboard-ui` (`DAGGraphView.tsx`) with an `architecture` filter mode, distinct module styling, and coupling edge visualization.

2. **Static Mode and Relative Base Path in Dashboard UI**:
   - Update `packages/dashboard-ui/vite.config.ts` with `base: './'`.
   - Update `packages/dashboard-ui/src/services/apiService.ts` to fallback to `fetch('./data.json')` when `/api/data` is unreachable.
   - Cleanly close SSE on error to avoid connection retry loops on static hosting.

3. **Static Export CLI & CI/CD Pipeline**:
   - Update `scripts/along_dash.py --export` to write `data.json` and copy UI assets into the destination directory.
   - Update `.github/workflows/pages.yml` to build the UI with pnpm, export `site/dashboard/`, and upload it as part of GitHub Pages.
   - Add navigation link in `mkdocs.yml` pointing to `https://actdim.github.io/along/dashboard/`.
