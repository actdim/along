---
protocol: along
protocol_version: "4.4.16"
slug: release-v4-5-0
type: task
status: done
completed: 2026-10-18
priority: medium
created: 2026-10-18
updated: 2026-10-18
agent: claude
tags: [docs, release]
blocked_by: []
related: [debt--agents-md-core-slimming]
---

# Doc sweep for protocol core/reference split; release v4.5.0

User request (2026-10-18): check that all docs are updated after `debt--agents-md-core-slimming`, update them if needed, commit everything, update the global Along install, and release 4.5 with a push.

## Requirements

- REQ-1: Docs that describe `along init` / `along update` outputs or the `AGENTS.md` block name the slim core and the managed `docs/topic--along-protocol.md` reference: `docs/topic--setup-and-workflow.md`, `docs/topic--skills-reference.md`, `skills/along-init/SKILL.md`, `skills/along-update/SKILL.md`.
- REQ-2: Commit all pending working-tree changes, including earlier uncommitted milestone/issue edits.
- REQ-3: Reinstall the global Along install from this checkout (`install.ps1 -Target all`).
- REQ-4: Release v4.5.0 via `/along-version-bump` (minor): changelog, milestone reconciliation, annotated tag; push the commits and tag.

## Acceptance Criteria
- [x] Docs describe the core + reference split (REQ-1): setup-and-workflow, skills-reference, along-init and along-update SKILLs; the hermetic-rule pointer now targets the reference; reviewed source hashes re-pinned.
- [x] Working tree clean after commits (REQ-2): 33a8813, 139113a.
- [x] Global install reports v4.5.0 and carries `protocol-reference.md` (REQ-3): `~/.along/bin/alongkit/version.py` reads 4.5.0; the reference is present in the Claude skills and the OpenCode helper.
- [x] Tag `v4.5.0` created and pushed with `main` (REQ-4): release commit a085e4b; CI green on 33a8813 and 139113a before the bump.
- [x] Automated tests passing (1420 OK)

## Notes

- The first bump attempt aborted on the strict KB gate. The slug `dependencies` existed in both root and `packages/dashboard-ui` docs, a collision introduced after v4.4.16. `along_kb_sync.py` now treats engine-written per-context slugs (`dependencies`, `along-protocol`) as standard; covered by `test_engine_per_context_slugs_never_collide`.
- Pre-existing source-drift warnings in architecture, llm-wiki-architecture, migrations and the `along-kb-sync` pin are unreviewed and left as is.
