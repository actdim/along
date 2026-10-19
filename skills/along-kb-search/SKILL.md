---
name: along-kb-search
description: Fast unified retrieval engine across Knowledge Base (docs/) and living project memory (.along/ISSUES, DECISIONS.md, MILESTONES, SESSIONS). Minimizes agent context tokens during research, blast radius analysis, and decision-making. Use when invoking /along-kb-search.
---

# Along KB Search

Unified Multi-Scope Knowledge & Memory Retrieval Engine for AI coding agents and developers.

## Retrieval Guidance

To keep latency and prompt context low:
1. **Search Before Scanning**: Query `along kb-search` before scanning `docs/` or `.along/` with directory search tools; a targeted grep is fine once you know what to look for.
2. **No Speculative File Reading**: Agents MUST NOT open and read whole files sequentially with `view_file` to search for concepts. Query `along kb-search` first, then inspect only the specific target file if edits are required.
3. **Single-Shot Invocation**: Agents MUST execute the deterministic search engine in a single command.

## Usage

```bash
along kb-search "<query>" [--category all|kb|issue|decision|milestone|session] [--archive|-a] [--limit 8] [--tag <tag>] [--any] [--prefix] [--stats]
```

Fallback when `along` is not in system PATH:
```bash
python ~/.along/bin/along_exec.py kb-search "<query>" [--archive|-a]
```
*(Or in repository root: `python scripts/along_exec.py kb-search "<query>" [--archive|-a]`)*

### Default Scope & Archive Filtering
By default (`--category all`), search targets current, active knowledge:
- Curated domain documentation (`docs/topic--*.md`, ranked with priority boost)
- Active and accepted ADRs (`.along/DECISIONS/`)
- Open and in-progress issues (`.along/ISSUES/`, spikes and `risk`-tagged issues included)
- Milestones

Historical and archived scopes are excluded by default to prevent stale records from dominating results:
- Completed session logs (`.along/SESSIONS/**/*.md`)
- Completed, done, or cancelled issues (`.along/ISSUES/done/`)
- Superseded, retired, or deprecated ADRs

To include archived entities, pass `--archive` (or `-a`).
Explicit category queries (such as `--category session` or `--category issue`) include historical records for that category without needing `--archive`.

## Capabilities & Scopes
1. **Curated Domain Wiki (`docs/*.md`)**: System architecture, domain model, workflows, guides, and engineering rules.
2. **Issues & Bug Tracker (`.along/ISSUES/**/*.md`)**: Active tickets, backlog, and completed tasks with live status, priority, and tags. Spikes (`spike--<slug>`, with `## Outcome`) and risks or blockers (issues tagged `risk`, with `## Mitigation`) are issues too.
3. **Architectural Decisions (`.along/DECISIONS.md`)**: ADR records, rationale, constraints, and superseded decisions.
4. **Milestones & Sprints (`.along/MILESTONES/*.md`)**: Release targets, due dates, and progress metrics.
5. **Work Session Logs (`.along/SESSIONS/**/*.md`)**: Historical logs, diff evaluations, and blast radius summaries.

## Token Hygiene & Agent Decision Making
Instead of reading entire project documents into prompt context during analysis or blast radius evaluation, agents invoke `along kb-search "<query>"` to retrieve concise, word-boundary aligned context snippets in milliseconds (typically < 150 tokens).
