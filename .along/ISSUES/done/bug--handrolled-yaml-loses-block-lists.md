---
protocol: along
protocol_version: 2.2.8
slug: handrolled-yaml-loses-block-lists
type: bug
status: done
completed: 2026-09-01
priority: critical
created: 2026-09-01
updated: 2026-09-01
agent: claude-code
tags: [yaml, frontmatter, data-loss, schema, parser]
milestone: v3.0.0-global-quality-revision
blocked_by: []
related: [extract-shared-python-library, entity-status-enum-and-unused-taxonomy]
parent: protocol-quality-audit-remediation
---

# Hand-rolled YAML front-matter parser and writer corrupt valid entity metadata

## Problem

Front-matter is parsed and serialized by hand in at least three independent copies
(`along_kb_sync.py:38-72`, `along_kb_search.py`, `dashboard/core/collector.py:33`).

### 1. The writer produces invalid YAML for ordinary values

```python
# along_kb_sync.py:58-72
def dump_frontmatter(fm, body):
    ...
    lines.append(f"{k}: {v}")
```

No quoting, no escaping. A title containing a colon, which is completely normal
("Protocol v1.5.0: Automated Entity Ecosystem", already present in this repository's ADR
titles), serializes to:

```yaml
title: Protocol v1.5.0: Automated Entity Ecosystem
```

which is not valid YAML. Values containing `#`, leading `[`/`{`, quotes, or newlines break
in similar ways.

### 2. The parser silently discards YAML block sequences

```python
# along_kb_sync.py:44-55
for line in fm_str.splitlines():
    ...
    if ":" in line:
        k, v = line.split(":", 1)
```

Lines without a colon are skipped entirely. So this perfectly valid front-matter:

```yaml
tags:
  - protocol
  - retrieval
```

parses to `{"tags": ""}`, and the subsequent `dump_frontmatter` writes back `tags:` with
the items **gone**. Any `docs/*.md` article or entity authored with block-style lists loses
its metadata the first time an Along engine touches the file. This is silent, irreversible
data loss triggered by a read-modify-write that the user did not ask for.

### 3. The schema the protocol documents cannot be parsed by the protocol's own tooling

`AGENTS.md` defines checklists as:

```yaml
items: [{ id, text, verified: bool }]
```

The hand-rolled parser has no notion of nested mappings inside a flow sequence. It would
store the raw string and destroy it on rewrite. The documented entity schema is therefore
not representable in the implementation.

### 4. Round-trip is not order- or comment-preserving

`dump_frontmatter` re-emits `protocol` and `protocol_version` first and then iterates the
remaining dict, so key order changes and YAML comments are dropped.

### 5. `pyyaml` is already a dependency

`scripts/along_dash.py:7` declares `pyyaml>=6.0.0` in its PEP 723 block. The project pays
for the dependency and does not use it for its own metadata.

## Impact

The entity metadata is the single source of truth for the whole system: dashboards,
retrieval, projections, milestone progress, and DAG links all read it. A parser that drops
data and a writer that can emit invalid YAML undermine every downstream consumer, and the
failure is silent.

## Requirements

- REQ-1: Use a real YAML implementation for front-matter (`pyyaml`, `safe_load` /
  `safe_dump`) behind one shared module, or vendor a small round-trip-safe implementation
  if a zero-dependency guarantee must be kept. Decide and record as an ADR: the
  `along-kb-sync` skill currently advertises "zero external dependencies".
- REQ-2: Support block sequences, flow sequences, nested mappings, quoted scalars, and
  multi-line strings on both read and write.
- REQ-3: Preserve key order; preserve unknown keys verbatim; never drop content the parser
  does not understand.
- REQ-4: Quote values that require quoting; validate that the emitted block re-parses to an
  equal structure before writing (round-trip assertion).
- REQ-5: Replace all three duplicate implementations with the shared module, coordinated
  with `[debt--extract-shared-python-library]`.
- REQ-6: Refuse to rewrite a file whose front-matter fails to parse; report file and line.
- REQ-7: Tests: block-list survives a rewrite; title with a colon round-trips; nested
  checklist `items` round-trips; unknown keys preserved; invalid YAML is rejected loudly.

## Acceptance Criteria

- [ ] Block-style `tags:` list survives `kb-sync` untouched.
- [ ] Titles containing colons produce valid, re-parseable YAML.
- [ ] Documented `CHECKLISTS` schema is representable and round-trips.
- [ ] Only one front-matter implementation exists in the codebase.
- [ ] ADR recorded on the dependency decision.

## Resolution (2026-09-01)

- REQ-1: `ruamel.yaml` round-trip mode behind `alongkit.frontmatter`. Decision and the
  dependency policy recorded in `[ADR-2026-09-01--frontmatter-on-ruamel-yaml]`.
- REQ-2: block sequences, flow sequences, nested flow mappings, quoted and block scalars
  all read and written; covered by `TestFrontmatterReading`.
- REQ-3: key order, comments, and unknown keys are preserved because `update()` edits only
  the named keys as text lines. Measured: a no-op read-and-write is byte-identical for
  123 of 123 entity files in this repository.
- REQ-4: quoting is the writer's job (`test_quoting_is_applied_where_yaml_requires_it`),
  and both `render()` and `update()` re-parse their own output before returning it.
- REQ-5: the four duplicate implementations are gone; `along_kb_search`, `along_kb_sync`,
  `migrate_protocol`, and `dashboard/core/collector` alias the shared reader.
- REQ-6: a file whose front-matter fails to parse is refused with file and line; the
  migration and sync engines skip and report it instead of rewriting from a partial parse.
- REQ-7: covered in `TestFrontmatterReading` / `TestFrontmatterWriting`.

Six pre-existing files in this repository were unreadable by any strict YAML reader
(unquoted `title:` / `summary:` containing a colon): four milestones and two session logs.
Repaired, one line each. Two more had `null` normalized to a bare key. Found while measuring
idempotency, and `migrate_protocol.py` was reverting the repair on every test run because
the old writer re-emitted the values unquoted.
