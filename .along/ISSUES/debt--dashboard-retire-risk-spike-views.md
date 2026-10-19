---
protocol: along
protocol_version: "4.5.0"
slug: dashboard-retire-risk-spike-views
type: debt
status: open
priority: low
created: 2026-10-19
updated: 2026-10-19
agent: claude-code
tags: [dashboard, entities, cleanup]
blocked_by: []
related: [debt--entity-model-slimming, debt--along-core-extras-split]
---

# Dashboard: retire risk and spike views

## Problem

`debt--entity-model-slimming` removed the Risk entity and made spikes an issue type. The
dashboard only got `spike` in the issue type literal; it still reads the retired
`.along/RISKS/` and `.along/SPIKES/` folders, which are now always empty after migration.

## Requirements

- REQ-1: Remove `_collect_risks` / `_collect_spikes` (`dashboard/core/collector.py`), the risk
  and spike nodes and edges (`dashboard/core/graph.py`), `RiskSchema` / `SpikeSchema`,
  `active_risks`, `risks`, `spikes` (`dashboard/schemas/`), and `GET /risks`, `GET /spikes`
  (`dashboard/api/entities_api.py`).
- REQ-2: Show risks as issues tagged `risk` (overview card, DAG node style) instead.
- REQ-3: Make `risks_logged` / `spikes_conducted` of old session logs optional or drop them from `SessionSchema`.
- REQ-4: Regenerate `packages/dashboard-ui/openapi.json` and the NSwag client
  (`src/api/client.ts`); update `types.ts`, `EntityDrawer.tsx`, `DAGGraphView.tsx`,
  `OverviewView.tsx`, `client.test.ts`; rebuild `dashboard/ui/dist`.

## Acceptance Criteria
- [ ] No dashboard code reads `.along/RISKS/` or `.along/SPIKES/`
- [ ] Risk-tagged issues are visible on the overview and in the DAG
- [ ] Client regenerated, 100% typed (zero `any` / `as`), `npm run build` passes
- [ ] Automated tests passing
