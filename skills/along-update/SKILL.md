---
name: along-update
description: Check and update Along protocol and skills to the latest version across local repository, global installation, and GitHub. Automatically reconciles runtime lifecycle hooks (.claude, .codex, .agents), cleans up legacy un-namespaced skills, and optionally runs post-update sync engines. Use when the user asks to update agents/along, upgrade the repository protocol, or invokes /along-update.
---

# Along Update (`/along-update`)
Discovers all existing agent contexts across the repository tree and updates them to the latest protocol standard: synchronizing global skill installations, executing versioned migrations, automatically configuring runtime lifecycle hooks for supported agents (Antigravity, Claude Code, OpenAI Codex), rewriting legacy inbound links, and validating repository-wide link integrity.

## When to use
- The user requests an update of Along protocol, instructions, or skills (`/along-update`, "update along", "upgrade protocol").
- Upgrading an existing workspace from an older protocol version.
- Reconciling global agent environments (Claude, Codex, Gemini, OpenCode).

## Execution

```bash
along update [target_root] [options]
```
*(Or fallback: `python ~/.along/bin/along_exec.py update [target_root] [options]` or `/along-update`)*

### CLI Flags
- `--check-only`: Inspect versions and print status report without modifying files.
- `--dry-run`: Simulate updates and migrations without writing to disk.
- `--force`: Force reinstallation and refresh even if versions match.
- `--local-only`: Skip remote GitHub check and use local installation.
- `--global`: Synchronize global skills installation on the host machine (dev repo -> host, or GitHub -> host). By default, updates are strictly isolated to the target repository.
- `--no-hooks`: Skip automatic reconciliation of runtime lifecycle hooks.
- `--kb-sync`: Run Knowledge Base sync (`/along-kb-sync`) across all contexts.
- `--dep-scan`: Run multi-project dependencies scan (`/along-dep-scan`) across all contexts.
- `--history-sync`: Run Git commit history reconciliation (`/along-history-sync`).
- `--all-sync`: Execute all three post-update sync operations sequentially.

## What the update changes in each context
For every folder with `AGENTS.md`, `.along/` or `.agents/` (root first, then nested):
- **Protocol block** (shared with `along init`, `alongkit.scaffold`): FULL at an architecture root, a short REF in a nested folder of the same git working tree; a git submodule root gets FULL. A hand-written `AGENTS.md` without markers gets the block on top and keeps its text under `## Project specifics`.
- **Migration** (`along migrate --apply`), including Step 13: a root `VISION.md` is moved into `.along/VISION.md` (or deduplicated, or merged under an `along:imported-vision needs-restructure` marker) and deleted; links to it are repointed (public files -> `docs/INDEX.md`). This check runs even when the context is already on the current version. Root notes (`ROADMAP.md`, `ARCHITECTURE.md`, `SPEC.md`, `TODO.md`, `DESIGN.md`) are listed.

### Agent actions after the update (mandatory, same run)
- Decompose any `along:imported-vision` section (scope / non-goals / roadmap stay; architecture -> `docs/topic--architecture.md`; backlog -> issues and milestones), then delete the section and its markers.
- Route listed root notes the same way and delete them.
- Run `along doctor` in each touched context; it must report no leftover marker, root `VISION.md` or root note.

## Post-Update Recommended Operations
When run without automatic sync flags, `/along-update` displays a recommended next steps summary table offering:
1. `📚 /along-kb-sync`: Ingest and compile Knowledge Base in `docs/` with in-place source provenance and `llms.txt` / `llms-full.txt` sync.
2. `🔍 /along-dep-scan`: Scan dependencies, submodules, and installed packages for AI rules into `docs/topic--dependencies.md`.
3. `📜 /along-history-sync`: Reconcile past Git history and commit logs into `.along/` entities.
4. `📊 /along-dash`: Launch the repository executive dashboard to inspect KPI metrics and DAG graph.
