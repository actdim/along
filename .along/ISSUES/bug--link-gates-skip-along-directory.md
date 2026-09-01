---
protocol: along
protocol_version: 2.2.8
slug: link-gates-skip-along-directory
type: bug
status: open
priority: high
created: 2026-09-01
updated: 2026-09-01
agent: claude-code
tags: [kb-sync, link-integrity, coverage, false-green]
milestone: v3.0.0-global-quality-revision
blocked_by: []
related: [generated-docs-emit-file-uri-links, quality-gates-skip-hidden-directories]
parent: protocol-quality-audit-remediation
---

# Global Link Integrity Gate and link rewriter never inspect .along/

## Problem

Both repository-wide passes filter out every directory whose name starts with a dot:

```python
# scripts/along_kb_sync.py:263  (rewrite_inbound_links)
dirs[:] = [d for d in dirs if d not in IGNORED_DIRS and not d.startswith('.')]

# scripts/along_kb_sync.py:390  (validate_repo_link_integrity)
dirs[:] = [d for d in dirs if d not in IGNORED_DIRS and not d.startswith('.')]
```

So `.along/**` is invisible to both the rewriter and the integrity gate. That is precisely
where the protocol's own link-bearing files live:

```text
.along/ISSUES.md       40 links
.along/HISTORY.md      34 links
.along/DASHBOARD.md    12 links
.along/SESSIONS/**     multiple links per session log
.along/ISSUES/**       links between entities
```

The claims contradicted by this filter:

- `skills/along-kb-sync/SKILL.md:14` - "Recursively verifies that every relative link in
  all `.md` files in the project physically resolves to an existing file on disk".
- `skills/along-kb-sync/SKILL.md:13` - "Automatically scans all Markdown files across the
  entire repository hierarchy".
- `AGENTS.md` - "migration engines MUST recursively rewrite legacy path references across
  all repository Markdown files before deleting legacy directories".

The migration story is the worst case: `along_kb_sync.py:637-639` deletes `.along/KB/`
after the rewrite pass, but the rewrite pass cannot see links inside `.along/` that point at
`.along/KB/`. Those links are guaranteed to break and guaranteed not to be reported. The
session log `2026-09-01--version-v226-and-migration-step8-repair.md` describes a "Step 8
migration engine for retroactive link repair", which cannot work for the directory it is
most needed in.

## Secondary defects in the same gate

1. **Over-broad skip rule.** Any link target containing `<` or `>` is skipped
   (`along_kb_sync.py:424`), so a whole class of real links with template-looking segments is
   never validated.
2. **Hardcoded placeholder allowlist.** `ILLUSTRATIVE_PLACEHOLDERS`
   (`along_kb_sync.py:33-36`) lists concrete real article names
   (`./topic--architecture.md`, `./topic--setup-and-workflow.md`), so genuine broken links to
   those two files can never be reported.
2. **No autofix and no machine-readable output.** The gate prints text only; `--strict`
   fails the run but offers no report artifact for CI consumption.
3. **`file://` links are validated but should not exist.** See
   `[bug--generated-docs-emit-file-uri-links]`; the resolver has bespoke Windows drive-letter
   handling (`along_kb_sync.py:437-448`) to support a link form the same skill forbids.

## Impact

The gate reports "All N relative Markdown links verified on disk" while excluding the
directory with the highest link density in the repository. This is a false-green signal on
the protocol's own memory.

## Requirements

- REQ-1: Walk `.along/` (and other protocol-relevant dot directories) in both the rewriter
  and the integrity gate. Keep excluding only genuine noise (`.git`, `node_modules`, build
  output, `.archive`), by exact segment match.
- REQ-2: Make the exclusion set explicit and shared between both passes, with a documented
  rationale per entry.
- REQ-3: Narrow the `<`/`>` skip rule to targets that are actually placeholders (for example
  containing `<...>` as a whole segment), and remove real article names from
  `ILLUSTRATIVE_PLACEHOLDERS`.
- REQ-4: Emit a machine-readable report (`--json`) with file, line, text, target, resolved
  path, so CI can consume it.
- REQ-5: Order of operations: the rewrite pass must complete and be verified before any
  legacy directory deletion, and deletion must be skipped if the gate found unresolved
  references to that directory.
- REQ-6: Tests: a broken link inside `.along/SESSIONS/` is reported; a legacy link inside
  `.along/HISTORY.md` is rewritten; legacy directory is not deleted while references remain.

## Acceptance Criteria

- [ ] Gate reports broken links located in `.along/**`.
- [ ] Rewriter fixes legacy links located in `.along/**`.
- [ ] Shared, documented exclusion set used by both passes.
- [ ] `--json` report available.
- [ ] Legacy deletion blocked while unresolved references exist.
