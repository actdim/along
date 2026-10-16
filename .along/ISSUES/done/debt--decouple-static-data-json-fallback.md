---
protocol: along
protocol_version: "4.4.13"
slug: decouple-static-data-json-fallback
type: debt
status: done
completed: 2026-10-14
priority: high
created: 2026-10-14
updated: 2026-10-14
agent: antigravity
tags: [dashboard-ui, cleanup]
related: [debt--remove-static-dashboard-data-json-export]
blocked_by: []
---

# Decouple frontend from static data.json fallback

Decouple `packages/dashboard-ui/` API service from static `data.json` fallback, routing requests to live API endpoints with robust error states.

## Acceptance Criteria
- [x] Decouple frontend from static data.json fallback
- [x] Automated tests passing
