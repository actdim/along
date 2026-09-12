---
protocol: along
slug: declarative-gates-and-traceability
title: Declarative Gate Engine & Protocol Traceability Matrix
type: architecture
created: 2026-09-13
updated: 2026-09-13
tags: [hooks, gates, declarative, traceability, verification, protocol, predicates]
sources:
  - path: scripts/alongkit/hooks/default_gates.yaml
  - path: scripts/alongkit/hooks/declarative.py
  - path: scripts/alongkit/hooks/predicates.py
  - path: scripts/alongkit/hooks/traceability.py
  - path: scripts/along_hook.py
---

# Declarative Gate Engine & Protocol Traceability Matrix

## 1. System Topology & Overview

Natural language guidelines and prose instructions in `AGENTS.md` and `skills/*/SKILL.md` are vulnerable to context truncation and probabilistic LLM compliance degradation. While runtime hooks provide interception at the agent harness boundary, hardcoded Python gates create maintenance overhead and opacity: agents and developers cannot easily inspect which prose instructions correspond to active enforcement logic.

The Along Declarative Gate Engine and Bi-Directional Traceability Matrix bridges this gap. It replaces opaque programmatic gates with an extensible, metadata-driven YAML gate catalogue (`scripts/alongkit/hooks/default_gates.yaml` and repository-level `.along/rules/gates.yaml`), paired with explicit inline prose badges (`[gate: <id>]`) embedded across protocol specifications and skill manifests.

```
+-------------------------------------------------------------------------+
|                  Prose Specifications & Skill Manifests                 |
|  AGENTS.md, skills/along-init/protocol.md, skills/along-commit/SKILL.md |
|  Embedded Badges: [gate: <id>] (e.g. [gate: commit_issue_binding])      |
+-------------------------------------------------------------------------+
                                    |
                    Machine-Checked Bi-Directional Audit
                    (along hook verify / traceability.py)
                                    v
+-------------------------------------------------------------------------+
|                   Declarative Gate Engine Catalogue                     |
|  scripts/alongkit/hooks/default_gates.yaml                              |
|  .along/rules/gates.yaml (repository overrides)                         |
+-------------------------------------------------------------------------+
       |                                                    |
       v (Regex/Match rules)                                v (Stateful predicates)
+----------------------------+             +------------------------------+
| Declarative Content Gates  |             | Stateful Predicates Engine   |
| - anti_stub_injection      |             | - require_active_issue       |
| - cli_safety               |             | - test_before_stop           |
| - projection_protection    |             | - wrap_before_stop           |
| - typography               |             | - projection_sync_before_stop|
| - commit_issue_binding     |             | - subproject_boundary        |
| - commit_no_conflict_marker|             +------------------------------+
+----------------------------+                            |
               \                                         /
                v                                       v
+-------------------------------------------------------------------------+
|                         Runtime Hook Execution                          |
|         Universal Dispatcher: scripts/along_hook.py                     |
|         Runtimes: Antigravity, Claude Code, OpenAI Codex                |
+-------------------------------------------------------------------------+
```

---

## 2. Core Components & Engine Implementation

### 2.1 Declarative Schema & Gate Catalogue (`default_gates.yaml`)

Gates are declared in YAML format with standard schema fields:
- `id`: Canonical identifier matching prose badges (e.g., `commit_issue_binding`).
- `description`: Human-readable summary of the invariant.
- `event`: Lifecycle trigger event (`PreToolUse`, `PostToolUse`, `Stop`).
- `decision`: Action on match (`deny`, `ask`, `force_ask`).
- `target_tools`: List of tools intercepted (e.g., `run_command`, `write_to_file`).
- `match_type`: Evaluation strategy (`regex`, `predicate`, `composite`).
- `patterns`: Regex patterns for argument matching (for `regex` matchers).
- `predicate`: Name of python predicate handler in `alongkit.hooks.predicates`.
- `remediation`: Explicit remediation message returned to the agent on violation.

The 11 canonical gates defined in the catalogue:
1. `commit_issue_binding`: Intercepts `git commit` to require issue binding (`--issue` or `(<type>--<slug>)`).
2. `commit_no_conflict_markers`: Intercepts `git commit` to reject unresolved merge conflict markers (`<<<<<<<`, `=======`, `>>>>>>>`).
3. `anti_stub_injection`: Intercepts file mutation tools to forbid stub markers (`// ... rest of code`, `/* existing code */`).
4. `cli_safety`: Intercepts shell commands to block heredocs (`<<EOF`), inline python file writers, destructive wipes (`git reset --hard`), and global installs.
5. `projection_protection`: Intercepts file writes to derived projections (`.along/ISSUES.md`, `docs/INDEX.md`, `DECISIONS.md`).
6. `typography`: Intercepts text writes to enforce ASCII typography (no em-dashes, curly quotes, guillemets, ellipsis glyphs, or NBSP).
7. `require_active_issue`: Stateful predicate requiring an active `in-progress` issue in `.along/ISSUES/` before modifying repository source code.
8. `test_before_stop`: Intercepts session termination (`Stop`) to ensure `/along-test` or test suites ran cleanly if code was modified.
9. `wrap_before_stop`: Intercepts session termination (`Stop`) to ensure a session log exists if an issue was marked done.
10. `projection_sync_before_stop`: Intercepts session termination (`Stop`) to require `/along-issue-sync` if issue files changed.
11. `subproject_boundary`: Enforces context localization in monorepos, preventing subproject entities from leaking to workspace root `.along/`.

