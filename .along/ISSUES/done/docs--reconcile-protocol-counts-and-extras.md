---
protocol: along
protocol_version: "4.9.1"
slug: reconcile-protocol-counts-and-extras
type: docs
status: done
completed: 2026-11-23
priority: medium
created: 2026-11-23
updated: 2026-11-23
agent: antigravity
tags: [docs, drift, metadata, gates, skills]
blocked_by: []
related: []
plan_status: approved
---

# Reconcile protocol counts, VISION version, and extras across documentation

## Problem
During repository quality analysis, several factual drift issues and out-of-sync counts were identified across core documentation and metadata:
1. `README.md` states "32 protocol invariants" in the Declarative Runtime Gates row, whereas `scripts/alongkit/hooks/default_gates.yaml` defines 35 active gates (verified via `along hook verify`).
2. `docs/topic--skills-reference.md` states "21 singular automation skills", whereas 22 skills exist on disk (`skills/*/SKILL.md`), including `along-webdev`. Furthermore, `scripts/alongkit/cli.py` retains a comment referencing "nineteen SKILL.md files".
3. `.along/VISION.md` has frontmatter `protocol_version: "4.4.11"` while the repository protocol version is `4.9.1`.
4. `README.md` omits `actdim-along[webdev]` from optional extras installation and describes `actdim-along[all]` as an alias for `[dash]` only, ignoring `[webdev]`.

## Requirements
- REQ-1: `README.md` MUST reflect 35 declarative runtime gates instead of 32.
- REQ-2: `docs/topic--skills-reference.md` MUST declare 22 singular automation skills instead of 21.
- REQ-3: `scripts/alongkit/cli.py` MUST NOT reference the obsolete count of nineteen skills in module comments.
- REQ-4: `.along/VISION.md` MUST set frontmatter `protocol_version: "4.9.1"`.
- REQ-5: `README.md` MUST document `actdim-along[webdev]` under optional extras installation and state that `actdim-along[all]` installs both `[dash]` and `[webdev]`.
- REQ-6: Knowledge Base provenance hashes MUST be synchronized via `along kb-sync` for modified topic files.

## Acceptance Criteria
- [x] `README.md` runtime gate description specifies 35 protocol invariants.
- [x] `README.md` extras section lists `pip install actdim-along[webdev]` and correctly defines `[all]`.
- [x] `docs/topic--skills-reference.md` specifies 22 singular automation skills.
- [x] `scripts/alongkit/cli.py` has no obsolete nineteen skills comment.
- [x] `.along/VISION.md` frontmatter has `protocol_version: "4.9.1"`.
- [x] `along hook verify` passes with 35 defined gates.
- [x] `python scripts/along_kb_sync.py --strict` passes.
- [x] `python .along/scripts/test.py` passes without regressions.
