---
protocol: along
protocol_version: "4.4.11"
doc_type: vision
sources:
  - AGENTS.md
  - README.md
  - docs/INDEX.md
---

# Vision

_North star: scope, boundaries, non-goals, roadmap. Evolves slowly; slims as features ship._

## Scope

ActDim Along is a provider-agnostic, zero-friction agent memory, documentation, and project governance protocol and skills suite for AI coding assistants (Claude Code, Google Antigravity, OpenAI Codex, OpenCode). Along equips repositories with:

1. **Dual-Tier Memory Architecture**:
   - **Evergreen Knowledge Base (`docs/`)**: Curated Andrej Karpathy-style LLM-Wiki with AST code symbol grounding, in-place source provenance, and SHA-256 drift detection.
   - **Living Project Memory (`.along/`)**: Structured, git-native transactional memory across sessions and tools, tracking DAG issues, decentralized ADRs, milestones, risks, and session blackboards.
2. **Zero-Vector Unified In-Repo Retrieval (`along-kb-search`)**: Fast local TF-IDF search engine indexing documentation, ADR constraints, active issues, and session logs into bounded snippets (<= 150 words) without external vector databases or cloud daemons.
3. **Mechanical Runtime Gates**: Interception layer enforcing declarative runtime gates in `default_gates.yaml` (32 protocol invariants enforced across runtime hooks, git hooks, and CI) with bi-directional traceability.
4. **Ephemeral Workspace Isolation**: Git worktree sandboxing with automated dependency junctions (`node_modules`, `.venv`) to prevent dirty working tree contamination during agent execution.
5. **Zero-Conflict Git Concurrency**: Custom merge drivers (`along git setup`), union merges, and atomic metadata files preventing Git merge conflicts across parallel branches and multi-agent sessions.
6. **21-Skill Automation Suite (`skills/`)**:
   - Context and Setup: `along-init`, `along-update`
   - Memory and Lifecycle: `along-wrap`, `along-feedback`, `along-history-sync`
   - Issue and Decision Governance: `along-issue-sync`, `along-decision-sync`
   - Knowledge Base and Retrieval: `along-kb-sync`, `along-kb-search`
   - Code Graph and Blast Radius: `along-graph-sync`, `along-graph-check`, `along-graph-impact`, `along-graph-arch`
   - Execution and Verification: `along-build`, `along-test`, `along-dev`, `along-commit`, `along-version-bump`
   - Workspace, Dependencies and Teams: `along-dep-scan`, `along-team`, `along-dash`

## Along Core and Modular Extras Architecture

To maintain reliability, rapid verification, and zero bloat, Along cleanly separates minimal Core capabilities from optional extras (see ADR: Core and Modular Extras Architecture):

### 1. Along Core (`actdim-along`)
- **Memory Layout**: Git-native transactional memory (`.along/`) with atomic entity files (`ISSUES/`, `DECISIONS/`, `MILESTONES/`, `SESSIONS/`), compiled projections (`ISSUES.md`, `CONSTRAINTS.md`, `docs/INDEX.md`), and lifecycle scripts (`.along/scripts/`).
- **Retrieval**: Zero-vector local TF-IDF search (`along-kb-search`) returning bounded snippets (<= 150 words) across `docs/` and `.along/` without external vector databases or daemon processes.
- **Lifecycle and Verification Contracts**: Unified lifecycle commands (`along-build`, `along-test`, `along-dev`), issue-bound conventional commits (`along-commit`), and transactional session wrapping (`along-wrap`).
- **Essential Mechanical Gates**: Active issue binding (`require-active-issue`), plan approval (`require-plan-approval`), ASCII typography cleanliness, projection protection, and commit issue binding, enforced via runtime hooks and portable baseline git hooks/CI (`along gates check`).
- **Minimal Core Dependencies**: Runtime dependencies are restricted strictly to `ruamel.yaml>=0.18`.

