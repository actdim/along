---
protocol: along
protocol_version: "3.0.0"
slug: mkdocs-root-index-404-and-version-drift
type: bug
status: done
priority: high
created: 2026-09-10
updated: 2026-09-10
completed: 2026-09-10
agent: antigravity
title: Fix MkDocs root 404 and version drift by injecting README.md as virtual index.md
---

# Bug: Fix MkDocs root 404 and version drift by injecting README.md as virtual index.md

## Description
- On GitHub Pages deployment, `/along/` returned 404 because MkDocs was configured with `Home: topic--index.md`, generating `site/topic--index/index.html` instead of root `site/index.html`.
- `docs/topic--index.md` was a static snapshot of README that was not updated by the release pipeline, freezing the web version at v2.5.0 instead of current v3.0.0.
- Solution: Inject `README.md` dynamically via MkDocs `on_files` hook as virtual `index.md`, generating `site/index.html` at root with zero file duplication, zero Windows filesystem case collisions, and automatic version synchronization with `README.md`.
