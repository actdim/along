---
protocol: along
protocol_version: "2.2.9"
slug: kb-source-provenance-and-reconstruction
type: feat
status: open
priority: high
created: 2026-09-01
updated: 2026-09-01
agent: claude-code
tags: [kb-sync, provenance, archive, llm-wiki, reconstruction]
milestone: v3.0.0-global-quality-revision
blocked_by: []
related: [kb-sync-ingestion-not-idempotent, link-gates-skip-along-directory]
parent: protocol-quality-audit-remediation
---

# KB articles carry no provenance back to the raw sources they were compiled from

## Problem

An LLM-Wiki is a compiled artifact. Its articles are a lossy synthesis of raw inputs, and
the synthesis is only trustworthy while the inputs remain reachable: a later model, a
corrected fact, or a changed article schema all require recompiling from the sources rather
than editing the summary. Along today keeps the sources and throws away the link to them.

### 1. The compiled article does not record what it was compiled from

`ingest_and_archive_sources` writes the article front-matter with a fixed key set and no
provenance field:

```python
# scripts/along_kb_sync.py:143-151 (and again at 195-204 for the docs/ branch)
fm = {
    "protocol": "along",
    "protocol_version": CURRENT_PROTOCOL_VERSION,
    "slug": slug, "title": title, "type": "topic",
    "created": today, "updated": today,
    "tags": [...],
}
```

The standard front-matter schema in `AGENTS.md` matches: `protocol`, `protocol_version`,
`slug`, `title`, `type`, `created`, `updated`, `tags`. Nothing names the origin. Every
article in `docs/` is therefore indistinguishable from one written by hand, and no consumer
can answer "where did this claim come from" or "which articles must be rebuilt if this
source changes".

### 2. The archived copy loses its original path

```python
# scripts/along_kb_sync.py:152
arch_path = os.path.join(archive_dir, f"{os.path.basename(src_dir)}--{item}")
# scripts/along_kb_sync.py:206
arch_path = os.path.join(archive_dir, f"raw--{item}")
```

The archive is a flat directory with a name-mangled copy. `wiki/adr/legacy/notes.md` lands
as `wiki--notes.md`: the intermediate path is gone, and two sources with the same basename
under different directories silently overwrite one another. The archive cannot be walked
back to a source tree, so it cannot be re-ingested.

### 3. The archive is excluded from every gate

`.archive` sits in `repo.IGNORED_DIRS` (`scripts/alongkit/repo.py:177`) alongside
`node_modules` and build output. Link validation, link rewriting, typography sanitation, and
KB search all skip it. Whatever provenance value the directory holds is unverified and
undiscoverable, and legacy links inside archived sources are never repaired.

### 4. `.archive/README.md` states the mechanism, not the contract

The bootstrapped README (`scripts/along_kb_sync.py:80`) says the directory "holds processed
raw notes ... that have been synthesized into structured Knowledge Base articles". It does
not say why anyone should keep them, what guarantees hold, or when they may be deleted. In
practice the directory reads as a wastebasket, which is how it gets treated: this
repository's own `.archive/` contains nothing but that README.

## Impact

The Knowledge Base cannot be rebuilt. A schema migration, a factual correction in a source,
or a better synthesis pass all have to be applied by hand-editing compiled prose, which is
exactly the drift the protocol exists to prevent. The `Strict Fact Grounding Requirement` in
`AGENTS.md` demands that agents extract facts from real sources, but offers no way to check
an existing article against the source it claims to be grounded in.

## Requirements

- REQ-1: Extend the `docs/*.md` front-matter schema with a provenance field recording each
  raw input the article was compiled from, by repository-relative path plus a content hash,
  and the date of the compilation. Update the schema in `AGENTS.md` and
  `skills/along-init/protocol.md` together (they are byte-equal by test).
- REQ-2: Preserve the source tree shape under `.archive/`, mirroring the original relative
  path instead of flattening to a mangled basename. Two sources with the same basename must
  not collide.
- REQ-3: Make the provenance chain verifiable: a `--check` mode reports articles whose
  recorded source is missing from the archive, and articles whose source hash no longer
  matches (the source changed after compilation, so the article is stale).
- REQ-4: State the contract in `.archive/README.md` and in the KB section of the protocol:
  the archive is the input side of a reproducible compilation, not a wastebasket. Say what
  may be deleted and what may not.
- REQ-5: Stop excluding `.archive/` from link rewriting and typography passes, so archived
  sources stay re-ingestible. Keep excluding it from KB search results and from the compiled
  `docs/INDEX.md`, which is a separate concern. Coordinate with
  `[bug--link-gates-skip-along-directory]`, which touches the same exclusion set.
- REQ-6: Support recompilation: a documented path from an archived source back to a
  regenerated article, so a schema change or a better synthesis can be replayed over the
  whole KB rather than hand-applied.
- REQ-7: Coordinate with `[bug--kb-sync-ingestion-not-idempotent]`. That issue fixes the
  copy-versus-move divergence and the overwrite loop in the same two code paths; provenance
  must be designed on top of the corrected ingestion, not bolted onto the broken one.

## Open questions

- Whether provenance belongs in article front-matter, in a separate manifest under
  `.archive/`, or both. Front-matter travels with the article and survives file moves; a
  manifest survives hand-edits to the article and keeps the front-matter compact.
- Whether externally sourced material (fetched pages, vendor documentation) is archived
  verbatim or recorded by URL plus retrieval date, given that these files are committed.

## Acceptance Criteria

- [ ] Compiled articles declare their sources with a verifiable hash.
- [ ] `.archive/` mirrors the original source paths without collisions.
- [ ] `--check` reports missing sources and stale articles.
- [ ] The archive contract is documented in the protocol and in `.archive/README.md`.
- [ ] A KB can be recompiled from `.archive/` with a documented command.
- [ ] Tests cover: provenance round-trip, basename collision, stale-source detection.
