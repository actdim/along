---
protocol: along
protocol_version: "4.8.1"
slug: provenance-drift-gate
type: feat
status: in-progress
priority: medium
created: 2026-11-13
updated: 2026-11-13
agent: claude-code
tags: [docs, kb-sync, provenance, gates]
blocked_by: []
related: [docs--kb-search-docs-accuracy]
plan_status: approved
---

# Settle doc provenance drift in the change that edits a tracked source

## Problem
`docs/topic--*.md` articles list their sources with SHA-256 hashes in front-matter (`sources: [{path, hash}]`). `along kb-sync` reports a mismatch as a `[DRIFT]` warning, but no commit, wrap or CI gate checks it, and no command records a new hash. Hashes were set by hand and went stale: on 2026-11-13 `along kb-sync --check` showed 11 drift warnings across 6 topics. Drift surfaces weeks after the source change, to someone who lacks the context, so the warnings are ignored.

Goal: drift is settled in the same change that edits a tracked source, by its author, through a CLI command instead of hand-edited hashes. Pre-existing drift must not block unrelated work.

Out of scope: section- or symbol-level hashing of sources (separate issue), and reviewing the 11 existing drift warnings (separate `docs--` issue).

## Requirements
- REQ-1: `along kb-sync --accept-drift <topic> [<source>...]` MUST write the current LF-normalized SHA-256 of each named source (all drifted sources when none is named) into the topic front-matter, changing no other front-matter key or body line.
- REQ-2: `along kb-sync --accept-drift` MUST require either `--reviewed` (the topic text was checked against the source change) or `--no-doc-impact "<reason>"`, and MUST print the recorded decision so it can be quoted in the commit message.
- REQ-3: `along kb-sync --drift-diff <topic>` MUST print the git diff of each drifted source from the last commit whose topic front-matter held the recorded hash, or say that no such commit exists.
- REQ-4: A commit-time gate `provenance_drift` MUST reject a staged change to a tracked source when a topic that lists it would hold a hash different from the staged source content after the commit.
- REQ-5: The `provenance_drift` gate MUST NOT report drift for sources that the checked change does not touch (pre-commit: staged paths; CI: paths changed in the commit range).
- REQ-6: The `provenance_drift` gate MUST be declared in `alongkit/hooks/default_gates.yaml` with `enforcement: [git, ci]` and run from `along gates check`, `along commit` and `along gates check --ci`.
- REQ-7: `compute_content_hash` and the source-to-topic mapping MUST live in `scripts/alongkit/` and be imported by `scripts/along_kb_sync.py`.
- REQ-8: `docs/topic--llm-wiki-architecture.md`, `docs/topic--cli-reference.md`, `docs/topic--runtime-hooks-and-gates.md` and `skills/along-kb-sync/SKILL.md` MUST describe the new flags and the gate.

## Acceptance Criteria
- [ ] Staging an edit to a tracked source without updating the topic hash makes `along gates check` fail with `provenance_drift`, naming the topic and the source.
- [ ] After `along kb-sync --accept-drift <topic> --reviewed` (or `--no-doc-impact "..."`) the same commit passes.
- [ ] A commit that touches no tracked source passes even while other topics carry pre-existing drift.
- [ ] `--accept-drift` leaves all other front-matter keys and the body byte-identical (round-trip test).
- [ ] `--drift-diff` prints the source diff for a drifted topic in a test repository.
- [ ] New tests in `tests/` cover REQ-1 to REQ-6; `python .along/scripts/test.py` passes.
- [ ] Docs and skill updated per REQ-8; `along kb-sync --strict` passes.
