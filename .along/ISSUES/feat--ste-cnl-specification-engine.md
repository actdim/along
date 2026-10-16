---
protocol: along
protocol_version: "4.4.15"
slug: ste-cnl-specification-engine
type: feat
status: open
priority: medium
created: 2026-10-16
updated: 2026-10-16
agent: antigravity
tags: [ste, cnl, quality-gate, specifications, linter]
milestone: v4.6.0-structured-state-and-blackboard-engine
blocked_by: []
related: [docs--ground-topic-based-docs, feat--declarative-gates-and-protocol-traceability]
---

# Controlled Natural Language (STE) Specification Engine & Quality Gate

## Goal

Integrate principles of Simplified Technical English (ASD-STE100 / Controlled Natural Language) into Along, providing formal specification patterns for issue requirements (`REQ-N`), deterministic agent rule enforcement, and an automated mechanical linting gate (`along ste-check`) to eliminate prompt ambiguity, soft prompt decay, and token waste.

## Problem Statement

1. **Natural Language Ambiguity in Specifications**:
   Requirements and protocol rules written in conversational, unconstrained prose lead AI coding agents to hallucinate implicit behavior, misinterpret architectural boundaries, and generate incomplete test coverage.
2. **Soft Prompt Decay in Agent Rules**:
   Long, compound, passive-voice sentences in rule packs (`AGENTS.md`, `.along/rules/`) degrade model instruction-following as conversation turns multiply. Models prioritize recent context over ambiguous instructions.
3. **Prompt Token Footprint Inflation**:
   Unconstrained prose in specifications and living documentation consumes 30% to 50% more tokens than necessary, diluting the information density of progressive disclosure snippets retrieved by `along-kb-search`.

## Technical Specifications

### 1. Formal STE Requirement Assertion Pattern (`REQ-N`)
Establish a standardized syntax contract for all formal requirements in `.along/ISSUES/` and living plan specifications:
- Syntax: `[Subject] + [MUST | MUST NOT | OPTIONAL] + [Imperative Action Verb] + [Target Object] + [Condition / Boundary]`.
- Enforce strict single-action atomicity: exactly one observable verification action per requirement sentence.
- Prohibit ambiguous modal operators (`should`, `could`, `might`, `preferably`).

### 2. Mechanical STE Linter & Quality Gate (`SteComplianceGate`)
Implement a deterministic lexical analysis engine in `alongkit.validation.ste`:
- **Sentence Length Limit**: Flag sentences exceeding 25 words in specification and rule sections (`## Requirements`, `## Acceptance Criteria`).
- **Passive Voice Detector**: Detect passive verb constructs (`is/are/was/were/be/been + past participle`) and require active imperative voice.
- **Fuzzy Lexicon / Hedging Filter**: Reject ambiguous qualifiers in specifications (`various`, `appropriate`, `etc.`, `and so on`, `as needed`, `flexible`, `preferably`).
- **Imperative Rule Enforcement**: Verify that behavioral rules in protocol packs begin with directive action verbs (`Run`, `Verify`, `Reject`, `Inspect`, `Write`).

### 3. CLI Subcommand & KB Sync Integration
- Expose verification via CLI:
  ```bash
  along ste-check [PATH] [--strict]
  ```
- Integrate optional STE compliance auditing into knowledge base compilation:
  ```bash
  along kb-sync --check-ste
  ```

### 4. Topic Reference Documentation
Publish `docs/topic--controlled-natural-language.md` covering:
- Industrial lineage: ASD-STE100 (aerospace maintenance), Attempto Controlled English (ACE), and DITA technical writing.
- Quantitative benchmarks: token footprint reduction and model instruction-following accuracy.
- Authoring guide for engineering teams.

## Requirements

- `REQ-1`: The engine MUST parse Markdown files and isolate specification blocks (`## Requirements`, `## Acceptance Criteria`) from free-form narrative prose.
- `REQ-2`: The linter MUST emit a warning when a specification sentence exceeds 25 words.
- `REQ-3`: The linter MUST detect passive voice constructs and suggest active imperative alternatives.
- `REQ-4`: The linter MUST reject banned ambiguous hedging terms (`various`, `etc.`, `appropriate`, `as needed`).
- `REQ-5`: The CLI MUST expose `along ste-check` returning exit code 0 on clean scan and exit code 1 when `--strict` encounters violations.
- `REQ-6`: All tests MUST execute against hermetic throwaway directories without mutating live repository files.

## Acceptance Criteria

- [ ] Core validation module `alongkit.validation.ste` implemented with sentence tokenization, passive voice detection, and stop-word filtering.
- [ ] Declarative gate `SteComplianceGate` registered in `default_gates.yaml` and wired to `along_hook.py`.
- [ ] CLI subcommand `along ste-check` implemented in `scripts/along_ste_check.py` and registered in `along_exec.py`.
- [ ] Integration with `along kb-sync --check-ste` implemented for knowledge base articles.
- [ ] Documentation published in `docs/topic--controlled-natural-language.md` and indexed in `docs/INDEX.md`.
- [ ] Hermetic unit tests in `tests/test_ste_linter.py` passing with 100% coverage of validation rules.
