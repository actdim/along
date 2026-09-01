---
protocol: along
protocol_version: 2.2.8
slug: kb-sync-rewrites-unrelated-numbered-links
type: bug
status: open
priority: high
created: 2026-09-01
updated: 2026-09-01
agent: claude-code
tags: [kb-sync, link-rewriting, heuristics, false-positive]
milestone: v3.0.0-global-quality-revision
blocked_by: []
related: [kb-sync-ingestion-not-idempotent, link-gates-skip-along-directory, generated-docs-emit-file-uri-links]
parent: protocol-quality-audit-remediation
---

# Link rewriting engine mangles unrelated links in consumer repositories

## Problem 1: legacy detection is a substring guess

```python
# scripts/along_kb_sync.py:299
has_kb_dir = any(k in target_base for k in
    [".along/KB", ".agents/KB", "/KB", "along/KB", "agents/KB", "/kb", "/wiki", "kb/", "wiki/"])
```

Substring matching on arbitrary link targets. Any link whose path merely contains `/kb`,
`/wiki`, `kb/`, or `wiki/` is classified as a legacy Knowledge Base path and rewritten.
Real-world false positives: `./assets/kbd-shortcuts.md`, `../sdk/kb-client/README.md`,
`./wiki/CONTRIBUTING.md` in a project that legitimately keeps a `wiki/` directory.

## Problem 2: any filename starting with digits is treated as legacy

```python
# scripts/along_kb_sync.py:318-324
elif re.match(r'^\d{1,3}[-_]', orig_filename) and not re.match(r'^\d{4}-\d{2}-\d{2}', orig_filename):
    is_legacy = True
    clean_name = re.sub(r'^\d{1,3}[-_]', '', orig_filename)
    new_filename = f"topic--{clean_name}"
```

Any markdown link whose filename begins with one to three digits plus `-` or `_` is
rewritten into `docs/topic--<name>.md`. Concretely affected conventions:

- `[ADR 001](./001-use-postgres.md)` - the Nygard/MADR ADR convention, which
  `.along/DECISIONS.md` itself cites as prior art in `ADR-2026-08-15--single-file-append-only-decisions`;
- `[Intro](./01-intro.md)`, `[API](./3-api.md)` - ordered documentation chapters;
- numbered RFC and proposal directories.

So Along rewrites the exact convention its own ADR discusses, in repositories that never
used Along's KB layout.

## Problem 3: the rewrite does not verify that the target exists

```python
# scripts/along_kb_sync.py:329-341
target_docs = root_docs_dir
if os.path.exists(os.path.join(file_dir, "docs", new_filename)):
    target_docs = os.path.join(file_dir, "docs")
target_abs = os.path.join(target_docs, new_filename)
new_rel = os.path.relpath(target_abs, file_dir)
```

Existence is checked only to choose between a subproject `docs/` and the root `docs/`. If
neither contains the file, the link is still rewritten to a non-existent path. The Global
Link Integrity Gate later in the same run then reports those links as broken. The engine
manufactures the defect it diagnoses, and `--strict` will fail the build because of it.

## Problem 4: fragile code-fence detection

```python
# scripts/along_kb_sync.py:356-363
if stripped.startswith("```") or stripped.startswith("~~~"):
    in_code_fence = not in_code_fence
```

A single toggle for both fence styles, no tracking of fence length or the opening marker,
so a `~~~` inside a ``` block flips the state and links inside code samples get rewritten
(or real links stop being rewritten).

## Impact

`/along-kb-sync` is presented as an idempotent, safe maintenance command and is recommended
to users right after `/along-init` (`skills/along-init/SKILL.md:58`). On a repository with
numbered docs or a `wiki/` directory it silently corrupts working links across the whole
tree, including `README.md`.

## Requirements

- REQ-1: Replace the substring heuristic with exact path-segment matching against a
  configured set of legacy roots.
- REQ-2: Remove the "filename starts with digits" rule as an automatic trigger. Support it
  only via an explicit opt-in (`--migrate-numbered`) or an explicit mapping file.
- REQ-3: Never rewrite a link unless the computed target exists on disk. If a legacy source
  is detected but the target is missing, report it and leave the link untouched.
- REQ-4: Add `--dry-run` output listing every intended rewrite (file, line, old, new) and
  require it in tool-to-tool invocations.
- REQ-5: Implement correct fenced-code tracking (marker character, fence length, opening
  info string) and cover it with tests including nested and mixed fences.
- REQ-6: Preserve link text and anchors exactly; add a round-trip test.
- REQ-7: Tests: `001-use-postgres.md` link untouched by default; `wiki/CONTRIBUTING.md`
  untouched; link inside a fenced block untouched; legacy `.along/KB/01-architecture.md`
  link correctly rewritten when the target exists.

## Acceptance Criteria

- [ ] Zero rewrites to non-existent targets.
- [ ] Numbered-file convention preserved unless explicitly opted in.
- [ ] `--dry-run` implemented.
- [ ] Fence detection handles mixed and nested fences.
- [ ] Regression tests cover all four false-positive classes above.