### 2. Modular Extras and Extensions
- **Web Dashboard and Analytics (`actdim-along[dash]`)**: Executive web dashboard, Cytoscape DAG visualization, and OpenAPI service (FastAPI, Uvicorn, Pydantic, Rich).
- **Telemetry and Tracing (`actdim-along[telemetry]`)**: OpenTelemetry / OpenInference tracing and remote OTLP export tooling.
- **Full Suite (`actdim-along[all]`)**: Installs all optional extras (`actdim-along[dash,telemetry]`).
- **Modular Protocol Capabilities**: Advanced extensions like `along-team` multi-agent loops, git worktree sandboxing, `along-graph-sync` AST code review graphs, and `along-dep-scan` operate with zero extra runtime package dependencies.

### 3. Installation Matrix
- Core only: `pip install actdim-along`
- Core + Dashboard: `pip install actdim-along[dash]`
- Core + Telemetry: `pip install actdim-along[telemetry]`
- All extensions: `pip install actdim-along[all]`

### 4. Protocol Versioning Policy
- **Protocol Version**: The protocol specification version (`ALONG-PROTOCOL vX.Y.Z`) increments ONLY upon format, schema, or structural protocol changes.
- **Toolchain Features**: New features and non-breaking capabilities release as minor toolchain versions.
- **Breaking Format Changes**: Batched into rare major releases accompanied by automated migrations (`along migrate`).
- **Fixes and Hardening**: Bug fixes and documentation improvements release as patch versions.

## Non-goals

- **No Proprietary Vendor Lock-in**: Never rely on tool-specific closed formats. Everything is stored in plain Markdown, YAML frontmatter, and JSON, operating seamlessly across Claude Code, Google Antigravity, OpenAI Codex, OpenCode, and standard shells.
- **No Context Bloat**: Never load full project history or entire directories into active agent contexts. Maintain bounded snippet retrieval (`along-kb-search`) and compact compiled projections (`ISSUES.md`, `CONSTRAINTS.md`, `docs/INDEX.md`).
- **No Manual Admin Overhead**: Humans should never be required to write metadata or manually maintain project tracking files. Agents infer, record, and recompile project state automatically.
- **No Monolithic Platform Bloat**: Along Core stays minimal, provider-agnostic, Git-native, and plain-text. Along is not a heavyweight enterprise management platform or closed cloud orchestrator.
- **No Unmeasured Enterprise Extras in Core**: Optional extensions (dashboard, telemetry, circuit breakers, autonomous team runners, worktree isolation, chat gateways) belong in modular extras, preventing runtime protocol inflation and dependency bloat in core.
- **No External Vector DB or Cloud Daemon Dependencies**: Project memory and retrieval operate completely in-repo with local file access; no external database servers, embedding APIs, background daemons, or cloud subscriptions are required.

## Strategic Horizons & Roadmap

Granular iteration progress, release milestones, and active task DAGs are tracked dynamically in `.along/MILESTONES/` and `.along/ISSUES/` (compiled into `.along/ISSUES.md`).

`VISION.md` governs long-term architectural horizons rather than day-to-day tickets:

1. **Foundation & Dual-Tier Memory (Shipped - v1.x - v3.x)**: Git-native transactional memory (`.along/`), Andrej Karpathy-style LLM-Wiki (`docs/`), bounded TF-IDF retrieval (`along-kb-search`), and executive dashboard (`along-dash`).
2. **Mechanical Safety & Isolation (Shipped - v4.0 - v4.5)**: Declarative runtime gates (`PreToolUse`, `Stop`), ephemeral git worktree sandboxing, test-gated merge automation (`along git setup`), and zero-manual-merge projection compilers.
3. **Structured Execution & Resilient Agent Loops (Active - v4.6 - v4.7)**: Deterministic blackboard state transitions (`along scratch patch`), clean-turn context isolation, bounded step prompt budgets, and automated zero-step drift recovery in `along-team`.
4. **Ecosystem & Cross-Runtime Expansion (Next - v4.8+)**: Empirical benchmarks, multi-language support (C++, Rust, Go, JVM), multi-runtime orchestration (Claude Code, Google Antigravity, OpenAI Codex, OpenCode), and enterprise governance packs.
