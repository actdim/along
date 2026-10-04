# Glossary

_Domain terms for Along and repository tracking. Add or refine terms whenever introduced._

- **ALONG-PROTOCOL** - Provider-agnostic agent memory and project management standard enabling seamless pair-programming across Claude Code, Codex, OpenCode, and Antigravity via `.along/` and `AGENTS.md`.
- **Issue** - Discrete, structured unit of work (`feat`, `bug`, `debt`, `task`, `docs`) tracked with YAML front-matter in `.along/ISSUES/` and summarized in `.along/ISSUES.md`.
- **Milestone** - Release target, stage, or sprint grouping multiple issues to measure delivery velocity and progress percentage in `.along/MILESTONES/`.
- **Risk / Blocker** - Explicitly tracked technical blocker, missing API credential, external dependency, or security risk documented in `.along/RISKS/` with mitigation plans.
- **Spike** - Exploratory research spike, benchmark evaluation, or PoC experiment documented in `.along/SPIKES/` prior to architectural decision-making.
- **Checklist** - Reusable, step-by-step verification checklist (`pre-commit`, `stage-completion`, `release`, `security`) in `.along/CHECKLISTS/` ensuring quality assurance compliance.
- **Session Log** - Immutable, structured work session record in `.along/SESSIONS/<YYYY>/<YYYY-MM-DD>--<slug>.md` capturing files touched, issues advanced/completed, ADRs, and metrics.
- **ADR (Architectural Decision Record)** - Append-only record of a non-trivial architectural or technical choice stored in `.along/DECISIONS.md`.
- **Knowledge Base (KB)** - Persistent project documentation repository in `.along/KB/` (`INDEX.md`, `01-architecture.md`, `02-domain-model.md`, `03-setup-and-workflow.md`).
- **Zero Friction** - Operational paradigm where agents automatically infer developer intent from natural conversation and manage project tracking entities in the background without human overhead.
- **Context Token Hygiene** - Practice of keeping root context files (`CONTEXT.md`, `ISSUES.md`, `AGENTS.md`) strictly compact (< 50-80 lines) to prevent LLM context bloat while pushing details into session logs and KB articles.
- **FULL / REF protocol block** - The managed `ALONG-PROTOCOL` block in `AGENTS.md`: FULL (whole protocol) at an architecture root or git repository/submodule root; REF (short pointer, `ref=<relpath>`) in a nested folder whose ancestor in the same git working tree carries the FULL block.
- **Imported VISION section** - A root `VISION.md` merged into `.along/VISION.md` between `<!-- along:imported-vision needs-restructure ... -->` markers when both had content; the agent decomposes it and removes the markers, `along doctor` reports it until then.
- **Root notes** - Root-level `ROADMAP.md`, `ARCHITECTURE.md`, `SPEC.md`, `TODO.md`, `DESIGN.md` that duplicate the Knowledge Base; listed by `along init`, migration, `along doctor` and `along kb-sync`, routed by the agent.
