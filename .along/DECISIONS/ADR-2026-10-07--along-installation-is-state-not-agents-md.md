---
protocol: along
slug: along-installation-is-state-not-agents-md
type: decision
title: "An Along installation is Along state, never an AGENTS.md"
date: 2026-10-07
status: accepted
tags: [adr, architecture, decision, contexts, subprojects]
---

# ADR-2026-10-07--along-installation-is-state-not-agents-md - An Along installation is Along state, never an AGENTS.md

- Date: 2026-10-07
- Status: accepted
- Context: Three helpers decided "Along is installed here" differently. `repo.find_repo_root` (every CLI command, wrap, commit, the engines) stopped at any `.along` entry, a `.git` or an `AGENTS.md`; `repo.find_agent_contexts` (update, kb-sync, hook cleanup) counted a folder with only an `AGENTS.md`; `repo.is_along_state_dir` counted any non-empty `.along/` except hook diagnostics, and an empty one. A nested `AGENTS.md` is ordinary progressive disclosure (instructions for working in that folder), yet a board command run there started a new `.along/`, `along update` wrote the protocol block into it, and side effects (`.along/scripts/test.py`, artifacts, blackboards) turned folders into contexts. Only the runtime hooks (`find_hook_root`) already ignored a bare `AGENTS.md`. Complements ADR-2026-10-06--subproject-boundary-is-git-or-explicit-init.
- Decision: (1) A folder has Along installed (`repo.is_installed`) when it owns Along state: a `.along/` holding at least one state entry (`repo.STATE_ENTRIES`: ISSUES, ISSUES.md, DECISIONS, DECISIONS.md, MILESTONES, SESSIONS, HISTORY.md, VISION.md, GLOSSARY.md, CONSTRAINTS.md, RISKS, SPIKES, CHECKLISTS, .protocol-version, legacy KB), a legacy `.agents/` with its state entries, or an explicit `<!-- along-root: ... -->` pointer. An empty `.along/` or one holding only what Along writes on its own (scripts, artifacts, .session, diagnostics, .migration-backup, worktrees) is not an installation. (2) `AGENTS.md` is never a context or root marker: root discovery stops at an installation or a `.git`; context discovery lists installations only. The one exception is `along update` refreshing a repository root whose AGENTS.md carries the managed block (an early install without state). (3) Only `along init` creates an installation. Board commands (issue, start, session, plan, decision, milestone, scratch, worktree, wrap, commit) refuse outside one; lifecycle commands run the detected command without writing a hook; history sync does not synthesize; diagnostics and lifecycle logs go to `~/.along` unless the root is installed. (4) Package documentation (`docs/` next to an `AGENTS.md`, `llms.txt` or a package manifest) is compiled by `kb-sync` without a `.along/` of its own.
- Consequences: A folder guide never receives the protocol block, so a guide shipped inside a NuGet/npm package stays a guide. Issues created from any subfolder land in the nearest installation. Test fixtures and tools that used an empty `.along/` as a context marker must create a state entry. A repository with only an AGENTS.md and no state is reported as not installed until `along init` runs. Existing nested installations keep working; `along doctor` lists those outside a nested git repository (ADR-2026-10-06).
