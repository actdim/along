---
protocol: along
protocol_version: "2.2.19"
slug: migration-resilience-and-link-reconciliation
type: feat
status: done
completed: 2026-09-04
priority: high
created: 2026-09-04
updated: 2026-09-04
agent: antigravity
tags: [migration, frontmatter, links, resilience]
milestone: v3.0.0-global-quality-revision
blocked_by: []
related: [generated-docs-emit-file-uri-links]
---

# Migration resilience and link reconciliation

Improve Along migration and link resilience:
1. Gated migration repair (< 2.2.9) for unquoted colons in YAML front-matter scalars.
2. Gated advisory scan (v2.0.0 <= version < 2.2.9) for potential shell-escaping artifacts in docs/.
3. Pure relative Markdown links in along_exec.py issue sync and sibling link updates on move to done/.
4. Safe subproject LICENSE link resolution in along_kb_sync.py.
5. Recompile issue projections in along_update.py.

## Acceptance Criteria
- [x] Front-matter repair in migrate_protocol.py recovers unquoted colons in title/summary/description for detected_version < 2.2.9.
- [x] migrate_protocol.py emits advisory warnings for shell-escape artifacts in docs/ only when migrating from v2.0.0 <= version < v2.2.9.
- [x] along_exec.py issue sync emits clean relative links (ISSUES/{f}) and issue done adjusts sibling links.
- [x] along_kb_sync.py rewrites missing subproject LICENSE links to root LICENSE.
- [x] along_update.py invokes issue sync on updated contexts.
- [x] All automated tests pass with zero regressions.

