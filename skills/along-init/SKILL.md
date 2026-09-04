---
name: along-init
description: Scaffold or refresh the provider-agnostic agent-context structure in a repository - root AGENTS.md (with a managed block carrying the ALONG-PROTOCOL v2.2.18), a CLAUDE.md that imports it, .gitattributes for merge union, and the .along/ directory (ISSUES + ISSUES/, DECISIONS, VISION, GLOSSARY, HISTORY, SESSIONS, docs/). Use when the user wants to set up agent context/instructions for a project, initialize the agent structure, or invokes /along-init. Idempotent - re-running refreshes only the managed protocol block and never overwrites existing dynamic state files.
---

# Along Init (`/along-init`) [v2.2.18]

Scaffold or refresh the provider-agnostic agent-context structure in a repository - root `AGENTS.md` (with a managed block carrying the `ALONG-PROTOCOL v2.2.18`), a `CLAUDE.md` that imports it, `.gitattributes`, and the `.along/` directory (`ISSUES.md` + `ISSUES/`, `DECISIONS.md`, `VISION.md`, `GLOSSARY.md`, `HISTORY.md`, `SESSIONS/`, `docs/`).

## When to use
- The user wants to set up agent context or instructions for a project (`/along-init`, "set up agent context", "initialize along").
- The user wants to refresh the managed protocol block in an existing repository's `AGENTS.md` without losing project-specific conventions.
- Migrating an existing `.agents/` structure to the isolated `.along/` standard.

## Execution Steps

### Step 1: Managed Protocol Block in `AGENTS.md`
- Locate the target repository root.
- If `AGENTS.md` does not exist: create it with the full managed protocol block (`protocol.md`) and a default `## Project specifics` section.
- If `AGENTS.md` already exists: update only the managed block between `<!-- BEGIN ALONG-PROTOCOL ... -->` and `<!-- END ALONG-PROTOCOL -->`, preserving all human-written content outside the markers.
- If legacy `<!-- BEGIN ACTDIM-AGENTS-PROTOCOL ... -->` markers are detected, replace them cleanly with the new ALONG-PROTOCOL markers.

### Step 2: Rule Pack Attachment
- Run `python scripts/along_exec.py rules attach` to detect the project stack, copy matching rule packs from `~/.along/rules/` into `.along/rules/`, and inject references into `AGENTS.md`.

### Step 3: `CLAUDE.md` & `.gitattributes` Scaffolding
- Ensure `CLAUDE.md` contains the line:
  ```markdown
  See @AGENTS.md for project instructions and guidance.
  ```
- Ensure `.gitattributes` exists at repository root with merge union configuration:
  ```gitattributes
  *.md text eol=lf
  .along/HISTORY.md merge=union
  .along/DECISIONS.md merge=union
  ```

### Step 4: Scaffold `.along/` Directory Skeleton (Create only if missing)
Create the directory structure if missing:
- `.along/ISSUES.md` + `.along/ISSUES/` + `.along/ISSUES/done/`: Issue tracking board and typed issue files (`protocol: along`).
- `.along/DECISIONS.md`: Append-only ADR log with slug headers (`ADR-YYYY-MM-DD--<slug>`).
- `docs/`: Knowledge base articles (`INDEX.md`, `topic--architecture.md`, `topic--domain-model.md`, `topic--setup-and-workflow.md`).
- `.along/MILESTONES/`: Milestone tracking files.
- `.along/RISKS/`: Risk & blocker registry.
- `.along/SPIKES/`: R&D experiment logs.
- `.along/CHECKLISTS/`: Standard verification checklists (`pre-commit.md`, `stage-completion.md`).
- `.along/VISION.md`, `.along/GLOSSARY.md`, `.along/HISTORY.md`, `.along/SESSIONS/<YYYY>/`.
*(Notice: CONTEXT.md is deprecated in v2.2.0 and is not created).*

### Step 5: Run Protocol Migration
Execute the migration engine against the target folder to validate front-matter and migrate any legacy `.agents/` content. Preview the plan first, then apply it:
```bash
python scripts/migrate_protocol.py <target_root> --dry-run
python scripts/migrate_protocol.py <target_root> --apply
```
`--apply` is mandatory for any non-interactive caller: without it the engine prints the plan and writes nothing. It never deletes a destination file (append-only files are merged, projections keep the destination, a colliding legacy entity is preserved as `<name>.legacy.md`), it copies the state directory into `.along/.migration-backup/<timestamp>/` before the first change, and it records `.along/.protocol-version` so a second run is a no-op. Add `--force` to re-run every step anyway.

### Step 6: Propose Onboarding & Repository Synchronization Operations
Upon completing initialization, agents and tools MUST present a clear onboarding proposal to the user with the following optional operations:

| Proposed Skill / Operation | Command | Purpose & Impact |
| **Knowledge Base Ingestion & Sync** | `/along-kb-sync` | Ingests `README.md` and raw notes into structured `docs/topic--*.md`, tracks in-place source provenance, compiles `llms.txt` and `llms-full.txt`, and cross-links `docs/INDEX.md`. |
| **Dependencies & Submodules AI Scan** | `/along-dep-scan` | Recursively inspects package manifests (`package.json`, `pyproject.toml`, `*.csproj`, `Cargo.toml`), Git submodules, and symlinks for AI rules and updates `docs/topic--dependencies.md`. |
| **Git History & Entities Reconcile** | `/along-history-sync` | Analyzes commit history, tags, and PRs to retroactively synthesize `.along/ISSUES/done/`, `.along/SESSIONS/`, and `HISTORY.md`. *(Recommended for existing repositories)* |
| **Executive Dashboard & Health** | `/along-dash` | Launches the interactive dashboard to inspect repository KPI metrics, Knowledge Base, and Cytoscape DAG graph. |
