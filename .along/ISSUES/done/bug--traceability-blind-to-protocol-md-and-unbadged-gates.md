---
protocol: along
protocol_version: "4.9.1"
slug: traceability-blind-to-protocol-md-and-unbadged-gates
title: "Gate traceability does not scan .along/PROTOCOL.md and ignores undocumented gates"
type: bug
status: done
completed: 2026-11-25
priority: high
created: 2026-11-24
updated: 2026-11-25
agent: dsh
tags: [gates, traceability, verify, protocol, documentation]
blocked_by: []
related: []
plan_status: approved
---

# Gate traceability does not scan .along/PROTOCOL.md and ignores undocumented gates

## Problem

The protocol claims a machine-checked bidirectional matrix: every catalogue gate must have at
least one prose badge, and every badge must resolve to a gate
(`docs/topic--declarative-gates-and-traceability.md:216`). Two independent holes break it.

**Hole 1: the scanner does not read the file the rules moved into.** After the v4.9 core
slimming, procedures live in `.along/PROTOCOL.md`, which carries 22 `[gate: ...]` badges.
`scan_prose_anchors` reads `AGENTS.md`, `CLAUDE.md`, `README.md`, then walks `skills/`,
`docs/` and `.along/rules/` - and never `.along/*.md`
(`scripts/alongkit/hooks/traceability.py:70-90`). Badges written in the new protocol file are
invisible, so the file that now holds most rules contributes nothing to the matrix.

**Hole 2: missing badges do not fail the check.** `TraceabilityReport.is_clean` is
`not dangling_references and not schema_errors`
(`scripts/alongkit/hooks/traceability.py:58-59`): `undocumented_gates` is collected and
printed (`:214-216`) but never affects the verdict, and `along_hook.py` exits non-zero on it
only under the optional `--strict` flag (`scripts/along_hook.py:243`, `:252`).

Measured against the current tree, five catalogue gates carry no badge in any scanned prose
file - their `[gate: ...]` appears only in `default_gates.yaml` error strings, Python literals,
or `gitgates.py` docstrings, none of which the scanner reads:

| Gate id | Only occurrence |
| :--- | :--- |
| `typography` | `default_gates.yaml:160`, as the different identity `clean-ascii-typography` |
| `provenance_drift` | `default_gates.yaml:459`, plus a `gitgates.py` docstring |
| `session_record_append_only` | `default_gates.yaml:446`, plus a `gitgates.py` docstring |
| `windows_safe_filenames` | `default_gates.yaml:364` |
| `no_tracked_secrets` | `default_gates.yaml:473` |

`no_tracked_secrets` is `tier: invariant`, and `typography` is one of the two rules most often
invoked against agents, so the blind spot sits on the strictest part of the catalogue. The
`typography` case is worse than a missing badge: the badge the YAML emits,
`[gate: clean-ascii-typography]`, is a different identity from the gate id `typography`, and
`_canonical_id` normalizes only case, hyphens and underscores
(`traceability.py:57-59`), so a badge copied from the error message would be reported as
dangling.

## Requirements

- REQ-1: `scan_prose_anchors` MUST include `.along/*.md` (at minimum `PROTOCOL.md`,
  `VISION.md`, `CONSTRAINTS.md`, `GLOSSARY.md`) in its scan set.
- REQ-2: A missing badge MUST fail the default check, not only `--strict`; if `--strict` stays,
  its default MUST flip, and CI MUST run the strict form.
- REQ-3: Every gate id MUST have at least one badge in scanned prose, and every badge emitted
  in a gate error message MUST be the gate id (fix `clean-ascii-typography` or the id).
- REQ-4: A test MUST assert that the number of distinct badges found in `.along/PROTOCOL.md` is
  greater than zero, so moving rules again cannot silently disconnect the matrix.

## Acceptance Criteria

- [x] `along hook verify` lists the five gates above and exits non-zero before any fix.
- [x] `.along/PROTOCOL.md` badges are counted in the report.
- [x] After badges are added, `along hook verify` exits zero without `--strict`.
- [x] The YAML error badge for `typography` equals the gate id.
- [x] A test fails if `.along/*.md` drops out of the scan set.

## Evidence

- Scan set: `scripts/alongkit/hooks/traceability.py:70-90`.
- Verdict: `:58-59`; report printing: `:214-226`.
- Exit code: `scripts/along_hook.py:243`, `:252`.
- Badges in the new protocol file: `.along/PROTOCOL.md` (22 matches).

## Resolution Notes

- `scan_prose_anchors` (`scripts/alongkit/hooks/traceability.py`) now scans top-level `.along/*.md` files (`PROTOCOL.md`, `VISION.md`, `CONSTRAINTS.md`, `GLOSSARY.md`, etc.) without descending into entity subdirs (`ISSUES/`, `SESSIONS/`, `DECISIONS/`).
- `TraceabilityReport.is_clean` requires `not self.undocumented_gates`, and `scripts/along_hook.py verify` flips `--strict` to `default=True` (CI `.github/workflows/tests.yml` runs `python scripts/along_exec.py hook verify --strict`).
- Fixed `scripts/alongkit/hooks/default_gates.yaml` so `typography` emits `[gate: typography]` instead of `[gate: clean-ascii-typography]`.
- Added `[gate: ...]` badges in `skills/along-init/protocol-reference.md` (and regenerated `.along/PROTOCOL.md` via `along update --local-only --no-hooks`) for all 10 undocumented commit-time gates: the 5 listed above plus the 5 remaining unbadged `[git, ci]` gates (`anti_stub_injection`, `code_fence_language`, `commit_no_ai_coauthor`, `portable_links`, `stable_entry_point`), bringing `along hook verify` to `35 / 35` anchored (`EXIT=0`).
- Added regression tests in `tests/test_gates_traceability.py` and updated `docs/topic--declarative-gates-and-traceability.md`, `docs/topic--runtime-hooks-and-gates.md`, and `docs/topic--cli-reference.md`.
