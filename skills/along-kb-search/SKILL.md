---
name: along-kb-search
description: Fast unified retrieval engine across Knowledge Base (docs/) and living project memory (.along/ISSUES, DECISIONS.md, MILESTONES, RISKS, SESSIONS). Minimizes agent context tokens during research, blast radius analysis, and decision-making. Use when invoking /along-kb-search.
---

# Along KB Search  [v2.2.20]

Unified Multi-Scope Knowledge & Memory Retrieval Engine for AI coding agents and developers.

## Capabilities & Scopes
1. **Curated Domain Wiki (`docs/*.md`)**: System architecture, domain model, workflows, guides, and engineering rules.
2. **Issues & Bug Tracker (`.along/ISSUES/**/*.md`)**: Active tickets, backlog, and completed tasks with live status, priority, and tags.
3. **Architectural Decisions (`.along/DECISIONS.md`)**: ADR records, rationale, constraints, and superseded decisions.
4. **Milestones & Sprints (`.along/MILESTONES/*.md`)**: Release targets, due dates, and progress metrics.
5. **Risks & Blockers (`.along/RISKS/*.md`)**: External API limits, security flags, and mitigation plans.
6. **Spikes & Experiments (`.along/SPIKES/*.md`)**: R&D evaluations, hypotheses, and benchmark results.
7. **Work Session Logs (`.along/SESSIONS/**/*.md`)**: Historical logs, diff evaluations, and blast radius summaries.

## Token Hygiene & Agent Decision Making
Instead of reading thousands of tokens of project files into prompt context during analysis or blast radius evaluation, agents invoke `/along-kb-search "<term>"` to retrieve concise ~200-character context snippets in milliseconds (< 100 tokens).

## Usage
```bash
python scripts/along_kb_search.py "<query>" [--category all|kb|issue|decision|milestone|risk|spike|session] [--limit 8] [--tag <tag>]
```
*(Or `python scripts/along_exec.py kb-search` / `/along-kb-search`)*

