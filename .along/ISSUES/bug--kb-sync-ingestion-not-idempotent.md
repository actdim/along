---
protocol: along
protocol_version: 2.2.8
slug: kb-sync-ingestion-not-idempotent
type: bug
status: open
priority: high
created: 2026-09-01
updated: 2026-09-01
agent: claude-code
tags: [kb-sync, idempotency, data-loss, archive]
milestone: v3.0.0-global-quality-revision
blocked_by: []
related: [kb-sync-rewrites-unrelated-numbered-links, handrolled-yaml-loses-block-lists]
parent: protocol-quality-audit-remediation
---

# KB ingestion is not idempotent and overwrites hand-edited articles from stale sources

## Problem 1: sources are copied, not moved, but reported as moved

```python
# scripts/along_kb_sync.py:157-162
with open(d_path, "w", encoding="utf-8") as fp:
    fp.write(dump_frontmatter(fm, raw))
arch_path = os.path.join(archive_dir, f"{os.path.basename(src_dir)}--{item}")
shutil.copy2(s_path, arch_path)
print(f"   Compiled & Archived raw source: {src_dir}/{item} -> docs/{target_name} (original -> .archive/)")
```

`shutil.copy2` leaves the original in place, while the message claims the original moved to
`.archive/`. Compare with the `docs/` branch at line 213, which uses `shutil.move`. The two
ingestion paths behave differently and only one matches the message.

## Problem 2: every subsequent run overwrites the compiled article

Because the raw source survives in `wiki/` or `kb/`, the next `/along-kb-sync` run finds it
again, still without `protocol: along`, and regenerates `docs/topic--<slug>.md` from the
stale raw content. Any human or agent edits made to the compiled article since the previous
run are destroyed.

The skill advertises the opposite:

```text
skills/along-kb-sync/SKILL.md:8   Idempotent LLM-Wiki Knowledge Base synchronization ...
AGENTS.md                          Idempotent Synchronization: Use /along-kb-sync to bootstrap, compile, and validate
```

The `.along/KB` and `.agents/KB` sources happen to escape this loop because they are deleted
at the end of the run (`along_kb_sync.py:637-639`), but `wiki/` and `kb/` are not, so the
overwrite loop is permanent for those two roots.

## Problem 3: irreversible deletion of legacy KB directories

```python
# scripts/along_kb_sync.py:630-639
for old_kb in [os.path.join(repo_root, ".along", "KB"), os.path.join(repo_root, ".agents", "KB")]:
    if os.path.exists(old_kb):
        shutil.rmtree(old_kb, ignore_errors=True)
```

Unconditional recursive delete with errors ignored. If ingestion partially failed earlier in
the same run (any of the `except` paths, or a write error), the source is deleted anyway.
`.along/CONTEXT.md` is likewise removed at line 631-636 with the exception swallowed.

## Problem 4: `--check` mode still writes

`sync_kb(check_only=True)` is documented as "Check links and structure without modifying
files", but `ingest_and_archive_sources` executes `os.makedirs(docs_dir, exist_ok=True)`
unconditionally at line 103, so a check run creates a `docs/` directory in a repository
that had none.

## Problem 5: front-matter round-trip loses metadata

Every article that needs any field filled in is rewritten through `dump_frontmatter`
(`along_kb_sync.py:529-533`), which inherits all the defects in
`[bug--handrolled-yaml-loses-block-lists]`: block-style lists are dropped, titles containing
colons produce invalid YAML, key order changes, comments are lost.

Related: `protocol_version` is only set when missing (line 513-515), never upgraded, which
is why `docs/topic--architecture.md` still declares `2.2.6` while the protocol is `2.2.8`.

## Impact

The command users are told to run right after initialization can destroy their curated
documentation, and running it twice is not safe. That is the opposite of the advertised
contract.

## Requirements

- REQ-1: Make ingestion genuinely idempotent: after compiling a raw source, either move it
  to `.archive/` or record a content hash so it is not recompiled. Messages must describe
  what actually happened.
- REQ-2: Never overwrite an existing compiled article from a raw source. On conflict, write
  `.archive/` and report a conflict requiring a decision.
- REQ-3: Remove unconditional `rmtree`. Delete a legacy source only after verifying the
  target exists and is non-empty, and only with an explicit `--prune-legacy` flag; write a
  backup otherwise.
- REQ-4: `--check` must perform zero filesystem writes, including directory creation. Add a
  test that asserts the tree is byte-identical after `--check`.
- REQ-5: Decide and implement `protocol_version` upgrade semantics for existing articles.
- REQ-6: Replace exception swallowing with reported failures.
- REQ-7: Tests: running sync twice on a `wiki/` source leaves the second run a no-op; a
  hand-edited compiled article survives a second run; `--check` writes nothing; partial
  failure does not delete sources.

## Acceptance Criteria

- [ ] Second consecutive `kb-sync` run produces no changes.
- [ ] Hand edits to `docs/topic--*.md` survive subsequent runs.
- [ ] `--check` provably writes nothing.
- [ ] Legacy deletion requires an explicit flag and verifies the target first.
- [ ] `protocol_version` upgrade behavior defined and tested.
