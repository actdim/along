---
protocol: along
slug: actdim-along-full-branding
type: docs
status: done
priority: medium
created: 2026-09-15
updated: 2026-09-15
completed: 2026-09-15
agent: antigravity
tags: [branding, docs, index, seo, release]
blocked_by: []
related: []
milestone: v1.3.0-knowledge-base-and-graph
---

# ActDim Along Full Branding Integration

## Context & Problem
The repository and protocol are published under `actdim-along`, but documentation entry points previously used the bare name "Along" in primary H1 headers and index generators. Using "Along" as a solitary English word causes search dilution in web and LLM vector indexing.

## Objectives
1. Adopt canonical full branding "ActDim Along" in README.md, llms.txt, llms-full.txt, and AGENTS.md (Project specifics).
2. Enable dynamic project title injection into docs/INDEX.md via along_kb_sync.py.
3. Update version bump regexes in scripts/along_version_bump.py to support ActDim Along.
4. Update automated test assertions in tests/test_skills_and_scripts.py.
5. Recompile docs/INDEX.md and llms-full.txt.
