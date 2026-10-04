---
name: along-init
description: Scaffold or refresh the provider-agnostic agent-context structure in a repository - root AGENTS.md (with a managed block carrying the ALONG-PROTOCOL), a CLAUDE.md that imports it, .gitattributes for merge union, and the .along/ directory (ISSUES + ISSUES/, DECISIONS, VISION, GLOSSARY, HISTORY, SESSIONS, docs/). Use when the user wants to set up agent context/instructions for a project, initialize the agent structure, or invokes /along-init. Idempotent - re-running refreshes only the managed protocol block and never overwrites existing dynamic state files.
---

# Along Init (`/along-init`)
Scaffold or refresh the provider-agnostic agent-context structure in a repository - root `AGENTS.md` (with a managed block carrying the `ALONG-PROTOCOL`), a `CLAUDE.md` that imports it, `.gitattributes`, and the `.along/` directory (`ISSUES.md` + `ISSUES/`, `DECISIONS/`, `VISION.md`, `GLOSSARY.md`, `HISTORY.md`, `SESSIONS/`, `docs/`).

## When to use
- The user wants to set up agent context or instructions for a project (`/along-init`, "set up agent context", "initialize along").
- The user wants to refresh the managed protocol block in an existing repository's `AGENTS.md` without losing project-specific conventions.
- Migrating an existing `.agents/` structure to the isolated `.along/` standard.

## Division of work
- **The engine (`along init`) does every mechanical step.** Do not re-implement them by hand; run the command and read its report.
- **The agent does the judgment steps** the report lists under `AGENT ACTIONS` and `RE-RUN QUESTIONS`, in the same run. Initialization is not done while either list has open items.

## Step 1: Run the deterministic scaffolder
Resolve the target: the directory the user named, else `git rev-parse --show-toplevel`, else the current directory. State it to the user, then:
```bash
along init <target> --dry-run
along init <target>
```
*(Fallback: `python ~/.along/bin/along_exec.py init <target>`. Flags: `--json`, `--no-rules`, `--no-git`, `--no-hooks`, `--no-migrate`.)*

What the engine does, so you can verify the report:
1. **`AGENTS.md` managed block** (`protocol.md` is the single source):
   - **FULL vs REF**: walking up from the target's parent inside the same git working tree, if an ancestor `AGENTS.md` carries a FULL block (`<!-- BEGIN ALONG-PROTOCOL root`), the target gets a short REF block (`<!-- BEGIN ALONG-PROTOCOL ref=<relpath>`) pointing to it; otherwise it is an architecture root and gets the FULL block. A git repository or submodule root always gets FULL (a REF into a parent repository breaks when the submodule is cloned alone).
   - **Existing file with markers**: only the text between the markers is replaced (legacy `ACTDIM-AGENTS-PROTOCOL` markers included).
   - **Hand-written file without markers**: the block goes on top; the original text stays below unchanged, under `## Project specifics` unless that heading already exists.
   - **Missing file**: created with the block and an empty `## Project specifics`.
2. **`CLAUDE.md`** imports `AGENTS.md` (`See @AGENTS.md for project instructions and guidance.`); the line is prepended only when missing.
3. **`.gitattributes`**: `*.md text eol=lf`, `.along/HISTORY.md merge=union`, `.along/DECISIONS.md merge=union` appended when missing.
4. **`.along/` skeleton, create-only**: `ISSUES.md`, `ISSUES/done/`, `DECISIONS/`, `GLOSSARY.md`, `HISTORY.md`, `SESSIONS/<YYYY>/`, `docs/INDEX.md`. Existing state is never overwritten. The migration (item 7) adds `MILESTONES/`, `RISKS/`, `SPIKES/`, `CHECKLISTS/` and `.code-review-graph-ignore`.
5. **`VISION.md`** - a VISION belongs to the folder it sits in. The root file is never left next to `.along/VISION.md`:
   - `.along/VISION.md` missing or an empty skeleton -> root content moved there, root file deleted.
   - Same content -> root file deleted.
   - Both with content -> root content appended to `.along/VISION.md` inside `<!-- along:imported-vision needs-restructure ... -->` ... `<!-- /along:imported-vision -->`, root file deleted.
   - Links to the root `VISION.md` are repointed: from `README.md`/`docs/` to `docs/INDEX.md` (public files never link into `.along/`), from `.along/` files to `.along/VISION.md`. Relative links inside the moved text are rebased.
   - No VISION anywhere -> skeleton with `## Scope`, `## Non-goals`, `## Roadmap`.
   - A `VISION.md` in a subfolder belongs to that subproject: untouched until `along init` runs there.
