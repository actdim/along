---
name: along-update
description: Check and update Along protocol and skills to the latest version across local repository, global installation, and GitHub. Cleans up legacy un-namespaced skills and optionally runs post-update sync engines. Use when the user asks to update agents/along, upgrade the repository protocol, or invokes /along-update.
---

# Along Update (`/along-update`) [v2.2.12]

Discovers all existing agent contexts across the repository tree and updates them to the latest protocol standard, synchronizing global skill installations, executing versioned migrations, rewriting legacy inbound links, and validating repository-wide link integrity.

## When to use
- The user requests an update of Along protocol, instructions, or skills (`/along-update`, "update along", "upgrade protocol").
- Upgrading an existing workspace from an older protocol version.
- Reconciling global agent environments (Claude, Codex, Gemini, OpenCode).

## Execution

```bash
python scripts/along_update.py [target_root] [options]
```

### CLI Flags
- `--check-only`: Inspect versions and print status report without modifying files.
- `--dry-run`: Simulate updates and migrations without writing to disk.
- `--force`: Force reinstallation and refresh even if versions match.
- `--local-only`: Skip remote GitHub check and use local installation.
- `--kb-sync`: Run Knowledge Base sync (`/along-kb-sync`) across all contexts.
- `--dep-scan`: Run multi-project dependencies scan (`/along-dep-scan`) across all contexts.
- `--history-sync`: Run Git commit history reconciliation (`/along-history-sync`).
- `--all-sync`: Execute all three post-update sync operations sequentially.

## Post-Update Recommended Operations
When run without automatic sync flags, `/along-update` displays a recommended next steps summary table offering:
1. `📚 /along-kb-sync`: Ingest raw notes into `docs/` and archive processed originals into `.archive/`.
2. `🔍 /along-dep-scan`: Scan dependencies, submodules, and installed packages for AI rules into `docs/topic--dependencies.md`.
3. `📜 /along-history-sync`: Reconcile past Git history and commit logs into `.along/` entities.
4. `📊 /along-dash`: Launch the repository executive dashboard to inspect KPI metrics and DAG graph.
