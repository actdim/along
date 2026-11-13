---
protocol: along
protocol_version: "4.8.1"
date: 2026-11-13
slug: opencode-runtime-integration
agent: antigravity
branch: main
commit: d1a5b4e
summary: 'feat: opencode runtime hooks integration and multi-subproject issue discovery'
issues_advanced: []
issues_completed: [feat--opencode-runtime-integration]
decisions: []
files: [.along/PROTOCOL.md, AGENTS.md, scripts/along_hook.py, scripts/alongkit/commands/issue.py, scripts/alongkit/commands/lifecycle.py, scripts/alongkit/entities/projections.py, scripts/alongkit/entities/stubs.py, scripts/alongkit/entities/validation.py, scripts/alongkit/entities/vocabulary.py, scripts/alongkit/hooks/adapters/__init__.py, scripts/alongkit/hooks/adapters/generic.py, scripts/alongkit/hooks/adapters/opencode.py, scripts/alongkit/hooks/config.py, scripts/alongkit/hooks/opencode_plugin.js, scripts/alongkit/install.py, scripts/alongkit/runtime.py, scripts/alongkit/session.py, skills/along-init/protocol-reference.md, skills/along-init/protocol.md, tests/test_issue_plans.py, tests/test_multi_subproject_find.py, tests/test_opencode_runtime.py]
---

# Session: Opencode runtime integration

## Summary
feat: opencode runtime hooks integration and multi-subproject issue discovery

## Decisions
- None (confirmed at wrap: no architectural decisions).

## Blackboard Record

Execution mode: role-based; plan revision 2; approved: true.

| Step | Title | Status | Retries | Review |
| --- | --- | --- | --- | --- |
| 1 | Step 1 | passed | 0 | yes |
| 2 | Step 2 | passed | 0 | yes |
| 3 | Step 3 | passed | 0 | yes |
| 4 | Step 4 | passed | 0 | yes |
| 5 | Step 5 | passed | 0 | yes |
| 6 | Step 6 | passed | 0 | yes |

Plan: kept with the issue (`plan/plan.md`, 1 revision(s)).

### Execution Trace

#### Execution Trace: opencode-runtime-integration
- 2026-11-13T02:01:33Z plan approved (approved issue plan; approved_via: issue-plan)
- 2026-11-13T02:01:50Z plan approved (along scratch; approved_via: cli-unverified)
- 2026-11-13T02:01:55Z step 1: pending -> in-progress
- 2026-11-13T02:03:57Z step 1: in-progress -> passed
- 2026-11-13T02:04:02Z step 2: pending -> in-progress
- 2026-11-13T02:06:29Z step 2: in-progress -> passed
- 2026-11-13T02:06:34Z step 3: pending -> in-progress
- 2026-11-13T02:07:49Z step 3: in-progress -> passed
- 2026-11-13T02:07:53Z step 4: pending -> in-progress
- 2026-11-13T02:09:36Z step 4: in-progress -> passed
- 2026-11-13T02:09:41Z step 5: pending -> in-progress
- 2026-11-13T02:10:50Z step 5: in-progress -> passed
- 2026-11-13T02:10:55Z step 6: pending -> in-progress
- 2026-11-13T02:12:06Z step 6: in-progress -> passed
- 2026-11-13T02:19:22Z test FAIL (Wrap Quality Gate)
- 2026-11-13T02:32:43Z test pass (Wrap Quality Gate)

### Review step-1

#### Review Step 1: OpenCode Hook Plugin and Adapter Updates

##### Checks
- OpenCode plugin template `scripts/alongkit/hooks/opencode_plugin.js` implemented with `tool.execute.before`, `tool.execute.after`, and `shell.env`.
- `OpenCodeAdapter` implemented in `scripts/alongkit/hooks/adapters/opencode.py` and registered in adapter factory.
- `SESSION_ENV_MARKERS` in `scripts/alongkit/session.py` updated to include `OPENCODE_SESSION_ID`.
- `detect_agent` updated in `scripts/alongkit/entities/vocabulary.py`.

VERDICT: PASS

### Review step-2

#### Review Step 2: Hook Installation, Runtime Detection, and Doctor Integration

##### Checks
- `install_opencode_hooks` implemented in `scripts/alongkit/hooks/config.py`.
- `scripts/along_hook.py` supports `--runtime opencode` in `along hook install`.
- `scripts/alongkit/runtime.py` marks `opencode` with `runtime_hooks: True` and checks `along-gates.js`.
- `along doctor` reports mechanical enforcement under OpenCode.

VERDICT: PASS

### Review step-3

#### Review Step 3: Cross-Subproject Issue Discovery and Start Navigation Hints

##### Checks
- `along issue find <slug_or_key>` implemented in `scripts/alongkit/commands/issue.py` searching all contexts via `repo.find_agent_contexts()`.
- Supports `--json` structured output.
- `along start <slug>` in `scripts/alongkit/commands/lifecycle.py` searches child contexts and prints navigation hint when found in a subproject.

VERDICT: PASS

### Review step-4

#### Review Step 4: Fix Projection Plan Status Wording, Doctor Integrity Check, and Lint Audit

##### Checks
- `_PLAN_STATUS_NOTES["approved"]` updated to output `- plan approved` in `scripts/alongkit/entities/projections.py`.
- `along doctor entities` checks `ISSUES.md` plan note consistency against front matter in `scripts/alongkit/entities/validation.py`.
- `along issue lint` audits stale free-text status headers in `plan.md` in `scripts/alongkit/entities/stubs.py`.

VERDICT: PASS

### Review step-5

#### Review Step 5: Update Protocol Documentation, Sub-Agent Execution Guidance, and Init Templates

##### Checks
- `skills/along-init/protocol.md` and `AGENTS.md` updated with Authority & Discovery clause.
- `skills/along-init/protocol-reference.md` and `.along/PROTOCOL.md` updated with OpenCode mechanical enforcement and sub-agent execution guidance across runtimes.

VERDICT: PASS

### Review step-6

#### Review Step 6: Verify with Automated Hermetic Test Suite and CLI Verification

##### Checks
- `tests/test_opencode_runtime.py` created and passed (7 tests).
- `tests/test_multi_subproject_find.py` created and passed (5 tests).
- `tests/test_runtime_detection.py` passed (11 tests).
- `along sanitize` scanned 1234 files with 0 banned characters.

VERDICT: PASS
