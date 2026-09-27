---
name: along-dep-scan
description: Hierarchical multi-project & submodule dependency discovery engine. Scans Node, Python, .NET NuGet, Rust, Go, and custom stacks, discovers AI instructions, and registers them into docs/topic--dependencies.md. Use when invoking /along-dep-scan.
---

# Along Dependency Scan
Discovers AI documentation and guidelines shipped inside internal subprojects, Git submodules, symlinked packages, and declared project dependencies, registering them into the Knowledge Base (`docs/topic--dependencies.md`).

## What it does
1. **Hierarchical Project & Submodule Discovery**:
   - Traverses workspace to discover monorepo packages (`packages/*`, `apps/*`, `libs/*`), Git submodules, and symlinks.
   - Applies strict skip lists (`node_modules`, `.git`, `.venv`, `bin`, `obj`, `dist`, `build`, `.archive`, `.cache`) and loop protection.
2. **Multi-Ecosystem Manifest Inspection**:
   - Node: `package.json` (`dependencies`, `devDependencies`, `peerDependencies`, `optionalDependencies`).
   - Python: `pyproject.toml`, `requirements*.txt`, `setup.py`.
   - .NET / C# / F#: `*.csproj`, `*.fsproj`, `Directory.Packages.props`, `packages.config`.
   - Rust: `Cargo.toml` (`[dependencies]`, `[dev-dependencies]`, `[build-dependencies]`).
   - Go: `go.mod`.
   - Adaptive Project Hooks: `.along/scripts/dep_scan.py` support for custom or unknown ecosystems.
3. **On-Disk AI Rules Discovery**:
   - Locates installed packages and submodules to discover `AGENTS.md`, `CLAUDE.md`, `llms.txt`, `llms-full.txt`, `docs/`, `.along/`, and package manifest metadata (`ai`, `llms`, `agents`, `along`).
4. **Internal Workspace DAG & Subproject-Scoped Projections**:
   - Resolves internal monorepo package relationships across Node, Python, .NET, and Rust.
   - Generates localized `docs/topic--dependencies.md` for initialized subprojects with accurate relative links.
   - Extracts exported invariants (`<!-- EXPORT-INVARIANTS: ... -->`) into the Transitive Guidelines & Invariants section.
   - Root `docs/topic--dependencies.md` maintains both the internal modules registry and the internal monorepo dependency graph.
5. **Optional Safe Direct Linking**:
   - `--link` safely maintains a managed block `<!-- BEGIN ALONG-DEPS --> ... <!-- END ALONG-DEPS -->` in subproject `AGENTS.md` strictly for internal workspace packages without polluting system prompts with external dependencies.

## Execution
Run the dependency scanner via the canonical Along entry point:

```bash
along dep-scan [--root <path>] [--link] [--all-subprojects] [--check] [--json]
```
*(Or fallback: `python ~/.along/bin/along_exec.py dep-scan` or `/along-dep-scan`)*

### CLI Flags
- `--all-subprojects`: Generate localized `docs/topic--dependencies.md` in all discovered subprojects.
- `--check`: Perform dry-run scan without modifying files.
- `--json`: Output discovered dependencies, internal DAG, and projects in structured JSON format.
- `--link`: Safely synchronize managed dependency links into subproject `AGENTS.md` files.
- `--quiet` / `-q`: Minimal console output.
- `--root <path>`: Specify custom repository or submodule root directory.
