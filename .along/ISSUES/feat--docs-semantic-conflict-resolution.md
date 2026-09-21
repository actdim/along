---
protocol: along
protocol_version: "3.8.0"
slug: docs-semantic-conflict-resolution
type: feat
status: open
priority: medium
created: 2026-09-21
updated: 2026-09-21
agent: antigravity
tags: [git, merge, docs, wiki, kb, markdown, llm]
milestone: v4.5.0-multi-user-merge-automation
blocked_by: [feat--git-merge-drivers-and-setup]
blocks: [feat--test-gated-code-merge-pipeline]
related: [feat--git-merge-drivers-and-setup]
---

# Semantic Knowledge Base & Documentation Conflict Auto-Resolution Engine

## Summary

When multiple developers or AI agents work concurrently on related features, they frequently update the same Knowledge Base topic articles (`docs/topic--*.md`) to document new endpoints, architectural decisions, and workflows.
Git default 3-way merge regularly halts on documentation files when two branches append new sections or alter adjacent bullet points.

This issue implements a semantic documentation conflict resolution engine:
1. `along resolve --docs`: Specialized command detecting conflicted markdown files and resolving semantic conflict blocks (`<<<<<<<`, `=======`, `>>>>>>>`).
2. Structural Markdown Reconciler: Merges non-overlapping headings, bullet lists, tables, and paragraphs while preserving dual contributions.
3. Link Integrity & Markdown Validation Gate: Verifies that merged documentation contains no broken internal links (`alongkit.markdown`) and runs `along kb sync` post-merge to maintain `docs/INDEX.md` consistency.

## Detailed Implementation Plan

### Stage 2.1: Conflict Detection and Parsing (`scripts/along_resolve.py`)
- Implement unmerged paths detector via `git status --porcelain`:
  - Isolates files with status `UU`, `AA`, `UD`, `DU`.
  - Filters paths matching `docs/**/*.md` and root documentation (`README.md`, `AGENTS.md`).
- Implement markdown conflict hunk parser:
  - Extracts ancestor (`%O`), current (`ours`), and incoming (`theirs`) content hunks between conflict markers.
  - Identifies AST section boundaries (H1, H2, H3 headers, code blocks, lists).

### Stage 2.2: Semantic Markdown Merge Engine
- Reconciliation heuristics:
  - Header-isolated additions: If branch A appended Section X and branch B appended Section Y under the same parent section, merge both sections in deterministic order.
  - List item additions: Perform set-union on unordered markdown lists (`- [ ] item`), eliminating duplicate items.
  - Table row additions: Identify markdown tables and append unique rows from both branches while keeping the header.
  - LLM/Agentic fallback: For complex paragraph rewrites where both branches modified the same sentence, construct a targeted semantic merge prompt providing baseline, local, and incoming diffs.

### Stage 2.3: Link Verification & Knowledge Base Recompilation
- Execute link integrity gate via `alongkit.markdown.find_broken_links`:
  - Checks every merged markdown file for dangling anchor links (`#heading-anchor`) or nonexistent file links (`[doc](./topic--other.md)`).
  - Automatically flags or fixes renamed topic references.
- Recompile Knowledge Base:
  - Automatically triggers `along kb sync` to update `docs/INDEX.md` and refresh document tags.

### Stage 2.4: Hermetic Test Suite (`tests/test_along_resolve_docs.py`)
- Test conflicting section additions in `docs/topic--test.md`.
- Test conflicting table rows and checklist items.
- Test broken link detection and recovery.

## Acceptance Criteria
- [ ] `along resolve --docs` reliably detects and resolves structural markdown conflicts.
- [ ] Conflicting heading additions from parallel branches are cleanly combined without manual intervention.
- [ ] Merged markdown files pass typography gates and link integrity verification.
- [ ] `along kb sync` runs automatically after successful documentation conflict resolution.
- [ ] Hermetic unit tests in `tests/test_along_resolve_docs.py` pass cleanly.