### 2.2 Stateful Predicate Handlers (`alongkit.hooks.predicates`)

While regex gates evaluate single tool calls in isolation, complex invariants require session state:
- `record_tool_activity()`: Records executed commands and modified paths into `.along/diagnostics/activity_trace.jsonl`.
- `load_activity_trace()`: Reconstructs session tool call history to evaluate post-conditions.
- Predicate functions (`check_require_active_issue`, `check_test_before_stop`, `check_wrap_before_stop`, `check_projection_sync_before_stop`, `check_subproject_boundary`) return a violation message string or `None`.

### 2.3 Bi-Directional Traceability Scanner (`alongkit.hooks.traceability`)

The traceability engine guarantees zero drift between written instructions and active enforcement:
- `scan_prose_anchors()`: Parses Markdown files across `AGENTS.md` and `skills/*/SKILL.md` using regex `r"\[gate:\s*([a-zA-Z0-9_-]+)\]"`.
- `audit_traceability()`: Correlates prose anchors against active gates loaded from YAML.
  - Reports missing anchors (gates defined in YAML with no prose badge).
  - Reports dangling badges (badges in prose with no corresponding YAML gate).
  - Returns boolean pass/fail status.
- CLI verification: `along hook verify` (or `python scripts/along_hook.py verify`) runs the audit and outputs a structured matrix report.

---

## 3. Data Flow & Execution Workflow

### 3.1 Declarative Gate Evaluation Flow

```
[Tool Invocation Event]
          |
          v
[Declarative Engine: load_gates()]
  Reads: scripts/alongkit/hooks/default_gates.yaml
  Reads: .along/rules/gates.yaml (if present)
          |
          v
[Filter Gates by event_type and target_tools]
          |
   +------+------+
   |             |
(Regex)     (Predicate)
   |             |
   |             +--> [Execute alongkit.hooks.predicates]
   |                  Reads repository state & activity trace
   v                  Returns violation string or None
[Regex Match on Args]    |
   |                     |
   +----------+----------+
              |
         (Violation?)
          /        \
        YES         NO
         |           |
         v           v
    [GateResult:   [GateResult:
     DENY]          ALLOW]
```

### 3.2 Machine-Checked Traceability Verification Flow

```
[Developer / Agent invokes: along hook verify]
                       |
                       v
         [audit_traceability(repo_root)]
          /                           \
         v                             v
[Parse Prose Badges]          [Load Declarative Gates]
AGENTS.md, skills/*/SKILL.md   default_gates.yaml + gates.yaml
         \                             /
          v                           v
         [Cross-Reference Badges <-> Gate IDs]
                       |
        +--------------+--------------+
        |                             |
 (Clean 1:1 Match)             (Drift Detected)
        |                             |
        v                             v
[Verdict: PASSED]             [Verdict: FAILED]
Exit Code: 0                  Exit Code: 1 (lists missing/dangling)
```

---

## 4. Invariants & Failure Modes

1. **Strict Bi-Directional Traceability Invariant**:
   - Every active gate in `default_gates.yaml` MUST have at least one corresponding `[gate: <id>]` badge in prose documentation (`AGENTS.md` or `skills/`).
   - Every `[gate: <id>]` badge in documentation MUST map to an active gate in the catalogue.
   - `along hook verify` MUST exit with code 0 in CI and local test suites (`tests/test_gates_traceability.py`).
2. **Deterministic Isolation**:
   - Predicate handlers and file parsers use narrow exception handling `(OSError, UnicodeDecodeError, ValueError)`. Generic exceptions (`except Exception:`) and unhandled crashes are forbidden.
3. **Repository Extensibility**:
   - Projects can extend or override default gates by adding `.along/rules/gates.yaml`.
   - Repository-specific gates are merged with `default_gates.yaml`, allowing local project rules to participate in declarative verification.
4. **Hermetic Test Guarantees**:
   - All tests for declarative gate loading, predicate evaluation, and traceability verification run strictly within throwaway temporary directories (`tempfile.mkdtemp()`).
