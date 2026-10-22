---
protocol: along
slug: requirement-format
title: Controlled Natural Language (STE-Inspired) Requirement Format
type: guide
created: 2026-10-22
updated: 2026-10-22
tags: [ste, cnl, requirements, specifications, convention, cross-runtime]
---

# Controlled Natural Language (STE-Inspired) Requirement Format

A pragmatic guide to writing unambiguous, testable specifications for human and agent workflows in Along repositories.

---

## 1. Background & Purpose

In multi-agent and cross-runtime workflows, requirements written by an architect model (such as a high-reasoning model) are handed off to cheaper implementer models and verified by automated reviewers.

When requirements contain vague wording, polite conditionals, or multiple actions per bullet, implementer models guess implementation details. This introduces defects and leads to repeated review rejection loops.

Along adopts principles inspired by Simplified Technical English (ASD-STE100) and Controlled Natural Language (CNL) as a **writing convention and handoff contract**, not as a brittle runtime gate.

---

## 2. The REQ-N Specification Pattern

Every requirement in an issue or implementation plan MUST follow the standardized atomic pattern:

```text
[Subject] + MUST | MUST NOT + [one verifiable action] + [object] + [condition]
```

### Core Rules

1. **One Observable Action**: Each requirement specifies exactly one verifiable, testable action. If an action has multiple parts, split it into separate requirements (`REQ-1`, `REQ-2`).
2. **Strict Imperative Keywords**: Use standard RFC 2119 imperatives: `MUST` for mandatory actions and `MUST NOT` for strict prohibitions.
3. **Explicit Condition**: State the triggering condition, input state, or boundary clearly (e.g., `when X occurs`, `if Y is omitted`, `under condition Z`).
4. **Verifiable Outcome**: State outcomes that can be confirmed through unit tests, exit codes, file states, or schema validators.

---

## 3. Banned Vague Terms

To prevent ambiguity, requirements MUST NOT include subjective qualifiers or open-ended phrasing.

| Banned Term | Why It Is Prohibited | Verifiable Alternative |
| :--- | :--- | :--- |
| `should`, `could`, `might` | Creates ambiguous obligation; implementer models may skip it. | Use `MUST` or `MUST NOT`. |
| `preferably` | Makes compliance optional without clear fallback rules. | State the exact required behavior or explicit fallback. |
| `appropriate`, `suitable` | Subjective judgment that automated tests cannot evaluate. | Specify exact status codes, types, or schemas. |
| `various`, `several` | Indeterminate quantity; impossible to know when scope is complete. | Enumerate items or state an explicit count/range. |
| `as needed`, `if possible` | Leaves scope decisions to the implementer model. | Define the exact condition when the action occurs. |
| `etc.`, `and so on` | Open-ended placeholder concealing unspecified requirements. | Explicitly list all required elements. |
| `fast`, `performant` | Unbounded performance claim without a metric. | Specify latency thresholds (e.g., `< 50ms at p99`). |

---

## 4. Good and Bad Specification Examples

### Example 1: Input Validation

- **Bad**:
  > `The system should preferably validate user registration input appropriately.`
  - *Flaws*: Uses `should`, `preferably`, and `appropriately`. Does not define which inputs, what validation rules apply, or what happens when validation fails.
- **Good**:
  > `The registration endpoint MUST return HTTP 400 with error code INVALID_EMAIL when the email address does not contain an @ character.`
  - *Why it works*: Explicit subject (`The registration endpoint`), keyword (`MUST`), single action (`return HTTP 400`), object (`error code INVALID_EMAIL`), and measurable condition (`when email lacks @`).

### Example 2: Caching Behavior

- **Bad**:
  > `Implement various caching mechanisms as needed for fast dashboard loading.`
  - *Flaws*: Uses `various`, `as needed`, and `fast`. Implementer must guess which cache backend, TTL, and cache key strategy to use.
- **Good**:
  > `The dashboard service MUST cache user project summaries in Redis for 300 seconds when the tenant has read-only access.`
  - *Why it works*: Identifies exact data (`user project summaries`), backend (`Redis`), duration (`300 seconds`), and trigger condition (`read-only access`).

### Example 3: CLI Error Handling

- **Bad**:
  > `The CLI could show helpful error messages etc. when things fail.`
  - *Flaws*: Uses `could`, `helpful`, `etc.`, and vague `when things fail`.
- **Good**:
  > `The CLI runner MUST write the subprocess exit code and stderr to standard error when a child process exits with non-zero code.`
  - *Why it works*: Names the exact output streams (`standard error`), content (`exit code and stderr`), and precise failure trigger (`child process non-zero exit`).

---

## 5. Convention vs Runtime Gate

Along purposefully treats STE-CNL as a **writing convention**, not as a runtime gate:

1. **No Brittle Linters**: Passive-voice detectors and regex word counters suffer from high false-positive rates on natural prose. Along does not block commits or builds on natural prose variations.
2. **Verbatim Handoff**: In cross-runtime handoffs (`feat--cross-runtime-handoff-entities`), tools like `along brief` forward the `## Requirements` section verbatim from architect to implementer and reviewer.
3. **Review Evaluation**: The reviewer role audits whether the diff satisfies `REQ-N` using test assertions and explicit rubric checks rather than checking grammar ASTs.
