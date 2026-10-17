---
protocol: along
protocol_version: "4.4.16"
slug: gate-event-remeasure
type: task
status: open
priority: medium
created: 2026-10-17
updated: 2026-10-17
agent: claude-code
tags: [gates, hooks, metrics]
parent: feat--autonomous-multi-runtime-mvp
blocked_by: []
related: [debt--gate-simplification]
---

# Re-measure gate events after gate simplification

Split out of debt--gate-simplification: its last acceptance criterion needs a normal week of
work on the new hooks and cannot be checked when the change lands.

## Baseline (2026-10-17, `hooks_audit.jsonl`)

| Repository | Gate events | `require_plan_approval` | of them "Inquiry Read-Only" |
| --- | --- | --- | --- |
| along | 1025 | 820 | 639 |
| dotnet + mempart | 2734 | 2403 | 2267 |

## Steps

1. Reinstall the hooks from the release that carries debt--gate-simplification
   (`along update`, then `along hook install`) in along, public/dotnet and mempart.
2. Work normally for a week.
3. Per repository: `along gates stats --since <install date>`; count `require_plan_approval`
   entries and the "Repeated blocks" section. Use the new `target` field to classify each
   remaining block as true or false positive.

## Acceptance Criteria
- [ ] `require_plan_approval` events down by at least 80% against the baseline, per repository.
- [ ] No repeated identical blocks (>= 3) per conversation, or each one explained.
- [ ] False positives found are filed as bug issues.
