---
name: along-dep-scan
description: Hierarchical multi-project & submodule dependency discovery engine. Scans Node, Python, .NET NuGet, Rust, Go, and custom stacks, discovers AI instructions, and registers them into docs/topic--dependencies.md. Use when invoking /along-dep-scan.
---

# Along Dependency Scan  [v2.2.13]

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
4. **Idempotent Knowledge Base Integration**:
   - Generates/updates `docs/topic--dependencies.md` with:
     * **Internal Subprojects, Modules & Submodules** registry.
     * **Declared External Dependencies with AI Guidelines**, scoped by component.
   - Reconciles links in `docs/INDEX.md`.

## Execution
Run the dependency scanner directly via Python:

```bash
python scripts/along_dep_scan.py [--root <path>] [--check] [--json]
```
*(Or `python scripts/along_exec.py dep-scan` / `/along-dep-scan`)*

### CLI Flags
- `--check`: Perform dry-run scan without modifying `docs/`.
- `--json`: Output discovered dependencies and subprojects in structured JSON format.
- `--quiet` / `-q`: Minimal console output.
- `--root <path>`: Specify custom repository or submodule root directory.
