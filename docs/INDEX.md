---
protocol: along
slug: INDEX
title: ActDim Along - Knowledge Base Topic Index
type: index
created: 2026-09-10
updated: 2026-10-23
tags: [index, kb, topics, map]
---

# ActDim Along - Knowledge Base Topic Index

Central entry point and cross-linked topic catalog for project documentation:

## Knowledge Graph & Topic Map

```mermaid
flowchart TD
    INDEX["Knowledge Base (INDEX)"]
    T_AGENT_RUN_PROTOCOL["Agent Run Protocol (ARP/AEP) & OpenTelemetry Engine"]
    INDEX --> T_AGENT_RUN_PROTOCOL
    T_ALONG_PROTOCOL["Along Protocol Reference"]
    INDEX --> T_ALONG_PROTOCOL
    T_ARCHITECTURE["System Architecture & Flow"]
    INDEX --> T_ARCHITECTURE
    T_CLI_REFERENCE["Along CLI Command Reference"]
    INDEX --> T_CLI_REFERENCE
    T_DECLARATIVE_GATES_AND_TRACEABILITY["Declarative Gate Engine & Protocol Traceability Matrix"]
    INDEX --> T_DECLARATIVE_GATES_AND_TRACEABILITY
    T_DEPENDENCIES["Dependencies & Submodules AI Documentation and Rules"]
    INDEX --> T_DEPENDENCIES
    T_DOMAIN_MODEL["Domain Model & Entity Ecosystem"]
    INDEX --> T_DOMAIN_MODEL
    T_LICENSE["License"]
    INDEX --> T_LICENSE
    T_LLM_WIKI_ARCHITECTURE["Topic-Based Knowledge Base Architecture & Paradigm"]
    INDEX --> T_LLM_WIKI_ARCHITECTURE
    T_MIGRATIONS["Protocol & Repository Migrations Guide"]
    INDEX --> T_MIGRATIONS
    T_PARALLEL_SESSIONS["Parallel Sessions & Closeout Guide"]
    INDEX --> T_PARALLEL_SESSIONS
    T_REQUIREMENT_FORMAT["Controlled Natural Language (STE-Inspired) Requirement Format"]
    INDEX --> T_REQUIREMENT_FORMAT
    T_RUNTIME_HOOKS_AND_GATES["Runtime Lifecycle Hooks & Mechanical Gates"]
    INDEX --> T_RUNTIME_HOOKS_AND_GATES
    T_SESSION_LIFECYCLE["Session & Blackboard Lifecycle Guide"]
    INDEX --> T_SESSION_LIFECYCLE
    T_SETUP_AND_WORKFLOW["Setup & Developer Workflow"]
    INDEX --> T_SETUP_AND_WORKFLOW
    T_SKILLS_REFERENCE["Skills & Slash Commands Technical Reference"]
    INDEX --> T_SKILLS_REFERENCE
    T_SYSTEM_COMPARISONS["System Comparisons & Alternative Architectural Paradigms"]
    INDEX --> T_SYSTEM_COMPARISONS
    T_TROUBLESHOOTING["Troubleshooting & Developer Diagnostics Guide"]
    INDEX --> T_TROUBLESHOOTING
    T_ARCHITECTURE -.->|references| T_CLI_REFERENCE
    T_ARCHITECTURE -.->|references| T_SETUP_AND_WORKFLOW
    T_ARCHITECTURE -.->|references| T_SESSION_LIFECYCLE
    T_CLI_REFERENCE -.->|references| T_SETUP_AND_WORKFLOW
    T_CLI_REFERENCE -.->|references| T_RUNTIME_HOOKS_AND_GATES
    T_CLI_REFERENCE -.->|references| T_PARALLEL_SESSIONS
    T_CLI_REFERENCE -.->|references| T_SESSION_LIFECYCLE
    T_DECLARATIVE_GATES_AND_TRACEABILITY -.->|references| T_RUNTIME_HOOKS_AND_GATES
    T_DOMAIN_MODEL -.->|references| T_MIGRATIONS
    T_LLM_WIKI_ARCHITECTURE -.->|references| T_SYSTEM_COMPARISONS
    T_LLM_WIKI_ARCHITECTURE -.->|references| T_ARCHITECTURE
    T_LLM_WIKI_ARCHITECTURE -.->|references| T_DOMAIN_MODEL
    T_LLM_WIKI_ARCHITECTURE -.->|references| T_SKILLS_REFERENCE
    T_LLM_WIKI_ARCHITECTURE -.->|references| T_SETUP_AND_WORKFLOW
    T_PARALLEL_SESSIONS -.->|references| T_SESSION_LIFECYCLE
    T_PARALLEL_SESSIONS -.->|references| T_CLI_REFERENCE
    T_RUNTIME_HOOKS_AND_GATES -.->|references| T_DECLARATIVE_GATES_AND_TRACEABILITY
    T_RUNTIME_HOOKS_AND_GATES -.->|references| T_SESSION_LIFECYCLE
    T_RUNTIME_HOOKS_AND_GATES -.->|references| T_ALONG_PROTOCOL
    T_SESSION_LIFECYCLE -.->|references| T_CLI_REFERENCE
    T_SESSION_LIFECYCLE -.->|references| T_RUNTIME_HOOKS_AND_GATES
    T_SESSION_LIFECYCLE -.->|references| T_PARALLEL_SESSIONS
    T_SETUP_AND_WORKFLOW -.->|references| T_RUNTIME_HOOKS_AND_GATES
    T_SETUP_AND_WORKFLOW -.->|references| T_CLI_REFERENCE
    T_SETUP_AND_WORKFLOW -.->|references| T_ALONG_PROTOCOL
    T_SYSTEM_COMPARISONS -.->|references| T_LLM_WIKI_ARCHITECTURE
    T_SYSTEM_COMPARISONS -.->|references| T_RUNTIME_HOOKS_AND_GATES
    T_SYSTEM_COMPARISONS -.->|references| T_AGENT_RUN_PROTOCOL
    T_SYSTEM_COMPARISONS -.->|references| T_ARCHITECTURE
    T_TROUBLESHOOTING -.->|references| T_SETUP_AND_WORKFLOW
    T_TROUBLESHOOTING -.->|references| T_CLI_REFERENCE
    T_TROUBLESHOOTING -.->|references| T_RUNTIME_HOOKS_AND_GATES
```

