---
protocol: along
protocol_version: "2.2.27"
date: 2026-09-09
slug: pluggable-lifecycle-hooks-showcase
agent: antigravity
branch: main
commit: pending
summary: Elevate pluggable lifecycle hooks as core feature and agent directives
milestone: v3.0.0-global-quality-revision
issues_advanced: []
issues_completed: [docs--pluggable-lifecycle-hooks-showcase]
decisions: []
risks_logged: []
spikes_conducted: []
---

# Session: Pluggable lifecycle hooks showcase

## Summary
Addressed user request to elevate Along's pluggable repository execution hooks (`.along/scripts/` supporting `.py`, `.sh`, `.ps1`, `.bat`) into a prominent selling feature and ensure AI coding agents naturally adopt and prioritize them. Updated `README.md` to highlight "Stack Friction & Tool Blindness" and introduced the 8th pillar "Stack-Agnostic Lifecycle & Polyglot Hooks" to the Core Value Proposition. Codified the mandatory Contract-First Lifecycle Execution rule in `skills/along-init/protocol.md` and synchronized the managed block in `AGENTS.md`. Documented custom dependency scanner hooks in `docs/topic--dependencies.md`, the `alongkit.lifecycle` subsystem in `docs/topic--architecture.md`, and expanded Section 4 in `docs/topic--setup-and-workflow.md`. Aligned all documentation articles to `protocol_version: "2.2.27"`, recompiled `docs/INDEX.md` and `llms-full.txt`, and verified 100% pass across 328 hermetic tests while staying within context budget limits.

## Work Completed
1. **Public Showcase & Marketing Surfaces (`README.md`)**:
   - Added pain point `Stack Friction & Tool Blindness` to the "Why Along?" section.
   - Added 8th pillar `Stack-Agnostic Lifecycle & Polyglot Hooks` to the "Core Value Proposition" table.
   - Updated the Drop-In Blurb to highlight the standardized lifecycle contract.
2. **Protocol & Agent Directives (`skills/along-init/protocol.md`, `AGENTS.md`)**:
   - Added `Contract-First Lifecycle Execution` directive under "While working".
   - Updated step 1 of "Mandatory Stage & Session Completion Checklist" to mandate executing tests via lifecycle hooks (`/along-test`, `python .along/scripts/test.py`, `/along-build`).
   - Added `Contract-First Lifecycle Execution & Polyglot Hooks` rule defining nearest-hook priority, zero-config auto-synthesis, and subproject hook localization.
   - Synchronized `AGENTS.md` managed block with 1-to-1 parity against `skills/along-init/protocol.md`.
   - Streamlined `AGENTS.md` "Project specifics" to ensure the file strictly satisfies the 32 KB context budget limit (`agents_md_bytes <= 32768`).
3. **Knowledge Base Documentation (`docs/`)**:
   - Added `Custom Project Dependency Hooks (.along/scripts/dep_scan.py)` to `docs/topic--dependencies.md` with CLI contract and output JSON schema.
   - Added Section 10 `Lifecycle & Polyglot Hook Architecture (alongkit.lifecycle)` to `docs/topic--architecture.md` with Mermaid diagram and design principles.
   - Expanded Section 4 in `docs/topic--setup-and-workflow.md` with full hook matrix, polyglot interpreter selection table, safe `argv` list passing (`shell=False`), and `# Status: verified` vs `# Status: unconfigured` status tags.
   - Clarified hook precedence in `docs/topic--skills-reference.md`.
   - Aligned `protocol_version: "2.2.27"` across all 9 `docs/*.md` articles.
   - Recompiled `docs/INDEX.md` and `llms-full.txt` via `python scripts/along_kb_sync.py`.
4. **Issue Management**:
   - Created and completed `docs--pluggable-lifecycle-hooks-showcase`, moved to `.along/ISSUES/done/`, and updated `.along/ISSUES.md`.

## Code Review & Blast Radius Assessment
- **Modified Surfaces**: Documentation (`README.md`, `docs/`, `llms-full.txt`), protocol source (`skills/along-init/protocol.md`, `AGENTS.md`), issue files, and history log.
- **AST Impact & Code Graph**:
  `[CRITICAL WARNING: code-review-graph OFFLINE, degraded to static search]`
  Code Review Graph timed out on Windows; degraded to static verification. Zero implementation code in `scripts/` or `packages/` was changed. All changes were to markdown documents and YAML front-matter.
- **Verification**:
  - Hermetic tests: `python .along/scripts/test.py` -> 328 tests passed (`OK (skipped=1)`).
  - Context budget: `python .along/scripts/test.py tests/test_context_budget.py` -> passed.
  - Typography gate: `python scripts/sanitize_typography.py` -> 302 files scanned, 0 banned characters.
  - KB link integrity: `python scripts/along_kb_sync.py --check` -> executed cleanly.
