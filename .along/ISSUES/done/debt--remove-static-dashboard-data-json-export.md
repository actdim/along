---
protocol: along
protocol_version: "4.4.13"
slug: remove-static-dashboard-data-json-export
type: debt
status: done
completed: 2026-10-14
priority: high
created: 2026-10-14
updated: 2026-10-14
agent: antigravity
tags: [dashboard, github-pages, data-json, cleanup, ci-cd]
blocked_by: []
related: [feat--dashboard-architecture-graph-and-pages-publish]
---

# Remove Static Dashboard data.json Export and Decouple Pages Workflow

## Problem

In commit `d1a67f0` (`feat--dashboard-architecture-graph-and-pages-publish`), an ad-hoc export mechanism was introduced:
1. `scripts/along_dash.py --export` serializes the in-memory entity graph into a monolithic `data.json` file (~2.8 MB) and copies the React UI bundle from `packages/dashboard-ui` into `site/dashboard/`.
2. `packages/dashboard-ui/src/services/apiService.ts` was patched with a fallback (`fetch('./data.json')`) so the React SPA could run without a live FastAPI backend on GitHub Pages.
3. `.github/workflows/pages.yml` was weighed down with Node.js 22, pnpm 10, building the React 19 SPA, and generating this 2.8 MB snapshot on every documentation push.

This intermediary `data.json` violates the core design principle of Along: direct, first-class usage of Markdown files (`.along/ISSUES/*.md`, `.along/DECISIONS/*.md`, `.along/MILESTONES/*.md`).
Furthermore:
- The static React dashboard on GitHub Pages is degraded: live updates via SSE are broken, backend KB search (`/api/kb/search`) is unavailable, and URL routing without trailing slashes fails to resolve relative assets.
- Local execution (`along dash --web`, `along dash --cli`) reads Markdown files directly from disk via `EntityCollector` and never required `data.json`.
- Documentation publishing in MkDocs should render Markdown entities directly without an intermediate 2.8 MB JSON artifact or Node.js build dependencies in CI.

## Requirements

- REQ-1: Remove `data.json` export logic from `dashboard/app.py` (`--export` mode copying assets and generating `data.json`).
- REQ-2: Remove `fetch('./data.json')` fallback and `ResilientDashboardApiClient` workarounds from `packages/dashboard-ui/src/services/apiService.ts`. The frontend should cleanly interface with the FastAPI server for local development and web mode.
- REQ-3: Remove Node.js, pnpm, and dashboard build/export steps (`Build Dashboard UI`, `Export Dashboard static bundle`) from `.github/workflows/pages.yml`, leaving a lean MkDocs publishing pipeline.
- REQ-4: Remove or update the external `Dashboard` link in `mkdocs.yml` navigation, preparing for native in-tree Markdown issue/roadmap rendering.
- REQ-5: Verify that local dashboard CLI (`scripts/along_dash.py --cli`) and local web server (`scripts/along_dash.py --web`) continue to work seamlessly by reading Markdown files on disk.

## Acceptance Criteria

- [x] `.github/workflows/pages.yml` has zero references to pnpm, Node.js setup, and `scripts/along_dash.py --export`.
- [x] `data.json` is no longer generated or required anywhere in the build or runtime pipeline.
- [x] `packages/dashboard-ui` is decoupled from static GitHub Pages export workarounds.
- [x] Local dashboard (`scripts/along_dash.py --cli` and `--web`) operates without regressions.
- [x] All automated tests pass (`python .along/scripts/test.py`).
