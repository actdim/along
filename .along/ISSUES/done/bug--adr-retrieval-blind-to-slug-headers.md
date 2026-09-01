---
protocol: along
protocol_version: 2.2.8
slug: adr-retrieval-blind-to-slug-headers
type: bug
status: done
completed: 2026-09-01
priority: critical
created: 2026-09-01
updated: 2026-09-01
agent: claude-code
tags: [kb-search, decisions, retrieval, regression]
milestone: v3.0.0-global-quality-revision
blocked_by: []
related: []
---

# along-kb-search returns zero ADRs: splitter expects legacy numeric headers

## Problem

`scripts/along_kb_search.py` splits `.along/DECISIONS.md` into ADR entries with a regex
that only recognizes the pre-v2.2.0 numeric header format (`## 011 - Title`):

```python
adr_blocks = re.split(r"\n(?=##\s+\d+[\.:])", dec_raw)
```

Protocol v2.2.0 replaced numeric ADR headers with decentralized slug headers
(`## ADR-YYYY-MM-DD--<slug> - <Title>`) to avoid merge collisions between parallel
branches. The splitter was never updated, so it yields zero blocks on any v2.2.x repo.

Reproduction on this repository (18 ADRs present in `.along/DECISIONS.md`):

```text
python scripts/along_kb_search.py "concurrency" --category decision   -> 0 matches
python scripts/along_kb_search.py "concurrency"                       -> 6 matches (issues/sessions/kb only)
```

## Impact

`AGENTS.md` mandates reading `.along/DECISIONS.md` every session and instructs agents to
prefer `along-kb-search` for targeted retrieval before loading whole files. Because the
retrieval engine is blind to the decision log, agents silently lose access to all
architectural constraints they are required to honor. Severity is critical: the failure is
silent (zero results look like "no relevant decisions"), and it degrades the core
memory loop the protocol exists to provide.

## Requirements

- REQ-1: Recognize the current slug header format `## ADR-YYYY-MM-DD--<slug> - <Title>`.
- REQ-2: Keep recognizing the legacy numeric format `## <NNN>[.:] <Title>` for repositories
  that have not yet migrated (protocol < v2.2.0).
- REQ-3: Skip the schema template placeholder line (`## ADR-YYYY-MM-DD--<slug> - <Title>`)
  so it never appears as a search result.
- REQ-4: Emit a usable canonical key and anchor per ADR (`slug`, `file_path` with a GitHub
  compatible heading anchor) instead of the numeric `#<N>` anchor.
- REQ-5: Preserve existing `status` detection (`superseded` vs `active`).
- REQ-6: Regression test that searches the real `.along/DECISIONS.md` and asserts a
  non-empty `decision` category result set, so the format cannot drift silently again.

## Acceptance Criteria

- [x] `--category decision` returns matching ADRs on this repository (17 ADRs indexed).
- [x] Legacy numeric ADR headers still parse (unit-tested with a synthetic fixture).
- [x] Template placeholder row is excluded from results.
- [x] `tests/test_kb_search.py` covers slug format, legacy format, placeholder exclusion.
- [x] Full suite passes except the pre-existing `test_06` locale defect (tracked separately).

## Resolution

`scripts/along_kb_search.py`: extracted `parse_decision_entries()` and
`github_heading_anchor()` as module-level testable units.

- Split and header regexes now accept the slug format AND the legacy numeric format.
- Root cause was wider than the v2.2.0 rename: the old splitter required `\d+[.:]`, while
  the actual legacy headers in git history are `## 012 - <Title>` (digit, space, dash).
  ADR retrieval therefore never worked in any released version, not only since v2.2.0.
- An ISO date heading (`## 2026-08-20 ...`) is explicitly excluded from ADR detection.
- Each ADR block is truncated at the next level-2 heading so unrelated appended sections
  cannot bleed into an ADR body or search snippet.
- `status` detection is now case insensitive, so the protocol's own lowercase
  `Status: superseded by ADR-...` form is recognized (previously only `Superseded` matched).
- `file_path` carries a real GitHub heading anchor instead of `#<N>`.
- Entry `slug` is now the canonical ADR key, which also improves ranking because the
  scorer matches query terms against `slug`.

Verified: `--category decision` for "concurrency" returns
`ADR-2026-08-31--concurrency-projections-and-context-deprecation` (previously 0 matches).

## Follow-ups Filed Separately

- `test_06` fails on non-UTF8 Windows locales: no `encoding="utf-8"` on any `subprocess.run`.
- `along_exec.py issue create` stamps `agent: antigravity` and a non-existent
  `milestone: v2.1.0-along`.
- `tests/test_skills_and_scripts.py` `test_07` mutates the live working tree (it rewrote
  this file's front-matter quoting mid-session).
