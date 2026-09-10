---
protocol: along
slug: token-efficiency-and-context-optimization-skills
type: feat
status: superseded
completed: 2026-09-10
priority: high
created: 2026-08-13
updated: 2026-09-10
agent: antigravity
tags: []
milestone: v1.5.0-dashboard-and-analytics
blocked_by: []
related: []
superseded_by: debt--agents-md-context-budget-pruning
---

# Token Efficiency & Context Window Optimization System

## Goal
Design and implement a comprehensive set of strategies, skills, and prompt optimizations across the protocol and skill suite to minimize token consumption and maximize context window efficiency across all AI agents.

## Problem Statement
AI agents start every turn reading project instructions, skills, issue boards, and code files. Large system prompts, uncompressed skill definitions, and full-file view reads consume context budget rapidly, leading to higher API costs and loss of long-term memory accuracy.

## Proposed Optimization Strategies

### 1. Progressive Disclosure & Ultra-Lean `SKILL.md` Architecture
- Keep main `SKILL.md` instruction files ultra-lean (~30-50 lines max).
- Move bulky reference material, detailed runbooks, and large examples into a `references/` subdirectory.
- Ensure agents load reference docs only when specifically executing that sub-procedure.

### 2. System Prompt & Customization Compression
- Optimize the protocol blocks stamped into `AGENTS.md` and global rules.
- Eliminate repetitive instruction boilerplate across skills.
- Use macro signposts and ancestor REF blocks for subfolders instead of duplicating rules.

### 3. Targeted Code & Memory Extraction (Minimal Context)
- **Vector Search for Issues & Memory**: Use SQLite vector embeddings (`add-sqlite-vector-indexing`) to query only relevant issue/decision snippets instead of reading entire boards.
- **Minimal Code Subgraphs**: Use `code-review-graph` MCP tools (`get_minimal_context_tool`, `get_impact_radius_tool`) to load only affected functions instead of full files.
- **Line Slicing**: Enforce line-range reading (`StartLine`/`EndLine`) for code inspection rather than reading entire source files.

### 4. Continuous Context Compaction Lifecycle
- Enforce strict size limits on `.along/CONTEXT.md` (~1 screen max).
- Automatically flush detailed execution logs to per-session files (`.along/SESSIONS/`) to keep active context clean.

## Acceptance Criteria
- [ ] Guidelines added to the protocol for writing ultra-lean, progressive-disclosure skills.
- [ ] Protocol blocks and skill front-matter audited for token compactness.
- [ ] Context compaction and minimal-read rules integrated into all skill workflows.
