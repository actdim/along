---
protocol: along
protocol_version: "4.8.1"
slug: doctor-detect-protocol-leak
type: feat
status: open
priority: low
created: 2026-11-13
updated: 2026-11-13
agent: claude-code
tags: [doctor, docs, kb-sync, leak]
blocked_by: []
related: [bug--protocol-leaks-into-docs]
---

# along doctor detects Along protocol leaked into consumer docs

## Problem

`bug--protocol-leaks-into-docs` moved the protocol reference to `.along/PROTOCOL.md` and made `along update` / `migrate_protocol.py` prune the legacy `docs/topic--along-protocol.md` (only when it carries the managed marker). Consumer repos are cleaned only after someone runs `along update` and then `along kb-sync`; until then the protocol stays in `docs/`, `docs/INDEX.md`, `llms.txt` and the published doc sites. `along doctor` (`scripts/alongkit/commands/doctor.py`) has no check for this, so the leak is invisible.

## Requirements
- REQ-1: `along doctor` MUST warn when any `docs/topic--along-protocol.md` exists in the repo or its subprojects, stating whether it carries the managed marker (`scaffold.REFERENCE_MARKER`).
- REQ-2: `along doctor` MUST warn when a `docs/INDEX.md`, `llms.txt` or `llms-full.txt` references `topic--along-protocol` or "Along Protocol Reference".
- REQ-3: Each warning MUST print the fix: `along update` (prunes the managed file) then `along kb-sync` (recompiles indexes); an unmarked file is reported but never suggested for deletion.
- REQ-4: A clean repo MUST print an `[OK]` line for this check.

## Acceptance Criteria
- [ ] Doctor warns on a temp repo with a managed legacy file and a leaked index entry, and prints the fix commands.
- [ ] Doctor reports an unmarked `docs/topic--along-protocol.md` without suggesting deletion.
- [ ] Doctor prints `[OK]` on a clean temp repo.
- [ ] `python .along/scripts/test.py` passes.

## Plan

Execution Mode: Direct (one command module plus tests).

1. In `scripts/alongkit/commands/doctor.py`, add `_doctor_protocol_leak_checks(repo_root, warnings) -> Tuple[int, List[dict]]`, modeled on `_doctor_zombie_docs_checks`: walk with `repo.IGNORED_DIRS` / `repo.PROVIDER_DIRS` pruning, find `docs/topic--along-protocol.md` and grep `docs/INDEX.md`, `llms.txt`, `llms-full.txt` for the slug/title. Reuse `scaffold.REFERENCE_MARKER` for the managed check. Print `[WARN: protocol-leak]` lines with the fix, or `[OK]`.
2. Call it from `handle_doctor_command` next to the zombie-docs check and include results in the JSON output if doctor has one.
3. Tests in a new or existing doctor test module: managed leak, unmarked file, index-only leak, clean repo; temp repos only.
4. Update the doctor section in the relevant `docs/topic--*.md` (locate via `/along-kb-search doctor`).

Verification: the new tests, the full suite, and `along doctor` on this repo (expects `[OK]`).
