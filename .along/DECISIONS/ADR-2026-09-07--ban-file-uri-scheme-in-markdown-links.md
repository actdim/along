---
protocol: along
slug: ban-file-uri-scheme-in-markdown-links
title: "Ban file:// Scheme in Markdown Links in Favor of Standard Relative Links"
date: 2026-09-07
status: accepted
tags: [adr, architecture, decision]
---

# ADR-2026-09-07--ban-file-uri-scheme-in-markdown-links - Ban file:// Scheme in Markdown Links in Favor of Standard Relative Links

- Date: 2026-09-07
- Status: accepted
- Context:
  1. Contradictory rules existed across AGENTS.md and skill definitions: AGENTS.md loosely suggested relative paths (`file://...` or standard markdown links), which was contradictory because `file://` is not a relative path, while along-kb-sync banned `file:///`.
  2. Over 100 `file://` links accumulated across repository memory and projections (.along/ISSUES/, .along/HISTORY.md, .along/DASHBOARD.md, rules/INDEX.md, docs/INDEX.md).
  3. `file://` links do not resolve for users on GitHub, GitLab, GitHub Pages, npm, NuGet, PyPI, or crates.io, producing dead links in published packages and documentation.
  4. The link integrity gate previously resolved `file://` against the local filesystem with Windows drive-letter workarounds instead of enforcing portable relative links.
- Decision:
  1. **Strictly Ban `file://` Pseudo-Scheme**: All internal links across documentation, entity files, and generated projections must use standard portable relative Markdown paths (e.g., `[Title](./target.md)`). The `file://` and `file:///` schemes are strictly prohibited.
  2. **Generator Compliance**: All generators (`along_kb_sync.py`, `along_exec.py`, `along_history_sync.py`, `rules.py`) must compute and emit standard relative links based on the specific file being written.
  3. **Gate Enforcement**: The link integrity gate (`validate_repo_link_integrity`) must treat any `file://` link as a hard violation rather than resolving it, and Windows drive-letter resolution workarounds are removed.
  4. **Automated Migration & Anchor Repair**: `along_kb_sync.py` (`rewrite_inbound_links`) automatically converts legacy `file://` and `file:///` links to relative paths, and repairs or drops unresolvable fragments (such as numbered ADR anchors `#011` mapping to `adr-2026-08-28--frontend-dynstruct-architecture-and-msgmesh-adapters`).
- Consequences:
  - Documentation and links render portably and reliably across GitHub, GitLab, GitHub Pages, npm, and IDEs.
  - Zero ambiguity in agent instructions across AGENTS.md, protocol.md, and skills.
  - Link integrity gate programmatically prevents regression without bespoke filesystem resolution branches.
