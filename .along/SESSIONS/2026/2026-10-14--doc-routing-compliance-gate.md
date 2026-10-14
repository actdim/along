---
protocol: along
protocol_version: "4.4.13"
date: 2026-10-14
slug: doc-routing-compliance-gate
agent: antigravity
branch: main
commit: 02c7b9c
summary: Enforce Documentation Routing Tree via doc-routing-compliance gate
issues_advanced: []
issues_completed: [feat--doc-routing-compliance-gate]
decisions: []
risks_logged: []
spikes_conducted: []
---

# Session: Doc routing compliance gate

## Summary
Enforce Documentation Routing Tree via doc-routing-compliance gate

## Decisions
- None (confirmed at wrap: no architectural decisions).

## Blackboard Record

Execution mode: direct; plan revision 1; approved: true.

### Attributed Files

| Path | Kind | Edits | Last edit | Sessions |
| --- | --- | --- | --- | --- |
| `.along/ISSUES/feat--doc-routing-compliance-gate.md` | state | 1 | 2026-10-14T13:26:59Z | antigravity--8be12411-e7f3-40e0-8483-432a82f228f3 |
| `AGENTS.md` | docs | 1 | 2026-10-14T13:23:45Z | antigravity--8be12411-e7f3-40e0-8483-432a82f228f3 |
| `docs/topic--declarative-gates-and-traceability.md` | docs | 1 | 2026-10-14T13:27:32Z | antigravity--8be12411-e7f3-40e0-8483-432a82f228f3 |
| `docs/topic--runtime-hooks-and-gates.md` | docs | 1 | 2026-10-14T13:24:00Z | antigravity--8be12411-e7f3-40e0-8483-432a82f228f3 |
| `scripts/along_exec.py` | source | 1 | 2026-10-14T13:23:33Z | antigravity--8be12411-e7f3-40e0-8483-432a82f228f3 |
| `scripts/along_kb_sync.py` | source | 2 | 2026-10-14T13:23:19Z | antigravity--8be12411-e7f3-40e0-8483-432a82f228f3 |
| `scripts/alongkit/gitgates.py` | source | 3 | 2026-10-14T13:22:16Z | antigravity--8be12411-e7f3-40e0-8483-432a82f228f3 |
| `scripts/alongkit/hooks/default_gates.yaml` | source | 1 | 2026-10-14T13:21:23Z | antigravity--8be12411-e7f3-40e0-8483-432a82f228f3 |
| `scripts/alongkit/hooks/predicates.py` | source | 2 | 2026-10-14T13:25:51Z | antigravity--8be12411-e7f3-40e0-8483-432a82f228f3 |
| `scripts/alongkit/repochecks.py` | source | 4 | 2026-10-14T13:26:04Z | antigravity--8be12411-e7f3-40e0-8483-432a82f228f3 |
| `skills/along-init/protocol.md` | source | 1 | 2026-10-14T15:00:31Z | antigravity--8be12411-e7f3-40e0-8483-432a82f228f3 |
| `tests/test_doc_routing_gate.py` | source | 6 | 2026-10-14T15:01:31Z | antigravity--8be12411-e7f3-40e0-8483-432a82f228f3 |

### Plan

#### Plan: doc-routing-compliance-gate

##### Objective
Implement `[gate: doc-routing-compliance]` to mechanically enforce the Along Documentation Routing Tree:
- Public overview / pitch / landing page -> README.md
- Technical interface contract / CLI spec -> docs/topic--<slug>.md (type: reference)
- Conceptual explanation / comparison / philosophy -> docs/topic--<slug>.md (type: explanation, write_policy: manual)
- Procedural walkthrough / runbook -> docs/topic--<slug>.md (type: guide)
- Architectural choice / trade-off -> .along/DECISIONS/ (ADR)

This prevents technical bloat, embedded coding rule packs, and deep code specification dumps in `README.md`, and prevents `AGENTS.md` from treating `README.md` as the conventions source of truth instead of `docs/`.

##### Architecture & Components

