# Along (v2.6.1)

**The Provider-Agnostic Context & Memory Operating System for AI Coding Agents.**

One universal convention (`ALONG-PROTOCOL v2.6.1`) and automation skills suite honored natively across **Claude Code**, **Google Antigravity**, **OpenAI Codex**, and **OpenCode**.

Along eliminates **agent context amnesia**, prevents **architectural drift**, and stops **token bloat** by transforming any codebase into an AI-ready engineering workspace with durable in-repo memory, token-efficient LLM-Wiki intelligence, and autonomous multi-agent coordination.

---

## Why Along?

AI coding agents are exceptionally capable, but they start every session blind:
- **Context Amnesia**: Agents forget past architectural choices, re-invent rejected patterns, and drop active tasks across sessions.
- **Token Combustion**: Dumping monolithic context files or full directories into prompts wastes tens of thousands of tokens per turn.
- **Multi-Branch Chaos**: Parallel agents clobber shared docs, status boards, and lock files, causing painful git merge conflicts.
- **Unanchored Edits & Hallucinations**: Without strict guardrails, agents make rogue modifications, bypass test gates, and produce silent regressions.
- **Stack Friction & Tool Blindness**: Agents stumble across differing build tools, test frameworks, and release workflows. They execute noisy commands that flood context buffers with megabytes of logs, or hallucinate project-specific build invocations.

**Along fixes this by embedding a durable, machine-parseable memory layer (`.along/`), an Andrej Karpathy-style LLM-Wiki (`docs/`), and a unified lifecycle contract (`.along/scripts/`) directly into your repository.** Agents read past decisions, track issues in a DAG, plan autonomously, and verify their own work before committing.

---

## Core Value Proposition

| Pillar | How Along Delivers It |
| :--- | :--- |
| **Persistent In-Repo Memory** | Durable, git-tracked memory (`.along/`): DAG issues, append-only ADR logs, milestones, risks, and session records that travel with the codebase. |
| **Autonomous Multi-Agent Teams** | Sequential living-plan state machine (`along-team`): Supervisor -> Scout -> Architect -> Implementer -> Reviewer with session blackboards, hard retry limits, and single-agent degradation. |
| **Token-Efficient LLM-Wiki (`docs/`)** | Modular knowledge base with in-place source provenance, SHA-256 drift detection, deterministic `llms.txt` compilation, and targeted snippet search (`along-kb-search`) avoiding full-file context ingestion. |
| **Stack-Agnostic Lifecycle & Polyglot Hooks** | Unified agent execution contract (`/along-build`, `/along-test`, `/along-dev`, `/along-version-bump`, `/along-dep-scan`) with zero-config stack auto-detection and polyglot repository hooks (`.along/scripts/` in Python, Bash, PowerShell, Batch). |
| **Zero-Conflict Git Concurrency** | Single Source of Truth (SSOT) atomic files vs compiled projections (`ISSUES.md`, `INDEX.md`), union merges (`merge=union`), and decentralized date-slug ADRs that never collide in parallel branches. |
| **Engineering Provenance & Dual-Track UI** | Living plans, fix loops, and verification gates are permanently recorded in session logs while projecting interactive visual review cards in IDEs (Antigravity). |
| **Strict Data Safety & Verification Gates** | Hermetic engines (`alongkit`) with transactional byte-exact rollbacks, strict front-matter preservation (`ruamel.yaml`), and zero-unintended-deletions invariant. |
| **Nearest Context Boundary** | Monorepos, microservices, and Git submodules maintain isolated localized memory, preventing root workspace pollution. |

---

## Using Along in Your Projects? (Drop-In Blurb)

Add this badge and blurb to the `README.md` of any repository powered by Along:

````markdown
### AI Development: Powered by [Along](https://github.com/actdim/along)

This repository follows the **Along Protocol** for AI agent context, persistent memory, and autonomous workflows:
- **Persistent In-Repo Memory**: Past architectural decisions (`.along/DECISIONS.md`), active constraints (`.along/CONSTRAINTS.md`), active issues, and session history survive across all AI sessions.
- **Token-Efficient Knowledge Base**: Structured LLM-Wiki documentation in `docs/` minimizes context overhead and eliminates architectural drift.
- **Standardized Lifecycle Contract**: Unified commands for build, test, dev, release, and dependency discovery via pluggable `.along/scripts/` hooks.
- **Provider-Agnostic**: Compatible out of the box with **Claude Code**, **Google Antigravity**, **OpenAI Codex**, and **OpenCode**.
````

---

## Quickstart & Installation

Install Along across all supported AI providers with a single command:

### Windows (PowerShell)
```powershell
git clone https://github.com/actdim/along.git
cd along
powershell -NoProfile -ExecutionPolicy Bypass -File install.ps1 -Target all
```

