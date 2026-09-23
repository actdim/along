---
protocol: along
protocol_version: "4.0.1"
slug: kb-search-deterministic-gate-and-skill-hardening
type: feat
status: done
completed: 2026-09-23
priority: high
created: 2026-09-23
updated: 2026-09-23
agent: antigravity
tags: [kb-search, gates, skills, performance, token-hygiene]
milestone: v4.1.0-code-intelligence-and-mcp-ecosystem
blocked_by: []
related: [feat--code-review-graph-user-skills]
---

# Deterministic Fast-Retrieval Gate and along-kb-search Skill Hardening

## Problem Description

When users or subagents invoke `/along-kb-search` or search the knowledge base and project memory, LLM agents frequently experience severe execution latency (15-30+ seconds). Agents tend to fall back into sequential file inspection loops, manually listing and grepping files across `docs/` and `.along/` directories rather than executing Along's deterministic search engine.

This occurs because:
1. **Ambiguous Skill Directives**: The instruction in `skills/along-kb-search/SKILL.md` explains the concept in prose but lacks strict negative constraints forbidding agents from manually inspecting files when searching.
2. **Missing Runtime Gate**: There is no programmatic gate preventing agents from executing `grep_search` or `find_by_name` targeting documentation or project memory directories.
3. **Execution Path Friction**: The in-memory Python search engine (`scripts/along_kb_search.py`) takes only 40-70ms to execute, but agents do not treat it as a mandatory single-shot command unless deterministically guided.

## Required Changes

### 1. Declarative Gate Implementation (`[gate: fast-retrieval]`)
- Add `fast_retrieval` gate to `scripts/alongkit/hooks/default_gates.yaml` intercepting `PreToolUse` for search tools (`grep_search`, `find_by_name`, `find_files`, `file_search`).
- Implement predicate `check_fast_retrieval` in `scripts/alongkit/hooks/predicates.py`:
  - Blocks `grep_search` and `find_by_name` targeting directories under `docs/` or `.along/`.
  - Permits single-file targeted greps (`os.path.isfile`) when an agent inspects a specific known document.
  - Permits whole-repository searches (`SearchPath="."` or empty) for broad code queries.
  - Returns clear actionable rejection instructing the agent to run `along kb-search "<query>"`.

### 2. Skill Contract Hardening (`skills/along-kb-search/SKILL.md`)
- Add strict negative constraints with anchor `[gate: fast-retrieval]`:
  - Agents MUST NOT use file-reading or directory search tools (`view_file`, `grep_search`, `find_by_name`, `list_dir`) to search knowledge base or issues manually.
  - Agents MUST execute `along kb-search "<query>"` in a single shot.
  - Provide clear CLI syntax and fallback options.

### 3. Protocol Alignment
- Anchor the `Fast Retrieval` rule in `skills/along-init/protocol.md` and `AGENTS.md` to `[gate: fast-retrieval]`.
- Verify full bi-directional traceability via `along hook verify --strict`.

### 4. Hermetic Unit Tests
- Add unit tests in `tests/test_declarative_gates.py` verifying:
  - Interception and rejection of `grep_search` on `docs/` and `.along/`.
  - Interception and rejection of `find_by_name` on `docs/` and `.along/`.
  - Allowance of targeted single-file inspection in `docs/`.
  - Allowance of whole-repository search.
  - Correct error message formatting.

## Acceptance Criteria
- `python scripts/along_hook.py verify --strict` passes with 100% anchored gates.
- All declarative gate unit tests pass cleanly.
- Full test suite passes without regressions under `python .along/scripts/test.py`.
