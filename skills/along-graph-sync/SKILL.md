---
name: along-graph-sync
description: Build, update, or incrementally synchronize the code-review-graph AST database with repository changes. Use when updating the AST code graph, indexing project symbols, or invoking /along-graph-sync.
---

# Along Graph Sync (`/along-graph-sync`)
Builds, updates, or inspects the `code-review-graph` code intelligence database for the repository.

## Usage
- Direct command: `/along-graph-sync`
- Incremental update (default): `along graph-sync` (or `along graph-build`)
- Full rebuild: `along graph-sync --full` (or `along graph-build --full`)
- Check graph stats: `along graph-sync --status`
- JSON summary: `along graph-sync --json`
- Direct script fallback: `python ~/.along/bin/along_exec.py graph-sync`

## Key Capabilities
1. **Self-Healing Exclusions**: Automatically verifies that `.code-review-graph-ignore` exists in the repository root. If missing or incomplete, auto-injects critical exclusions (`node_modules/`, `dist/`, `build/`, `.venv/`, `site/`, `.git/`, `*.min.js`) to prevent parser ballooning and timeouts.
2. **Incremental by Default**: Re-indexes only files modified since the last build (`code-review-graph update`), completing in seconds.
3. **Full Rebuild Mode**: Re-parses the entire codebase from scratch (`--full`) when switching branches or performing major refactorings.
4. **Lifecycle Interoperability**:
   - `along-init`: Scaffolds ignore filters and runs initial graph build.
   - `along-update`: Runs incremental sync to keep AST symbols fresh.
   - `along-wrap`: Refreshes graph before evaluating semantic blast radius.
