---
protocol: along
protocol_version: 2.2.8
slug: always-on-context-budget-exceeds-claims
type: debt
status: open
priority: high
created: 2026-09-01
updated: 2026-09-01
agent: claude-code
tags: [token-efficiency, context-budget, rules, projections, claims]
milestone: v3.0.0-global-quality-revision
blocked_by: []
related: [protocol-documentation-drift, kb-search-ranking-and-snippet-quality, team-skill-state-not-persisted]
parent: protocol-quality-audit-remediation
---

# Always-on context cost contradicts the token-efficiency claims

## Measured cost per session

```text
AGENTS.md                     22.5 KB   loaded automatically every session
~/.claude/rules/*.md (11)     41.5 KB   loaded globally, for every project
.along/DECISIONS.md           26.3 KB   mandatory session-start read (AGENTS.md item 3)
.along/ISSUES.md               5.5 KB   mandatory session-start read (AGENTS.md item 2)
                             --------
                              95.8 KB   roughly 25-27k tokens before any useful work
```

Claims being contradicted:

- `README.md:19` - "95-98% token reduction on retrieval".
- `README.md:21` - "Zero Bookkeeping Overhead".
- `AGENTS.md` - "Keep `ISSUES.md` compact - it costs context every session".
- `AGENTS.md` - "Context & Token hygiene: Keep tool output lean to prevent context bloat".

## Specific structural causes

### 1. All rule packs load for every project

`rules/INDEX.md` documents an Automatic Detection Matrix: `/along-init` inspects project
descriptors and attaches only the matching rule packs to `AGENTS.md`. In practice
`install.ps1:108-117` copies all eleven packs into `~/.claude/rules/`, where they are loaded
for every session in every repository. A Python project pays for the C#, Rust, mobile,
desktop, CLI, and backend packs on every request. The detection matrix is designed but
bypassed by the installation model.

### 2. DECISIONS.md is append-only, mandatory, and unbounded

`AGENTS.md` requires reading `.along/DECISIONS.md` at session start. The file is append-only
by design and already 26.3 KB with 18 ADRs. Cost grows linearly and forever, with no index,
no summary, and no supersession pruning. ADR-2026-08-15 justifies the single-file design with
"Agents read all active constraints on session start in one tool call (< 300 tokens)"; the
actual figure is roughly 7000 tokens, a 20x divergence from the recorded rationale.

### 3. The "compact board" contains the full history

`.along/ISSUES.md` has a `## Done (recent)` section listing all 36 completed issues. The
`issue sync` generator applies no cap, so the board grows without bound while the protocol
instructs agents to keep it compact.

### 4. Protocol text duplicated five times

See `[debt--protocol-documentation-drift]`. Beyond drift, the duplication means the same
content can be loaded more than once in a single session (`AGENTS.md` plus a docs article
plus `llms.txt`).

### 5. No measurement

Nothing in the repository measures its own context cost, so the efficiency claims are
unverifiable and cannot regress-test.

## Impact

The product's headline value is context efficiency for agents. Its actual always-on cost is
substantial and grows monotonically with project history. For small repositories the
bookkeeping context can exceed the code context.

## Requirements

- REQ-1: Add a measurement tool (`along_exec.py context-budget`) reporting bytes and
  estimated tokens for: auto-loaded files, mandatory session reads, and per-skill overhead.
  Emit JSON for regression tracking.
- REQ-2: Set explicit budgets and enforce them by test, for example: `AGENTS.md` under
  12 KB, `ISSUES.md` under 4 KB, mandatory session reads under 40 KB total. Fail the suite
  when a budget is exceeded.
- REQ-3: Implement per-stack rule attachment as `rules/INDEX.md` already specifies: install
  rule packs into a namespaced directory and have `/along-init` reference only the matching
  packs from the project's `AGENTS.md`, instead of loading all of them globally.
- REQ-4: Restructure the decision log for bounded cost. Options to evaluate and record as an
  ADR: split into `.along/DECISIONS/<slug>.md` with a compact index of active constraints
  only; or keep the single file plus a generated `DECISIONS-ACTIVE.md` summary that excludes
  superseded entries, and make the summary the mandatory read.
- REQ-5: Cap `## Done (recent)` in the projection (for example the 10 most recent) and move
  the rest to a generated archive view.
- REQ-6: Generate the duplicated documentation instead of maintaining copies
  (`[debt--protocol-documentation-drift]` REQ-1).
- REQ-7: Re-derive the published claims from measurements, or remove the specific
  percentages. Update `README.md`, and correct or supersede
  `ADR-2026-08-15--single-file-append-only-decisions` where its "< 300 tokens" rationale no
  longer holds.

## Acceptance Criteria

- [ ] `context-budget` tool implemented with JSON output.
- [ ] Budget tests in place and green.
- [ ] Rule packs attached per detected stack, not loaded globally for all projects.
- [ ] Mandatory session reads bounded and non-growing with history.
- [ ] Published efficiency claims backed by measurement or removed.
- [ ] ADR recorded for the decision-log restructuring.
