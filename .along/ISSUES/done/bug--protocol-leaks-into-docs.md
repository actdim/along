---
protocol: along
protocol_version: "4.6.0"
slug: protocol-leaks-into-docs
type: bug
status: done
completed: 2026-11-05
priority: high
created: 2026-11-05
updated: 2026-11-05
agent: antigravity
tags: [kb-sync, scaffold, docs, separation-of-concerns, leak]
blocked_by: []
related: []
plan_status: approved
---

# Internal agent protocol leaks into public docs/INDEX.md and GitHub Pages

## Problem

`along init` and `along update` force-scaffold `docs/topic--along-protocol.md` inside `docs/`. When `along kb-sync` executes, it indexes all `topic--*.md` articles and registers `Along Protocol Reference` in `docs/INDEX.md`:
1. In the public Mermaid graph: `T_ALONG_PROTOCOL["Along Protocol Reference"]`.
2. In the public article catalog: `- **[Along Protocol Reference](./topic--along-protocol.md)**`.

Static site documentation builders (VitePress, MkDocs, Docusaurus) deployed on GitHub Pages (e.g. `@actdim/utico`, `@actdim/dynstruct`, `@actdim/msgmesh`, `mempart`) compile `docs/INDEX.md` into the site landing page (`index.html`). As a result, public library consumers see internal AI agent orchestration regulations (gates, sessions, blackboard, wrap flow) on the public documentation portal.

## Root Cause

1. `debt--agents-md-core-slimming` (commit `856249a`) reduced `AGENTS.md` from 14 KB to ~5 KB, moving situational procedures to a separate file.
2. The file was scaffolded into the public `docs/` folder (`docs/topic--along-protocol.md`) instead of the internal agent directory `.along/`.
3. `along kb-sync` does not filter out internal agent service articles, indexing every `topic--*.md` indiscriminately.

## Requirements

- REQ-1: `alongkit.scaffold` MUST define the protocol reference location as `.along/PROTOCOL.md` instead of `docs/topic--along-protocol.md`.
- REQ-2: `along init` and `along update` MUST scaffold and refresh the protocol reference at `.along/PROTOCOL.md` for FULL roots.
- REQ-3: `along update` and `migrate_protocol.py` MUST remove legacy `docs/topic--along-protocol.md` if it contains the Along managed marker.
- REQ-4: `skills/along-init/protocol.md` and `AGENTS.md` managed blocks MUST link procedures to `.along/PROTOCOL.md`.
- REQ-5: `along_kb_search.py` MUST index `.along/PROTOCOL.md` so agents can retrieve situational protocol procedures via `/along-kb-search`.
- REQ-6: `along_kb_sync.py` MUST exclude internal agent protocol topics from `docs/INDEX.md`, Mermaid diagrams, `llms.txt`, and `llms-full.txt`.
- REQ-7: All automated regression tests MUST verify `.along/PROTOCOL.md` and confirm `docs/INDEX.md` remains free of internal protocol nodes.

## Acceptance Criteria

- [x] `alongkit.scaffold.REFERENCE_DOC_RELPATH` points to `(".along", "PROTOCOL.md")`.
- [x] `along init` and `along update` create/refresh `.along/PROTOCOL.md` and prune managed `docs/topic--along-protocol.md`.
- [x] `AGENTS.md` managed core and `skills/along-init/protocol.md` reference `.along/PROTOCOL.md`.
- [x] `along_kb_search.py` indexes `.along/PROTOCOL.md` with keyword and snippet extraction.
- [x] `along_kb_sync.py` omits `along-protocol` from `docs/INDEX.md` and `llms.txt`.
- [x] Unit tests pass cleanly (test_scaffold_profiles, test_docs, test_wrap_engine_writes, test_skills_and_scripts).
