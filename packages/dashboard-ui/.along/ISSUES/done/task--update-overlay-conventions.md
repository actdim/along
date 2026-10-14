---
protocol: along
protocol_version: "4.4.12"
slug: update-overlay-conventions
type: task
status: done
completed: 2026-10-14
priority: medium
created: 2026-10-14
updated: 2026-10-14
agent: antigravity
tags: [docs, conventions, overlays]
blocked_by: []
related: []
---

# Apply generalized overlay and modal conventions from mempart

Apply updated and generalized overlay conventions from `mempart/src/apps/webapp/docs/topic--frontend-conventions.md` into `docs/topic--frontend-conventions.md`:
- Expanded guidelines prohibiting callback props (`onClose`, `onOpen`, `onDismiss`).
- Concrete code snippet for two-way binding on `open` with anchor element cleanup.
- Fragment child rendering rules for reactive live observer updates.
- Hardware back button and Escape key lifecycle rules via `def.effects` and `onDestroy`.

## Acceptance Criteria
- [x] Generalized overlay and modal conventions applied to docs/topic--frontend-conventions.md
- [x] along kb sync and along sanitize pass cleanly
- [x] Automated tests passing
