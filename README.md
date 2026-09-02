# Along (v2.2.17)

A provider-agnostic **agent-context and memory system** for software repositories - the `ALONG-PROTOCOL v2.2.17` plus the automation skills suite that scaffolds and maintains it. One unified convention, honored natively across **Claude Code**, **OpenAI Codex**, **OpenCode**, and **Google Antigravity**.

---

## Why Along?

AI coding agents start every session blind. They lack persistent memory of past architectural decisions, work in progress, open issues, or repository conventions. Each tool maintains its own isolated configuration (`~/.claude`, `~/.codex`, `~/.config/opencode`, `~/.gemini/config`), leading to context loss and fragmented workflows.

**Along fixes this by giving the repository an isolated, durable, human-readable memory directory (`.along/`) and a structured Knowledge Base (`docs/`) that all agents read and maintain collaboratively.**

---

## Core Value Proposition

- **Persistent In-Repo Memory**: DAG issue tracking, append-only ADR log, milestones, risks, and session logs committed with the code.
- **Provider-Agnostic Single Protocol**: Write conventions once in `AGENTS.md`; Claude Code, Codex, OpenCode, and Antigravity follow them identically.
- **LLM-Wiki Knowledge Base (`docs/`)**: Modular, cross-linked topic articles with isolated raw source archival (`.archive/`) and 95-98% token reduction on retrieval.
- **Nearest Context Boundary**: Strict isolation for monorepos, microservices, and Git submodules preventing root workspace pollution.
- **Zero Bookkeeping Overhead**: 18 automation skills handle scaffolding, sync, commit checks, and stage wrap-ups in the background.

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
| **`along-decision-sync`** (`/along-decision-sync`) | Append structured architectural decisions (ADRs) to `.along/DECISIONS.md`. |

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
| **`along-graph-check`** (`/along-graph-check`) | Inspect `code-review-graph` AST impact radius (blast radius) and caller flows. |
| **`along-dep-scan`** (`/along-dep-scan`) | Scan declared dependencies for AI instructions into `docs/topic--dependencies.md`. |

### 5. Knowledge Base & LLM-Wiki Intelligence
| Skill / Command | Purpose |
| :--- | :--- |
| **`along-kb-sync`** (`/along-kb-sync`) | Idempotent LLM-Wiki Knowledge Base compiler and link integrity gate in `docs/`. |
| **`along-kb-search`** (`/along-kb-search`) | Fast targeted snippet search across `docs/` and project memory (<100 tokens). |

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
