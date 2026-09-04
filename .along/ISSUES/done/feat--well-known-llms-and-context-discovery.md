---
protocol: along
protocol_version: "2.2.18"
slug: well-known-llms-and-context-discovery
type: feat
status: done
completed: 2026-09-04
priority: high
created: 2026-09-04
updated: 2026-09-04
agent: antigravity
tags: [llms-txt, well-known, alongkit, discovery, kb-sync]
---

# Feature: Deterministic llms.txt & llms-full.txt with .well-known/ Support and Centralized Context Discovery

## Problem Statement
1. `llms.txt` and `llms-full.txt` lack support for `.well-known/` directory resolution.
2. `llms-full.txt` was not deterministically compiled by script, leading to drift or manual maintenance.
3. Downward traversal for Along contexts and project manifests is duplicated across `along_update.py`, `along_dep_scan.py`, and `along_kb_sync.py`, with hardcoded ignore lists and inconsistent patterns.

## Target Changes
1. Centralize downward discovery in `alongkit.repo`:
   - `find_agent_contexts(root)`: standard downward walk finding `.along/`, `.agents/`, or `AGENTS.md` using `IGNORED_DIRS` and `PROVIDER_DIRS`.
   - `find_manifest_projects(root)`: standard downward walk finding package/build manifests.
   - `resolve_llm_targets(target_dir, filename)`: resolves target paths checking `.well-known/` and root.
2. Implement deterministic `llms.txt` and `llms-full.txt` compilation in `along_kb_sync.py`.
3. Support `.well-known/` in `along_dep_scan.py` and `along_version_bump.py`.
4. Add hermetic test suite covering all cases.

