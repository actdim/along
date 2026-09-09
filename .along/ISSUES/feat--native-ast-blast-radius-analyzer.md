---
protocol: along
slug: native-ast-blast-radius-analyzer
type: feat
status: open
priority: medium
created: 2026-09-09
updated: 2026-09-09
agent: antigravity
tags: [blast-radius, ast, code-intelligence, analysis, zero-mcp]
milestone: v3.1.0-native-ast-and-cursor-parity
blocked_by: []
related: [debt--unpinned-mcp-and-ghost-wiki-query-tool]
---

# Native In-Process AST Blast Radius Analyzer

## 1. Problem Statement

Evaluating the systemic blast radius of code changes currently relies on the external `code-review-graph` MCP server.

During real-world execution on developer machines (especially Windows):
1. The external MCP server frequently experiences stdio deadlocks, launch timeouts, or connection drops, forcing the agent to fall back to static search.
2. The current fallback procedure relies on unstructured regex/grep text search (`grep_search` across callers, imports, and references).
3. Plain text grep generates numerous false positives (comments, docstrings, variable names with the same token) and cannot identify semantic call paths or import dependencies.

Along requires an internal, zero-dependency code-intelligence engine that analyzes import and call graphs directly within the Along CLI without relying on external MCP processes.

## 2. Proposed Architecture

Implement `alongkit/blast.py` and register command `along blast-radius [PATH]` (or `along blast <PATH>`):

```text
along blast-radius scripts/alongkit/textio.py [--json] [--depth 2]
```

### Core Components:
1. **Python AST Dependency Parser (`alongkit.blast.python_ast`)**:
   - Uses standard library `ast` module.
   - Parses `import ...` and `from ... import ...` statements across repository Python files to construct an in-memory directed dependency graph.
   - Scans function and class definitions, attributes, and call expressions to identify callers of symbols defined in modified files.
2. **JavaScript / TypeScript Import Scanner (`alongkit.blast.js_imports`)**:
   - Fast regex-based scanner for ESM `import ... from '...'` and CommonJS `require('...')`.
   - Resolves relative path references and package entries.
3. **Deterministic Output & Documentation Mapping**:
   - Returns a structured list of:
     - Directly affected files (direct importers / callers).
     - Downstream transitive callers up to `--depth`.
     - Associated Knowledge Base topic files (`docs/topic--<slug>.md`) mapped via AST symbol occurrences.
   - Generates clean markdown summaries suitable for session logs and code review checklists.

## 3. Requirements

- REQ-1: Implement `alongkit/blast.py` with zero external pip runtime dependencies (pure Python standard library).
- REQ-2: Support Python AST import and call-graph tracing with sub-250ms execution on medium repositories.
- REQ-3: Support JavaScript/TypeScript import graph resolution.
- REQ-4: Expose CLI command `along blast-radius <path>` with human-readable and `--json` output formats.
- REQ-5: Integrate with `along-wrap` and `skills/along-wrap/SKILL.md` as the primary built-in blast-radius provider.
- REQ-6: Add comprehensive test suite in `tests/test_blast_radius.py`.

## 4. Acceptance Criteria

- [ ] `along blast-radius <file>` identifies direct and transitive importers.
- [ ] Symbol callers detected via AST parsing without running code.
- [ ] JSON output schema validated.
- [ ] Operates in < 300ms without spawning external background servers.
- [ ] Unit and behavioral tests pass hermetically across platforms.