### Linux / macOS (Bash)
```bash
git clone https://github.com/actdim/along.git
cd along
bash install.sh --target=all
```

An install records what it wrote in `~/.along/install-manifest.json`: it never deletes a
directory it does not own, so rules you wrote yourself survive every re-install, and
`install.ps1 -Uninstall` / `./install.sh --uninstall` removes exactly that record and
nothing else. See [Setup, Installation & Workflows](./docs/topic--setup-and-workflow.md).

---

## Knowledge Base & Architecture Index

The repository's complete technical specification is maintained as a living LLM-Wiki in [`docs/`](./docs/INDEX.md):

| Topic | Description | Link |
| :--- | :--- | :--- |
| **System Architecture** | Provider flow, context boundaries, MCP servers, and bridge layers. | [System Architecture & Flow](./docs/topic--architecture.md) |
| **Domain Model & Entities** | Machine-parseable schemas for Issues, ADRs, Milestones, and Risks. | [Domain Model & Entity Ecosystem](./docs/topic--domain-model.md) |
| **Setup & Workflows** | Installation matrix, repository onboarding, and session lifecycle. | [Setup, Installation & Workflows](./docs/topic--setup-and-workflow.md) |
| **LLM-Wiki Architecture** | Andrej Karpathy paradigm, source isolation, and token efficiency. | [LLM-Wiki Architecture & Paradigm](./docs/topic--llm-wiki-architecture.md) |
## Automation Skills Reference (Grouped by Workflow Phase)

Along provides **18 singular automation skills** structured across 6 core lifecycle phases:

### 1. Bootstrap & Repository Protocol Management
| Skill / Command | Purpose |
| :--- | :--- |
| **`along-init`** (`/along-init`) | Scaffold/refresh `AGENTS.md` + `CLAUDE.md` + `.along/` in a folder. |
| **`along-update`** (`/along-update`) | One-liner update of repository context, protocol, and global skills from GitHub. |
| **`along-version-bump`** (`/along-version-bump`) | Multi-stack version bump and release orchestrator (Node, Python, Rust, .NET). |

### 2. Orchestration, Planning & Multi-Agent Teams
| Skill / Command | Purpose |
| :--- | :--- |
| **`along-team`** (`/along-team`) | Sequential multi-agent autonomous development engine and living plan. |
| **`along-issue-sync`** (`/along-issue-sync`) | Reconcile active issue board projection (`ISSUES.md`) with atomic issue files. |
| **`along-decision-sync`** (`/along-decision-sync`) | Record ADRs into append-only `.along/DECISIONS.md` and compile active `.along/CONSTRAINTS.md`. |

### 3. Development & Lifecycle Execution Runners
| Skill / Command | Purpose |
| :--- | :--- |
| **`along-build`** (`/along-build`) | Project build lifecycle hook via `.along/scripts/build.py` or auto-detected runner. |
| **`along-test`** (`/along-test`) | Automated test suite with quiet flags via `.along/scripts/test.py` or runner. |
| **`along-dev`** (`/along-dev`) | Local development/debugging server via `.along/scripts/dev.py` or runner. |

### 4. Quality Gates, Code Graph & Commit Integrity
| Skill / Command | Purpose |
| :--- | :--- |
| **`along-commit`** (`/along-commit`) | Smart ASCII-clean Conventional Committer linked to active `.along/` issue. |
| **`along-graph-check`** (`/along-graph-check`) | Preflight health check and verification for `code-review-graph` MCP server. |
| **`along-dep-scan`** (`/along-dep-scan`) | Scan declared dependencies for AI instructions into `docs/topic--dependencies.md`. |
| **`along context-budget`** (`along budget`) | Context budget measurement and regression gate (`--check`, `--json`). |

### 5. Knowledge Base & LLM-Wiki Intelligence
| Skill / Command | Purpose |
| :--- | :--- |
| **`along-kb-sync`** (`/along-kb-sync`) | Idempotent LLM-Wiki Knowledge Base compiler and link integrity gate in `docs/`. |
| **`along-kb-search`** (`/along-kb-search`) | Fast targeted snippet search across `docs/` and project memory. |

### 6. Visual Analytics, History & Diagnostics
| Skill / Command | Purpose |
| :--- | :--- |
| **`along-dash`** (`/along-dash`) | Launch executive dashboard (Web UI, CLI, Cytoscape DAG, HTML export). |
| **`along-history-sync`** (`/along-history-sync`) | Reconstruct `.along/` milestones, issues, and sessions from Git commits. |
| **`along-feedback`** (`/along-feedback`) | System self-diagnostics, incident logging, and feedback dispatch. |
| **`along-wrap`** (`/along-wrap`) | Unified end-of-stage wrap: verification checklist, session log, issues, history. |

---

## License

MIT License. See [LICENSE](./LICENSE) for details.
