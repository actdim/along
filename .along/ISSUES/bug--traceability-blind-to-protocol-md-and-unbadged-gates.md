---
protocol: along
protocol_version: "4.9.1"
slug: traceability-blind-to-protocol-md-and-unbadged-gates
title: "Gate traceability does not scan .along/PROTOCOL.md and ignores undocumented gates"
type: bug
status: open
priority: high
created: 2026-11-24
updated: 2026-11-24
agent: dsh
tags: [gates, traceability, verify, protocol, documentation]
blocked_by: []
related: []
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

- [ ] `along hook verify` lists the five gates above and exits non-zero before any fix.
- [ ] `.along/PROTOCOL.md` badges are counted in the report.
- [ ] After badges are added, `along hook verify` exits zero without `--strict`.
- [ ] The YAML error badge for `typography` equals the gate id.
- [ ] A test fails if `.along/*.md` drops out of the scan set.

## Evidence

- Scan set: `scripts/alongkit/hooks/traceability.py:70-90`.
- Verdict: `:58-59`; report printing: `:214-226`.
- Exit code: `scripts/along_hook.py:243`, `:252`.
- Badges in the new protocol file: `.along/PROTOCOL.md` (22 matches).
