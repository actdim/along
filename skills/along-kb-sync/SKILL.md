---
name: along-kb-sync
description: Synchronize, compile, and reconcile the Knowledge Base in docs/ using LLM-Wiki pipeline. Ingests README facts and raw sources, rewrites inbound legacy links, validates link integrity across monorepo packages, and rebuilds docs/INDEX.md. Use when invoking /along-kb-sync.
---

# Along KB Sync  [v2.2.11]

Idempotent LLM-Wiki Knowledge Base synchronization, inbound link rewriting, compilation, and repository-wide link-integrity gate for `docs/`.

## Capabilities
1. **Cold-Start Bootstrapping**: If `docs/` is missing or empty, generates `docs/INDEX.md`, `docs/topic--architecture.md`, `docs/topic--domain-model.md`, `docs/topic--setup-and-workflow.md` grounded in codebase and `README.md` facts.
2. **README Ingestion & Streamlining**: Extracts deep technical specifications from monolithic `README.md` files into modular `docs/topic--<slug>.md` articles, leaving `README.md` as an executive overview with direct navigation links.
3. **Inbound Link Rewriting Engine**: Automatically scans all Markdown files across the entire repository hierarchy (`packages/*`, `apps/*`, root `README.md`) and rewrites legacy paths (`.along/KB/...`, `.agents/KB/...`, old file names) to valid relative paths in `docs/`.
4. **Global Link Integrity Gate**: Recursively verifies that every relative link in all `.md` files in the project physically resolves to an existing file on disk, reporting exact files, line numbers, and invalid targets.
5. **Ingestion & Archival**: Compiles unmanaged notes, specs, or drafts (`wiki/`, `kb/`, `docs/`) into structured Wiki articles and safely moves raw source files into `.archive/`.
6. **LLM-Wiki Paradigm**: Native Python implementation of the Andrej Karpathy LLM-Wiki methodology. One runtime dependency (`ruamel.yaml`, for front-matter), resolved automatically by `uv`; everything else is standard library.

## Universal Rendering & Stable Entry Points

All Markdown generated or maintained by `along-kb-sync` MUST strictly adhere to universal rendering standards:
- **Stable Entry Point Rule**: Files outside the service directory (`README.md`, `docs/`, package manifests, external documentation) MUST NOT link directly into `.along/`, nor into legacy service paths from earlier protocol versions. Route every such reference through a stable canonical path in `docs/` (`docs/INDEX.md` or `docs/topic--<slug>.md`). The rule governs published links only: agents still read `.along/ISSUES.md` and `.along/DECISIONS.md` directly, as instructed at session start.
- **Monorepo Scope Rule**: Knowledge Base synchronization, link rewriting, and link verification operate recursively across all subprojects, packages (`packages/*`, `apps/*`), and directories.
- **Relative Markdown Links**: Use standard relative paths (`./docs/topic--<name>.md` from root, `./topic--<name>.md` within `docs/`). Never use absolute URLs, local filesystem schemes (`file:///`), or OS-specific backslashes.
- **Cross-Platform Renderers**: Guarantees 100% clean rendering across **GitHub**, **GitLab**, **GitHub Pages** (Jekyll, Astro, Docusaurus, MkDocs), **npm**, **NuGet**, **PyPI**, and **crates.io**.
- **Clean ASCII Typography**: Zero non-ASCII typography (no em-dashes U+2014, curly quotes, or ellipsis glyphs).
- **Explicit Code Fences**: Every code block must declare an explicit language identifier (`bash`, `yaml`, `typescript`, `python`, `powershell`).

## Execution Strategy: Adaptive Ingestion & Parallel Research

When executing `/along-kb-sync`:
- **Direct Incremental Ingestion**: For 1-3 raw source files or minor updates, the agent directly reads facts, creates/updates `docs/topic--<slug>.md`, and runs the compiler.
- **Parallel Research Ingestion (Large-Scale / Multi-Package)**:
  - When processing extensive documentation dumps, large monorepos, or multiple subprojects:
    1. **Decompose Topics**: Split the knowledge extraction into 2-4 discrete domain vectors (e.g. `architecture`, `data-models`, `api-integrations`, `workflows`).
    2. **Spawn Parallel Subagents**: Concurrently invoke research subagents to synthesize independent `docs/topic--<slug>.md` articles in parallel with standard YAML front-matter (`protocol: along`, `protocol_version: "2.2.11"`).
    3. **Reconcile & Link**: Run `python scripts/along_kb_sync.py` to rewrite inbound links, validate relative links across the repository, move processed raw sources into `.archive/`, and rebuild `docs/INDEX.md`.

## Usage
```bash
python scripts/along_kb_sync.py [REPO_ROOT] [--check] [--strict]
```
*(Or `python scripts/along_exec.py kb-sync` / `/along-kb-sync`)*
