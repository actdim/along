---
protocol: along
protocol_version: 2.2.8
slug: issue-done-corrupts-status-and-drops-completed
type: bug
status: done
completed: 2026-09-01
priority: high
created: 2026-09-01
updated: 2026-09-01
agent: claude-code
tags: [entity-lifecycle, along-exec, frontmatter, regression]
milestone: v3.0.0-global-quality-revision
blocked_by: []
related: [adr-retrieval-blind-to-slug-headers]
---

# issue done produces invalid status done-progress and silently drops completed

## Problem

Found while closing `[bug--adr-retrieval-blind-to-slug-headers]` with the protocol's own
CLI. `along_exec.py issue done` mutated the entity with unanchored substitutions over the
entire file:

```python
content = re.sub(r'status:\s*\w+', 'status: done', content)
content = re.sub(r'updated:\s*\S+', f'updated: {today}', content)
if "completed:" not in content:
    content = re.sub(r'(status:\s*done\n)', f'\\1completed: {today}\n', content)
```

Three compounding defects:

1. `\w+` does not match a hyphen, so `status: in-progress` became `status: done-progress`,
   a value outside the protocol enum (`open | in-progress | blocked | done`).
2. The mandatory `completed:` insertion is conditional on `status:\s*done\n` matching
   afterwards, which never matches once the value is `done-progress`. Closing an
   in-progress issue therefore silently dropped a field the protocol declares mandatory.
3. Both substitutions are unanchored and global, so any `status:` or `updated:` occurrence
   in the markdown body (prose, tables, code samples) was rewritten too.

Defect 1 and 2 only fire on the documented normal path (`open -> in-progress -> done`).
Closing straight from `open` worked, which is why this survived: the real lifecycle was
never exercised end to end.

## Impact

Silent corruption of the single source of truth for issue state, plus loss of the
`completed` date that dashboards, milestone progress, and `history-sync` depend on. The
CLI reported "Moved issue to done" while writing an invalid entity.

## Requirements

- REQ-1: Mutate keys only inside the leading YAML front-matter block; never touch the body.
- REQ-2: Handle hyphenated and quoted values; produce a status inside the protocol enum.
- REQ-3: Always write `completed: YYYY-MM-DD`, inserted directly after `status`.
- REQ-4: Preserve existing line endings (CRLF working copies are common on Windows).
- REQ-5: Tolerate a leading UTF-8 BOM instead of turning every update into a silent no-op.
- REQ-6: Refuse to close an entity whose front-matter cannot be parsed, with a non-zero
  exit code, instead of reporting success.

## Resolution

`scripts/along_exec.py`:

- Added `FRONTMATTER_RE`, `has_frontmatter()`, and `update_frontmatter_fields()` as
  reusable, line-anchored, body-safe front-matter primitives.
- `issue done` now calls `update_frontmatter_fields(..., place_after={"completed": "status"})`
  and aborts with exit code 1 when front-matter is unparseable.
- A leading BOM is detected and normalized away, matching the protocol's BOM-free rule.

Discovered during verification: a BOM-prefixed entity (routinely produced by PowerShell
`Set-Content -Encoding utf8` on Windows PowerShell 5.1) made the update a no-op while the
CLI still reported success. That is why REQ-5 and REQ-6 exist.

## Verification

- `tests/test_issue_lifecycle.py`: 12 tests covering the hyphenated status, mandatory
  `completed` placement, body immutability, idempotent re-close, CRLF preservation, BOM
  handling, and two repository-wide invariants:
  - no committed issue may carry a status outside the enum;
  - every issue in `ISSUES/done/` must declare `completed:`.
- End-to-end probe (create -> in-progress -> `issue done`) returns
  `status: done` + `completed: 2026-09-01`, no `done-progress`.
- Repaired the one already-corrupted entity: `ISSUES/done/bug--adr-retrieval-blind-to-slug-headers.md`.

## Acceptance Criteria

- [x] `issue done` on an in-progress issue yields `status: done`.
- [x] `completed:` is always written, directly after `status`.
- [x] Markdown body is never rewritten.
- [x] CRLF and BOM inputs handled.
- [x] Unparseable front-matter fails loudly with exit code 1.
- [x] Repository invariant tests guard both rules going forward.

## Known Remaining (not in scope)

`along_version_bump.py:410-411` uses the same unanchored pattern on milestone files
(`re.sub(r'status:\s*(?:open|in-progress)', 'status: completed', c)`), which can rewrite
milestone body text. To be fixed with the release-engine item.