---

## Articles

- **[Agent Run Protocol (ARP/AEP) & OpenTelemetry Engine](./topic--agent-run-protocol.md)** (architecture) `telemetry`, `opentelemetry`, `openinference`, `tracing`, `arp`, `aep`, `redactor`, `offloader`, `spool`
- **[Along Protocol Reference](./topic--along-protocol.md)** (reference) `protocol`, `agents-md`, `checklist`, `routing`, `concurrency`, `along-team`, `conventions`
- **[System Architecture & Flow](./topic--architecture.md)** (architecture) `architecture`, `boundaries`, `multi-agent`, `blackboard`, `concurrency`, `ast`, `flow`
- **[Along CLI Command Reference](./topic--cli-reference.md)** (reference) `cli`, `commands`, `router`, `lifecycle`, `tools`, `reference`
- **[Declarative Gate Engine & Protocol Traceability Matrix](./topic--declarative-gates-and-traceability.md)** (architecture) `hooks`, `gates`, `declarative`, `traceability`, `verification`, `protocol`, `predicates`
- **[Dependencies & Submodules AI Documentation and Rules](./topic--dependencies.md)** (topic) `dependencies`, `ai-context`, `submodules`, `vendor`, `rules`
- **[Domain Model & Entity Ecosystem](./topic--domain-model.md)** (domain-model) `domain-model`, `entities`, `schemas`, `dag`, `metadata`, `issues`, `milestones`, `spikes`, `sessions`
- **[License](./topic--license.md)** (license) `license`, `mit`
- **[Topic-Based Knowledge Base Architecture & Paradigm](./topic--llm-wiki-architecture.md)** (topic) `topic-based-authoring`, `diataxis`, `tf-idf`, `architecture`, `knowledge-base`, `token-efficiency`, `indexing`, `methodology`, `search`, `karpathy`
- **[Protocol & Repository Migrations Guide](./topic--migrations.md)** (guide) `migrations`, `upgrade`, `protocol`, `changelog`, `versioning`, `data-safety`
- **[Parallel Sessions & Closeout Guide](./topic--parallel-sessions.md)** (guide) `session`, `parallel`, `closeout`, `attribution`, `ledger`, `commit`, `readiness`, `approval`
- **[Controlled Natural Language (STE-Inspired) Requirement Format](./topic--requirement-format.md)** (guide) `ste`, `cnl`, `requirements`, `specifications`, `convention`, `cross-runtime`
- **[Runtime Lifecycle Hooks & Mechanical Gates](./topic--runtime-hooks-and-gates.md)** (architecture) `hooks`, `gates`, `runtime`, `enforcement`, `antigravity`, `claude`, `codex`, `typography`, `cli-safety`, `destructive-command`, `attribution`
- **[Session & Blackboard Lifecycle Guide](./topic--session-lifecycle.md)** (guide) `session`, `blackboard`, `plan`, `trace`, `wrap`, `purge`, `issue-done`, `session-log`, `gates`
- **[Setup & Developer Workflow](./topic--setup-and-workflow.md)** (setup-workflow) `setup-workflow`, `installation`, `lifecycle`, `runners`, `developer-workflow`, `testing`
- **[Skills & Slash Commands Technical Reference](./topic--skills-reference.md)** (reference) `skills`, `commands`, `reference`, `runners`, `lifecycle`, `automation`, `multi-agent`
- **[System Comparisons & Alternative Architectural Paradigms](./topic--system-comparisons.md)** (explanation) `comparisons`, `architecture`, `paradigms`, `memory`, `zero-vector`, `mechanical-gates`, `governance`, `engineering-decisions`
- **[Troubleshooting & Developer Diagnostics Guide](./topic--troubleshooting.md)** (guide) `troubleshooting`, `diagnostics`, `packaging`, `alongkit`, `uv`, `pep-723`, `api-discovery`, `anti-patterns`

---

## Related Context

- [AGENTS.md](../AGENTS.md): Active protocol conventions and rules.
- [Decisions (ADRs)](./decisions/INDEX.md): Architectural Decision Records.
- [Domain Model & Entity Ecosystem](./topic--domain-model.md): Specifications for active issues and project history.
