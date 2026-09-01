---
protocol: along
date: 2026-08-27
slug: along-v200-rebranding-and-migration
agent: antigravity
branch: main
commit: unknown
summary: 'Major architectural milestone: transition to Along (actdim-along), ALONG-PROTOCOL v2.0.0, .along/ directory, along-* skill prefixes, and automated migration engine.'
milestone: v2.0.0-along-transition
issues_advanced: []
issues_completed: []
decisions: ["007: Along v2.0.0 rebranding", ".along/ directory isolation", "along-* skill prefixes", "and protocol: along metadata"]
risks_logged: []
spikes_conducted: []
---

# Session Log: Along v2.0.0 Rebranding & Migration

## Overview
Executed comprehensive migration and rebranding from `Along` (`ALONG-PROTOCOL v1.5.7`) to **`Along` / `actdim-along` (`ALONG-PROTOCOL v2.0.0`)**.

## Key Accomplishments
1. **Isolated `.along/` Directory**:
   - Migrated all memory and tracking files from `.along/` to `.along/`.
   - Injected mandatory `protocol: along` in YAML front-matter across all entity files.
2. **Skill Suite Namespacing (`along-*`)**:
   - Renamed and restructured all skills to use the `along-*` prefix (`along-init`, `along-update`, `along-dash`, `along-wrap-session`, `along-wrap-stage`, `along-sync-context`, `along-sync-issues`, `along-sync-decisions`, `along-sync-history`, `along-init-kb`, `along-sync-kb`, `along-search-kb`, `along-check-graph`, `along-bump-version`).
   - Added automatic purge of legacy un-namespaced skill folders in `install.ps1`, `install.sh`, and `along_update.py`.
3. **Migration Engine (`scripts/migrate_protocol.py`)**:
   - Upgraded to support Step 4 (`.along/` -> `.along/` transfer, YAML front-matter validation, marker updates, and empty legacy directory removal).
4. **Dashboard & Analytics Engine (`scripts/along_dash.py`)**:
   - Updated scanner to prioritize `.along/` with fallback to `.along/`.
   - Updated UI and terminal reporting branding to `Along Dashboard`.
5. **Installers & Protocol Manfiest**:
   - Updated `AGENTS.md`, `README.md`, `rules/INDEX.md`, `docs/MIGRATIONS.md`, `install.ps1`, `install.sh`, and `install.bat`.
   - Verified local deployment and clean ASCII typography.

