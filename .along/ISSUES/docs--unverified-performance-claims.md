---
protocol: along
protocol_version: "4.2.0"
slug: unverified-performance-claims
type: docs
status: open
priority: medium
created: 2026-09-27
updated: 2026-09-27
agent: cowork
tags: [docs, readme, claims, benchmark]
milestone: v4.4.0-multi-user-merge-automation
blocked_by: []
related: [feat--empirical-benchmark-harness-and-metrics, feat--git-level-gate-enforcement]
---

# Replace unverified performance and token-savings claims

## Problem

README and `docs/topic--system-comparisons.md` state figures that no code or data in the repository backs:

- "Sub-50ms" retrieval - the project's own `ADR-2026-09-09--kb-search-in-memory-ranking-vs-sqlite-fts5` targets `< 250ms` for 1,000 entities; no benchmark script exists.
- "85-95% token savings" - no measurement methodology or dataset.
- "12 protocol invariants" - `default_gates.yaml` defines 16 gates.
- "No direct monolithic counterparts" - comparable tools exist (GitHub spec-kit, Task Master, Beads, Kiro specs, native CLAUDE.md/AGENTS.md memory, Cursor rules).
- Runtime gates described as "hard runtime errors" without the caveat that they exist only in runtimes with Along hooks.

Unbacked numbers and absolute claims reduce trust with exactly the skeptical engineers the project targets.

## Requirements

- REQ-1: Add `scripts/bench_kb_search.py` (or a `along kb-search --bench` mode) that reports p50/p95 latency and returned-token counts on this repo and on a synthetic 1,000-entity fixture; publish the numbers with hardware and date.
- REQ-2: Replace "85-95%" with a measured comparison (tokens to answer N fixed questions via kb-search snippets vs. reading whole files), or remove it until `feat--empirical-benchmark-harness-and-metrics` delivers.
- REQ-3: Derive the invariant count from the gate catalogue (generated text) instead of hard-coding it.
- REQ-4: Rewrite the comparison page as a neutral feature/trade-off table including the tools above.
- REQ-5: Tone pass on README: fewer superlatives, one-sentence value proposition, quickstart first.

## Acceptance Criteria

- [ ] Every numeric claim in README links to a reproducible measurement
- [ ] Automated tests passing
