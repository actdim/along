---
protocol: along
protocol_version: "4.4.1"
slug: rule-packs-local-extensions
type: feat
status: done
completed: 2026-10-01
priority: high
created: 2026-09-30
updated: 2026-10-01
agent: antigravity
tags: [rules, platform-packs, integrity, dep-scan, migration]
milestone: v4.5.0-multi-user-merge-automation
blocked_by: []
related: []
---

# Rule Packs Integrity, Clean Archetypes, and Docs-First Invariants

## Problem
Standard rule packs in `.along/rules/` are general-purpose conventions managed by Along.
When repositories have stack-specific rules (such as `@actdim/dynstruct`), agents mistakenly write them directly into `.along/rules/platforms/web.md`.
Subsequent `/along-update` or `/along-init` invocations silently overwrite those modifications and destructively prune repository files like `gates.yaml`.

Project-specific architectural invariants and framework guidelines do NOT belong in `.along/rules/`. They belong in the repository documentation (`docs/` LLM-Wiki), `AGENTS.md` ("Project specifics"), and package-exported invariants indexed via `along-dep-scan` into `docs/topic--dependencies.md`.

## Solution
1. Mark `.along/rules/*.md` files with a clear header comment:
   `<!-- managed by along: do not edit. Project guidelines belong in docs/ and AGENTS.md -->`
   `<!-- template: <rule> sha256:<hash> -->`
2. Track template SHA-256 hashes and abort silent overwrites in `attach_rules` when unmanaged modifications are detected.
3. Protect `.along/rules/gates.yaml` and dirty files from destructive pruning.
4. Provide `along rules status`, `along rules diff`, and `along rules restore` CLI commands.
5. Ensure generic platform archetypes (`rules/platforms/web.md`) are 100% clean of proprietary/framework dependencies.
6. Migrate `infomnia/src/apps/webapp`: extract Dynstruct/MsgMesh rules into `docs/topic--frontend-architecture.md` and `AGENTS.md`, and restore pristine Along `web.md`.

## Acceptance Criteria
- [ ] Rule templates copied to `.along/rules/` carry header comment and SHA-256 hash.
- [ ] `attach_rules` detects modified files, refuses silent overwrites, and logs warnings.
- [ ] `attach_rules` never deletes `.along/rules/gates.yaml` or dirty files during pruning.
- [ ] `along rules status|diff|restore` CLI works reliably.
- [ ] Generic `rules/platforms/web.md` contains zero proprietary framework references.
- [ ] `infomnia/src/apps/webapp` migrated: rules moved to `docs/` and pristine `web.md` restored.
- [ ] All automated tests pass hermetically.
