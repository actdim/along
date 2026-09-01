---
protocol: along
protocol_version: "2.2.9"
slug: INDEX
title: Knowledge Base Topic Index
type: index
created: 2026-09-01
updated: 2026-09-01
tags: [index, kb, topics, map]
---

# Knowledge Base Topic Index

Central entry point and cross-linked topic catalog for project documentation:

## Knowledge Graph & Topic Map

```mermaid
flowchart TD
    INDEX["Knowledge Base (INDEX)"]
    T_ARCHITECTURE["System Architecture & Flow"]
    INDEX --> T_ARCHITECTURE
    T_DEPENDENCIES["Dependencies & Submodules AI Documentation and Rules"]
    INDEX --> T_DEPENDENCIES
    T_DOMAIN_MODEL["Domain Model & Entity Ecosystem"]
    INDEX --> T_DOMAIN_MODEL
    T_FRONTEND_FRAMEWORKS["Frontend Architecture, Dynstruct, MsgMesh & NSwag Integration"]
    INDEX --> T_FRONTEND_FRAMEWORKS
    T_LLM_WIKI_ARCHITECTURE["LLM-Wiki Knowledge Base Architecture & Paradigm"]
    INDEX --> T_LLM_WIKI_ARCHITECTURE
    T_MIGRATIONS["Protocol & Repository Migrations Guide"]
    INDEX --> T_MIGRATIONS
    T_SETUP_AND_WORKFLOW["Setup & Developer Workflow"]
    INDEX --> T_SETUP_AND_WORKFLOW
    T_SKILLS_REFERENCE["Skills & Slash Commands Technical Reference"]
    INDEX --> T_SKILLS_REFERENCE
    T_ARCHITECTURE -.->|references| T_SETUP_AND_WORKFLOW
    T_LLM_WIKI_ARCHITECTURE -.->|references| T_ARCHITECTURE
    T_LLM_WIKI_ARCHITECTURE -.->|references| T_DOMAIN_MODEL
    T_LLM_WIKI_ARCHITECTURE -.->|references| T_SKILLS_REFERENCE
    T_LLM_WIKI_ARCHITECTURE -.->|references| T_SETUP_AND_WORKFLOW
```

---

## Articles

- **[System Architecture & Flow](./topic--architecture.md)** (architecture) `architecture`, `boundaries`, `multi-agent`, `blackboard`, `concurrency`, `mcp`, `flow`
- **[Dependencies & Submodules AI Documentation and Rules](./topic--dependencies.md)** (topic) `dependencies`, `ai-context`, `submodules`, `vendor`, `rules`
- **[Domain Model & Entity Ecosystem](./topic--domain-model.md)** (domain-model) `domain-model`, `entities`, `schemas`, `dag`, `metadata`, `issues`, `milestones`, `risks`, `spikes`, `checklists`, `sessions`
- **[Frontend Architecture, Dynstruct, MsgMesh & NSwag Integration](./topic--frontend-frameworks.md)** (topic) `dynstruct`, `dynstruct-mui`, `msgmesh`, `utico`, `react`, `mui`, `nswag`, `openapi`, `architecture`
- **[LLM-Wiki Knowledge Base Architecture & Paradigm](./topic--llm-wiki-architecture.md)** (topic) `llm-wiki`, `architecture`, `knowledge-base`, `token-efficiency`, `indexing`, `methodology`, `search`, `karpathy`
- **[Protocol & Repository Migrations Guide](./topic--migrations.md)** (topic) `migrations`, `upgrade`, `protocol`, `changelog`, `versioning`
- **[Setup & Developer Workflow](./topic--setup-and-workflow.md)** (setup-workflow) `setup-workflow`, `installation`, `lifecycle`, `runners`, `developer-workflow`, `testing`
- **[Skills & Slash Commands Technical Reference](./topic--skills-reference.md)** (topic) `skills`, `commands`, `reference`, `runners`, `lifecycle`, `automation`, `multi-agent`

---

## Related Context

- [AGENTS.md](file://AGENTS.md): Active protocol conventions and rules.
- [.along/DECISIONS.md](file://.along/DECISIONS.md): Architectural Decision Records.
- [.along/ISSUES.md](file://.along/ISSUES.md): Active issue tracking board.
- [.along/HISTORY.md](file://.along/HISTORY.md): Append-only project history log.
