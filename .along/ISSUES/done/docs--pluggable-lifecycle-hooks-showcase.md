---
protocol: along
protocol_version: "2.2.27"
slug: pluggable-lifecycle-hooks-showcase
type: docs
status: done
priority: high
created: 2026-09-09
updated: 2026-09-09
completed: 2026-09-09
agent: antigravity
tags: [docs, lifecycle, protocol, agents]
blocked_by: []
related: []
---

# Elevate Pluggable Lifecycle Hooks as Core Feature and Agent Directives

## Context
Along supports polyglot, pluggable repository execution hooks in `.along/scripts/` (`build.py`, `test.py`, `dev.py`, `bump_version.py`, `dep_scan.py` across `.py`, `.sh`, `.ps1`, `.bat`). However, this capability is under-documented, absent from the README showcase, and not mandated as a contract-first rule in the agent protocol.

## Requirements
- REQ-1: Highlight Stack Friction & Agent Tool Blindness in `README.md` ("Why Along?") and add the 8th pillar "Stack-Agnostic Lifecycle & Polyglot Hooks" to Core Value Proposition.
- REQ-2: Embed Contract-First Lifecycle Execution into `skills/along-init/protocol.md` and synchronize `AGENTS.md` managed block.
- REQ-3: Document `dep_scan.py` in `docs/topic--dependencies.md`.
- REQ-4: Document `alongkit.lifecycle` subsystem in `docs/topic--architecture.md`.
- REQ-5: Expand `docs/topic--setup-and-workflow.md` Section 4 to cover all hooks, polyglot interpreters, and argv safety.
- REQ-6: Clarify hook precedence in skills (`along-test`, `along-build`, `along-dev`, `along-dep-scan`).
- REQ-7: Recompile `docs/INDEX.md` and `llms-full.txt` via `along_kb_sync.py`, passing all hermetic tests and typography checks.

## Acceptance Criteria
- [x] README.md presents lifecycle hooks as a primary value proposition.
- [x] protocol.md and AGENTS.md managed block match exactly and mandate contract-first execution.
- [x] docs/topic--dependencies.md, docs/topic--architecture.md, and docs/topic--setup-and-workflow.md fully document all lifecycle scripts.
- [x] Hermetic test suite passes 100% (`python .along/scripts/test.py`).
- [x] Strict KB link validation passes (`python scripts/along_kb_sync.py --check --strict`).
- [x] Zero typography violations (`python scripts/sanitize_typography.py`).
