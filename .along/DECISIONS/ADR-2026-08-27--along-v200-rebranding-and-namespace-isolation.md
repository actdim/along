---
protocol: along
slug: along-v200-rebranding-and-namespace-isolation
title: "Along v2.0.0: Rebranding, Isolated .along/ Directory, along-* Skill Prefixes, and protocol: along Metadata"
date: 2026-08-27
status: accepted
tags: [adr, architecture, decision]
---

# ADR-2026-08-27--along-v200-rebranding-and-namespace-isolation - Along v2.0.0: Rebranding, Isolated .along/ Directory, along-* Skill Prefixes, and protocol: along Metadata

- Date: 2026-08-27
- Status: accepted
- Context: The generic `.along/` folder was prone to collision with third-party tools, and generic un-namespaced skills (like `dashboard`, `bump-version`, `sync-context`) collided in global agent environments (`~/.claude/skills/`, `~/.gemini/config/skills/`).
- Decision:
  1. Transition the product and protocol to **Along (`actdim-along`)** and **`ALONG-PROTOCOL v2.0.0`**.
  2. Store all project tracking and memory in an isolated **`.along/`** directory in target repositories.
  3. Require **`protocol: along`** in the YAML front-matter of all entity markdown files.
  4. Prefix all skills and slash commands with **`along-*`** (`along-init`, `along-update`, `along-dash`, `along-wrap-session`, etc.) and purge legacy un-namespaced skills during installation and update.
  5. Upgrade migration engine (`scripts/migrate_protocol.py`) to seamlessly detect legacy `.along/`, inject `protocol: along`, relocate files to `.along/`, and clean up empty `.along/` directories without touching foreign files.
- Consequences: Total isolation from third-party tools, zero namespace collision in global skill registries, backward-compatible automated migration path for existing projects.