###### 1. Core Detection Engine (`alongkit.repochecks` & `alongkit.kb`)
- Add `check_doc_routing_compliance(paths, read, options)` in `scripts/alongkit/repochecks.py`.
- Inspection Rules for `README.md`:
  - Deep code fences: any code fence (` ``` ` or ` ~~~ `) exceeding 50 lines.
  - Bloated technical reference / convention sections: sections with headings matching conventions, coding standards, architectural rules, interface contracts, API reference, or rule packs that exceed 50 lines of specification.
  - Overall bloated README (>300 lines) with technical specification sections.
  - Pragma exemption: `along: allow-doc-routing-compliance` bypasses checks for test fixtures.
- Inspection Rules for `AGENTS.md`:
  - Flag references pointing to `README.md` as the source of truth for coding conventions or architecture rules (e.g. `[.*conventions.*](.*README\.md.*)` or `[.*rules.*](.*README\.md.*)` or "conventions documented in README.md").
  - Enforce routing to `docs/topic--<slug>.md` or `docs/INDEX.md`.

###### 2. Runtime PreToolUse Gate (`alongkit.hooks.predicates`)
- Add `check_doc_routing_compliance(event, repo_root, **kwargs)` in `scripts/alongkit/hooks/predicates.py`.
- Intercepts file mutation tools (`write_to_file`, `write_file`, `replace_file_content`, `edit_file`, `patch_file`, `create_file`).
- When target file is `README.md` (root or subproject), evaluates the resulting content against doc routing invariants.
- Blocks violations with clear remediation pointing to `docs/topic--<slug>.md`.

###### 3. Declarative Gate Catalogue (`default_gates.yaml`)
- Register `doc_routing_compliance` in `scripts/alongkit/hooks/default_gates.yaml`:
  - `id: doc_routing_compliance`
  - `profiles: { strict: block, standard: block, light: warn }`
  - `enforcement: [runtime, git, ci]`
  - `event: PreToolUse`
  - `tools: [write_to_file, write_file, replace_file_content, edit_file, patch_file, create_file]`
  - `handler: alongkit.hooks.predicates.check_doc_routing_compliance`

###### 4. Git Hooks & CI Pipeline Integration (`alongkit.gitgates`)
- Wire `check_doc_routing` into `scripts/alongkit/gitgates.py`:
  - `check_pre_commit`: inspects staged `README.md` and `AGENTS.md` files.
  - `check_ci`: inspects all tracked `README.md` and `AGENTS.md` files across repository and subprojects.

###### 5. Static Inspection in `along kb sync` and `along doctor`
- In `scripts/along_kb_sync.py`:
  - Add `_kb_validate_doc_routing(repo_root, check_only)` during Knowledge Base sync.
  - Warns on bloat and exits with error in `--check` mode when violations exist.
- In `scripts/along_exec.py`:
  - Add `doc-routing-compliance` diagnostic check to `along doctor`.

###### 6. Protocol Badge & Documentation Anchor
- Update `AGENTS.md` line 51 with anchor:
  `- **Documentation Routing Tree** [gate: doc-routing-compliance]:`
- Document gate in `docs/topic--runtime-hooks-and-gates.md`.

###### 7. Hermetic Verification Suite
- Create `tests/test_doc_routing_gate.py`:
  - Unit tests for deep code fence detection (> 50 lines).
  - Unit tests for bloated convention sections (> 50 lines).
  - Unit tests for AGENTS.md conventions references to README.md.
  - Unit tests for pragma `along: allow-doc-routing-compliance`.
  - Runtime predicate denial tests on `write_to_file` and `replace_file_content`.
  - Git pre-commit and CI tests via throwaway Git repositories.
  - Verify `test_gates_traceability.py` passes with zero dangling references and clean schema.

### Execution Trace

#### Execution Trace: doc-routing-compliance-gate
- 2026-10-14T09:55:57Z denied [require_plan_approval] run_command: Unclassified Tool Nature [gate: require-plan-approval]: Tool or command 'where-object {' has unclassified nature. Ask the user for its nature (read-only, ver...
- 2026-10-14T13:18:00Z plan approved (along plan approve) approved_via: cli-unverified, plan_sha256: bc5023240607
- 2026-10-14T13:20:31Z edit scripts/alongkit/repochecks.py (x3)
- 2026-10-14T13:21:10Z edit scripts/alongkit/hooks/predicates.py
- 2026-10-14T13:21:23Z edit scripts/alongkit/hooks/default_gates.yaml
- 2026-10-14T13:22:16Z edit scripts/alongkit/gitgates.py (x3)
- 2026-10-14T13:23:19Z edit scripts/along_kb_sync.py (x2)
- 2026-10-14T13:23:33Z edit scripts/along_exec.py
- 2026-10-14T13:23:45Z edit AGENTS.md
- 2026-10-14T13:24:00Z edit docs/topic--runtime-hooks-and-gates.md
- 2026-10-14T13:25:17Z edit tests/test_doc_routing_gate.py
- 2026-10-14T13:25:51Z edit scripts/alongkit/hooks/predicates.py
- 2026-10-14T13:26:04Z edit scripts/alongkit/repochecks.py
- 2026-10-14T13:26:59Z edit .along/ISSUES/feat--doc-routing-compliance-gate.md
- 2026-10-14T13:27:32Z edit docs/topic--declarative-gates-and-traceability.md
- 2026-10-14T14:54:33Z denied [cli_safety] run_command: CLI Safety Gate Violation: Ad-hoc internal module probe via python -c [gate: cli_safety] (use Along CLI, code search tools, or a scratch/ script) detected in...
- 2026-10-14T14:56:20Z denied [require_plan_approval] run_command: Unclassified Tool Nature [gate: require-plan-approval]: Tool or command '$env:antigravity_conversation_id' has unclassified nature. Ask the user for its natu...
- 2026-10-14T15:00:06Z test FAIL (along test)
- 2026-10-14T15:00:31Z edit skills/along-init/protocol.md
- 2026-10-14T15:01:31Z edit tests/test_doc_routing_gate.py (x5)
- 2026-10-14T15:02:29Z test pass (along test)