6. **Root notes**: `ROADMAP.md`, `ARCHITECTURE.md`, `SPEC.md`, `TODO.md`, `DESIGN.md` at the target root are listed (never moved by the engine).
7. **Pipeline**: `along rules attach` (stack detection, rule packs into `.along/rules/`, references in `AGENTS.md`), `along git setup` (git roots only; registers the merge drivers in `.git/config` and the managed `merge=along-projection` / `merge=along-frontmatter` block in `.gitattributes`; `--uninstall` removes both), `along hook install --runtime all` (Antigravity `.agents/hooks.json`, Claude Code `.claude/settings.json`, Codex `.codex/hooks.json`), `along migrate <target> --apply`. `CONTEXT.md` is deprecated since v2.2.0 and is not created.

## Step 2: Agent actions (mandatory, same run)
Work through every `AGENT ACTIONS` line of the report:
- **Imported VISION section**: decompose it, then delete the section and both markers.
  - Scope, boundaries, non-goals, roadmap phases -> merge into the matching `## Scope` / `## Non-goals` / `## Roadmap` of `.along/VISION.md`.
  - Architecture, specifications, integrations -> `docs/topic--architecture.md` (or another `docs/topic--<slug>.md`).
  - Concrete backlog items -> issues (`along issue create`) and milestones in `.along/MILESTONES/`.
- **Root notes**: route each file the same way (roadmap -> VISION `## Roadmap` and milestones; architecture/spec/design -> `docs/topic--*.md`; TODO items -> issues), repoint links to it through `docs/INDEX.md`, then delete it. Ask the user first if a file is clearly meant to stay public at the root.
- **Adopted hand-written `AGENTS.md`**: review `## Project specifics`; keep project conventions, remove text that duplicates the protocol.
- Fill `## Project specifics` from facts in the code, `README.md` and manifests (what the project is, build / test / run, architecture map).
- Run `along doctor`: it reports a leftover `needs-restructure` marker, a root `VISION.md` next to `.along/`, and root notes.

## Step 3: Re-run dialog (mandatory when `.along/` already existed)
The report prints `RE-RUN QUESTIONS`. Ask the user each one and act on the answer; do not replace the dialog with a passive table:
1. Rebuild the code graph from scratch (`along graph-sync --full`)?
2. Refresh the Knowledge Base from `README.md` and `docs/` (`/along-kb-sync`)?
3. Review `.code-review-graph-ignore` exclusions (`along graph-check`)?

## Step 4: Propose onboarding operations
After a first initialization, offer the user these optional operations:

| Proposed Skill / Operation | Command | Purpose & Impact |
| --- | --- | --- |
| **Knowledge Base Ingestion & Sync** | `/along-kb-sync` | Ingests `README.md` and raw notes into structured `docs/topic--*.md`, tracks in-place source provenance, compiles `llms.txt` and `llms-full.txt`, and cross-links `docs/INDEX.md`. |
| **Dependencies & Submodules AI Scan** | `/along-dep-scan` | Recursively inspects package manifests (`package.json`, `pyproject.toml`, `*.csproj`, `Cargo.toml`), Git submodules, and symlinks for AI rules and updates `docs/topic--dependencies.md`. |
| **Git History & Entities Reconcile** | `/along-history-sync` | Analyzes commit history, tags, and PRs to retroactively synthesize `.along/ISSUES/done/`, `.along/SESSIONS/`, and `HISTORY.md`. *(Recommended for existing repositories)* |
| **Code Intelligence Graph Indexing** | `/along-graph-sync` | Builds code-review-graph AST database (`along graph-sync --full`) to empower semantic blast-radius and symbol dependency analysis. |
| **Executive Dashboard & Health** | `/along-dash` | Launches the interactive dashboard to inspect repository KPI metrics, Knowledge Base, and Cytoscape DAG graph. |

## Step 5: Report
Summarize for the user: files CREATED / UPDATED (FULL or REF) / left UNTOUCHED, the VISION outcome with the deleted source path, repointed links, root notes routed, and the answers to the re-run questions. Do not `git add` or commit unless the user asks.

## Migration engine notes
`along init` runs `along migrate <target> --apply`. The engine never deletes a destination file (append-only files are merged, projections keep the destination, a colliding legacy entity is preserved as `<name>.legacy.md`), copies the state directory into `.along/.migration-backup/<timestamp>/` before the first change (a removed root `VISION.md` is copied to `root/` there), and records `.along/.protocol-version` so a second run is a no-op. The root `VISION.md` check runs even on an up-to-date repository. Add `--force` to re-run every step.
