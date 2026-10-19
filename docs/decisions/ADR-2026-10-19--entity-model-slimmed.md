---
protocol: along
slug: entity-model-slimmed
type: decision
title: "Entity model slimmed: spike is an issue type, risks and checklists retired"
date: 2026-10-19
status: accepted
tags: [adr, architecture, decision]
---

# ADR-2026-10-19--entity-model-slimmed - Entity model slimmed: spike is an issue type, risks and checklists retired

- Date: 2026-10-19
- Status: accepted
- Context: Measured on 2026-10-17 across along, dotnet and mempart: 1 risk record in total, 3 spikes, checklists only as never-read scaffold, and session logs that repeat git (attributed files table) and the plan. Each entity type costs schema, scaffolding, validation, kb-search, dashboard and protocol text. Subprojects collected empty VISION/GLOSSARY stubs and empty RISKS/SPIKES/CHECKLISTS folders. [debt--entity-model-slimming]
- Decision: 1. Issue types are feat|bug|debt|task|docs|spike; a spike is .along/ISSUES/spike--<slug>.md with an ## Outcome section. 2. The Risk type is removed: a risk or blocker is an issue (usually debt) tagged risk with a ## Mitigation section. 3. The Checklist type is removed: the completion checklist lives in AGENTS.md and is printed by along wrap; custom checklists are docs. 4. Migration Step 16 converts RISKS/ and SPIKES/ records into issues, rewrites front-matter references, discards the two scaffolded checklists and moves others to docs/, with a backup; it also runs on repositories already at the current version. 5. A session log keeps front matter, summary, decisions and the blackboard record (steps, research, trace, notes, reviews); attributed paths move to the files: front matter, which closeout reads (the legacy table is still read); the plan is not copied. 6. along session gc archives and removes blackboards of closed issues. 7. Nested contexts get no GLOSSARY.md or VISION.md skeleton on init; files are created on first use. 8. HISTORY.md stays one line per slug, through one writer.
- Consequences: Fewer folders and schemas; one board for all work, spikes included. Old logs are not rewritten (append-only gate) and still parse. A wrapped issue's approved plan survives only in the user's plan file and git history. The dashboard still has empty risk/spike collectors until the core/extras split removes them. Supersedes the risk/spike/checklist parts of ADR-2026-08-27--protocol-v150-automated-entities-and-intent-heuristics.
