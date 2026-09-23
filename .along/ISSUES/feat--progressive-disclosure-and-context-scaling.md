---
protocol: along
protocol_version: "4.0.1"
slug: progressive-disclosure-and-context-scaling
type: feat
status: open
priority: medium
created: 2026-09-23
updated: 2026-09-23
agent: antigravity
tags: [context, kb-search, progressive-disclosure, scaling, llm-wiki, schema]
milestone: v4.5.0-multi-user-merge-automation
blocked_by: []
related: []
---

# Progressive Context Disclosure and Scalable Retrieval Engine

## Problem

As an Along project grows to hundreds of ADRs, domain documents, and task records, injecting broad context or reading whole files wastes context window tokens and degrades reasoning:
1. **Blind Searching**: When agents do not know what topics or decisions exist, they make blind search queries or attempt broad directory listings.
2. **Full-File Loading Overhead**: When a relevant document is identified, agents often load the entire file (10-30 KB) even when only a single section or constraint is needed.
3. **Task Context Ambiguity**: Workers spend extra turns discovering which ADRs or domain models govern the current task.
4. **Structural Disparity between Wiki and Issues**: While `docs/` adheres to Karpathy's LLM-Wiki paradigm (rigid section taxonomy, verified references, compiled indices), issues and workflow artifacts lack structural schema contracts and machine-readable digests, leading to inconsistent ticket bodies and token-heavy backlog inspections.
5. **Daemon-Free Requirement**: Context disclosure must scale natively via Along CLI and file tools without requiring stateful servers, background MCP daemons, or external memory databases (such as Letta).

## Non-Goals & Architectural Boundaries

To avoid breaking the transactional nature of issues and workflow history:
- **No AST Ghost-Symbol Gate for Issues**: Wiki articles in `docs/` enforce AST grounding against codebase symbols. Issues describe future, planned, or defective functionality that does not yet exist; AST ghost symbol verification must not run against issues.
- **No Mutating Cross-Linking on Archive**: Auto-crosslinking must not mutate historical session logs (`.along/SESSIONS/`) or closed issues (`.along/ISSUES/done/`), which remain immutable in Git history.
- **No Heavy Background Memory Daemons**: Memory persistence remains strictly Git-grounded via Markdown and YAML frontmatter.

## Requirements

### 1. Project Map and Catalog Mode (`along kb-search --toc`)
- Implement `--toc` (or `--catalog`) in `along kb-search` (`scripts/along_kb_search.py`).
- Returns a compact hierarchical overview of available knowledge across both Wiki and entity scopes:
  - Curated wiki topics in `docs/`
  - Active ADR slugs and titles in `.along/DECISIONS/`
  - Active milestones and sprint targets
  - High-level domains
- Footprint must remain strictly bounded (< 150-200 tokens) so agents can discover available resources in a single call.

### 2. Bounded Snippets and Section Anchors
- Refactor `along kb-search` match formatting to return:
  - Bounded snippet windows (maximum 150 words per match).
  - Exact file paths with line-range anchors (e.g. `docs/topic--domain-model.md#L45-L75`).
  - Section headings corresponding to the matched chunk.
- Allows agents to use native host file tools (`view_file`, `Read`) with line boundaries instead of reading full documents.

### 3. Structural Section Contracts for Issues (`along issue lint`)
- Apply the LLM-Wiki structural taxonomy concept to issue management:
  - Standard mandatory sections: `## Problem`, `## Requirements` (or `## Architecture`), `## Acceptance Criteria`.
  - Reject empty placeholder bodies and ungrounded stubs during `along issue create` and `along issue sync`.
  - Add `along issue lint [--strict]` to audit issue files against section contracts.

### 4. Declarative Task-Bound Context (`requires`) and DAG Edges
- Support an optional `requires` section in issue frontmatter (`.along/ISSUES/<type>--<slug>.md`):
  ```yaml
  requires:
    decisions: [code-graph-mcp-and-hybrid-kb-search]
    docs: [topic--domain-model]
  ```
- Strengthen entity DAG relationships: ensure `requires`, `blocked_by`, and `related` are recognized in entity graphs.
- Update `along issue show <slug>` to display direct links to referenced context items.
- Enables `along-team` orchestrators to pass exactly the necessary context slices directly to workers.

### 5. Compact Backlog Digest (`along issue export --compact`)
- Introduce a lightweight machine-readable export of open issues (canonical key, status, priority, and 1-line title).
- Allows orchestrators and agents to survey the entire active backlog in < 250 tokens without opening individual issue markdown files.

### 6. Compact Architectural Projections
- Verify that `along decision sync` continues to compile only active, non-superseded architectural constraints into `.along/CONSTRAINTS.md` as compact bullet points (< 1 KB total).
- Superseded decisions and detailed historical discussions remain in modular ADR files and are omitted from the projection.

### 7. Role-Scoped Context via Subagents
- Ground progressive disclosure within `along-team` orchestration:
  - Scout gathers relevant snippets via `along kb-search`.
  - Implementer receives only the active task and referenced context slices.
  - Reviewer receives diffs and gate rubrics.

## Acceptance Criteria

- [ ] `along kb-search --toc` returns a compact hierarchical knowledge catalog (< 200 tokens).
- [ ] `along kb-search` output includes bounded snippets and line-number anchors for native slicing.
- [ ] Issue schema and `alongkit.issues` validate mandatory section contracts (`Problem`, `Requirements`, `Acceptance Criteria`).
- [ ] Issue frontmatter parser supports `requires` field (decisions, docs) and displays links in `along issue show <slug>`.
- [ ] `along issue export --compact` (or equivalent flag in `along issue list`) outputs a high-density, low-token backlog digest.
- [ ] AST symbol verification and mutating auto-crosslinking remain strictly scoped to `docs/` and never touch `.along/ISSUES/` or `.along/SESSIONS/`.
- [ ] Projections in `CONSTRAINTS.md` remain compact and bullet-aligned.
- [ ] Hermetic unit tests cover `--toc`, `requires` parsing, and issue section linting in `tests/test_kb_search.py` and `tests/test_alongkit.py`.
- [ ] Typography verification passes clean via `along sanitize`.
