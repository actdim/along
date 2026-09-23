---
name: along-team
description: Execute software development tasks via sequential multi-agent protocol (Supervisor -> Research -> Architect -> Living Plan -> Step Loops [Implement -> Review/Test -> Reassess]). Supports autonomous execution, /goal integration, and adaptive complexity routing.
---

# Along Team (`/along-team`)
Universal sequential development protocol and state machine for complex engineering tasks across all supported AI providers.

---

## Core Philosophy

> **Plan globally, execute locally, verify after every step, replan whenever reality differs from the plan.**

The protocol replaces unstructured multi-agent chat and parallel swarms with a **deterministic sequential state machine**. It functions identically whether executed via multi-agent subagent primitives or single-agent sequential role execution.

---

## When to Use & Triggers

- **Explicit Skill Invocation**: `/along-team <issue-slug>` or `/along-team` with a task description.
- **Worktree Isolation Mode**: `/along-team <issue-slug> --worktree`, `/goal --worktree`, or configuration `workspace: worktree`.
- **Autonomous Goal Trigger**: Whenever `/goal` is invoked or high-autonomy mode is requested for feature implementation.
- **Natural Language Triggers**: "Execute issue via team", "Run multi-agent pipeline", "Implement with agent team", "in an isolated worktree", "run without touching active workspace".
- **False-Positive Guard**: Standard requests lacking explicit isolation intent ("implement feature", "fix bug") default strictly to `workspace: inherit` to avoid unnecessary worktree provisioning overhead.

---

## Adaptive Complexity Routing (T-Shirt Sizing)

Before spawning subagents or running multi-phase loops, the **Supervisor** evaluates task complexity to prevent token explosion:

| Size | Scope & Characteristics | Execution Path |
| :--- | :--- | :--- |
| **`S-Size`** | 1-2 files, clear scope, no architectural unknowns. | **Fast-Path**: Single-agent direct execution + automated tests. Zero subagents spawned. |
| **`M-Size`** | 3-5 files, isolated module/route, clear interface. | **Fast Loop**: Scout (`spawn_readonly_researcher`) -> Implementer (`spawn_worker`) -> Reviewer (`spawn_reviewer`) in one pass. |
| **`L / XL-Size`** | Cross-module impact, core refactoring, protocol migration, architectural unknowns. | **Full Protocol**: Complete sequential state machine with Step-by-Step Living Plan and Reassess loops. |

---

## Provider Capability Abstraction & Primitive Mapping

All roles map to abstract orchestration primitives rather than provider-specific APIs:

1. **`spawn_readonly_researcher`**: Spawns an isolated exploratory worker with read-only tools to gather facts, symbols, and constraints. Zero write tools enabled.
2. **`spawn_worker`**: Spawns an implementation worker scoped strictly to the current Living Plan step.
3. **`spawn_reviewer`**: Spawns an independent gatekeeper to execute the verification rubric, run tests, and audit diffs.

### Provider Mapping Table

| Provider | `spawn_readonly_researcher` | `spawn_worker` | `spawn_reviewer` | Fallback Behavior |
| :--- | :--- | :--- | :--- | :--- |
| **Google Antigravity** | `invoke_subagent` (`TypeName: "research"`, `Role: "Scout"`) | `invoke_subagent` (`TypeName: "self"`, `Role: "Implementer"`, `Workspace: "inherit"`) | `invoke_subagent` (`TypeName: "self"`, `Role: "Code Reviewer"`) | Single-Agent Fallback if subagents fail |
| **Claude Code** | `Task` tool (role: Scout, instructions: read-only analysis) | `Task` tool (role: Implementer, step-scoped instructions) | `Task` tool (role: Reviewer, rubric verification prompt) | Single-Agent Fallback if Task tool unavailable |
| **OpenAI Codex** | Single-Agent Fallback (Phase 1 inline) | Single-Agent Fallback (Phase 3 inline) | Single-Agent Fallback (Phase 4 inline) | Native execution mode |
| **OpenCode** | Single-Agent Fallback (Phase 1 inline) | Single-Agent Fallback (Phase 3 inline) | Single-Agent Fallback (Phase 4 inline) | Native execution mode |

---

## Single-Agent Degradation Path (Ralph-Style Execution)

When subagent spawning is unavailable (OpenAI Codex, OpenCode) or disabled/throttled (Google Antigravity, Claude Code), the state machine executes in **Single-Agent Sequential Mode** (Ralph Loop pattern):

1. **Deterministic Phase Boundaries**: The single agent explicitly announces each phase in output:
   - `=== PHASE 0: SUPERVISOR (REQUIREMENT EXTRACTION) ===`
   - `=== PHASE 1: SCOUT (READ-ONLY RESEARCH) ===`
   - `=== PHASE 2: ARCHITECT (LIVING PLAN) ===`
   - `=== PHASE 3: IMPLEMENTER (STEP N EXECUTION) ===`
   - `=== PHASE 4: REVIEWER (RUBRIC AUDIT & TESTS) ===`
   - `=== PHASE 5: REASSESS (VERDICT & RETRY EVALUATION) ===`
2. **Blackboard Persistence**: State is externalized to disk at `.along/.session/<slug>/` (`state.json`, `plan.md`, `research.md`, `reviews/step-<N>.md`, `execution_trace.md`). Initialized via `along scratch init <slug>`. Inspect state at any time via `along scratch state <slug>` (`--json`). Resumption automatically reads `state.json` and resumes from `current_step` unless `--restart` is passed.
3. **Explicit Review Verdicts**: The agent evaluates the step against the Reviewer Rubric and outputs a mandatory verdict block:
   ```text
   VERDICT: PASS
   # or
   VERDICT: FAIL
   ISSUES:
   1. [Check Name]: Concrete reason for failure...
   ```
4. **Retry Counters**: Tracked on disk in `state.json` via `along scratch update <slug> --step <N> --inc-retry` (maximum 2 retries per step, governed by `retry_limit`). If the retry limit is exceeded, execution immediately halts and escalates to the human user.
5. **CLI Resolution & Fallback**: Agents invoke `along <subcommand>` (e.g. `along scratch init <slug>`). If `along` is not found on `PATH`, fallback to `~/.along/bin/along.cmd <subcommand>` (Windows), `~/.along/bin/along <subcommand>` (POSIX), or `python ~/.along/bin/along_exec.py <subcommand>`.

---

## Isolated Workspace Contract

Workspaces isolate changes during step implementation:

- **Default Mode (`Workspace: "inherit"`)**: Implementer executes directly in the primary working tree. This is the universal default across all providers and avoids git merge complexity.
- **Worktree Mode (`Workspace: "worktree"` / `--worktree`)**: Available across all platforms via the `along worktree` engine (`scripts/alongkit/worktree.py`) and host-assisted providers (Google Antigravity `Workspace: "branch" | "share"`, Claude Code `--worktree`).
  - **Environment Readiness Contract** [gate: worktree-env-readiness]: Bare `git worktree add` checkouts lack gitignored dependencies and local configuration, which immediately crashes test runners. Before worker execution begins, the orchestrator satisfies three readiness prerequisites:
    1. **Dependency Linking**: Heavy package directories (`node_modules`, `.venv`, `venv`) are linked from the primary repository to the worktree via NTFS directory junctions on Windows (`mklink /J`) or symbolic links on POSIX (`os.symlink`) without duplicating storage. Mutating operations (`npm install`, `pip install`) inside worktrees affect parent packages through junctions and are forbidden without confirmation.
    2. **Configuration Propagation**: Untracked configuration files (`.env`, `.env.local`, `local.settings.json`) are copied into the worktree so runtime secrets and flags are available.
    3. **State Preservation**: The session blackboard (`.along/.session/<slug>/`) is linked or flushed before teardown to ensure failure forensics, retry counters, and session logs survive worktree pruning.
  - **Strict Fail-Fast Policy**: In Phase 0 (Supervisor), the orchestrator verifies host runtime and filesystem capability (`along worktree is_supported`). If `--worktree` or semantic isolation was requested but environment readiness cannot be satisfied (unsupported filesystem, uncommitted merge conflicts, broken junctions), the agent **MUST IMMEDIATELY HALT WITH AN ERROR**. Silent fallback to the primary working tree is strictly forbidden.
  - **Branch Naming**: `along/<issue-slug>` (or `along/<issue-slug>/step-<N>`).
  - **Merge Strategy**: Fast-forward or squash merge (`along worktree merge <slug> --squash`) into the parent working branch upon Reviewer `PASS`.
  - **Conflict Handling**: If merge conflicts arise during squash/merge, the Supervisor discards the worktree, creates a fresh branch from current HEAD, and retries the step.
  - **Teardown & Windows Lock Resilience**: Worktrees are safely pruned via `along worktree remove <slug> --force`. On Windows NTFS, file handle locks from language servers or indexers are mitigated through junction pre-unlinking (`os.rmdir`), CWD reset to repo root, an exponential backoff retry loop (4 attempts, 0.5s backoff), and deferred garbage collection via `.along/.pending_worktrees.json` and `along worktree gc`.
  - **Non-Worktree Fallback**: When `--worktree` is not requested, all steps operate in the main working tree guarded by `git diff` review and `git checkout` rollback.

---

## Conditional & Observable Reviewer Rubric

The Reviewer rubric gates every step. Every check is conditional, resilient, and observable:

1. **Zero-Byte & File Integrity Gate**: Mandatory. Inspects created, modified, and untracked files (`git status -u`). Verifies `size > 0` bytes and ensures no empty placeholders or truncated bodies exist. Status: `EXECUTED`.
2. **Automated Tests**: Mandatory when a test runner is present. Resolves canonical test command: `along test` (if on `PATH`) or `python <resolved>/along_exec.py test` or native package runner (`pytest -q`, `python -m unittest`, `npm test`, `cargo test -q`, `dotnet test -v q`). If no test runner exists in the repository, marks as `SKIPPED (no test runner detected)`. Status: `EXECUTED` | `SKIPPED`.
3. **Diff & Scope Audit**: Mandatory. Inspects `git diff` for out-of-scope modifications, broken imports, or incomplete logic. Status: `EXECUTED`.
4. **Requirement Traceability Gate**: Mandatory. Verifies the diff satisfies the atomic requirements (`REQ-N`) defined for Step N. Status: `EXECUTED`.
5. **Blast Radius & Architecture**:
   - Mandatorily executes `/along-graph-impact` (or `along graph-impact <symbol|file>`) on all modified symbols and files.
   - If `code-review-graph` is available: traces callers, callees, and affected flows. Status: `EXECUTED (code-review-graph)`.
   - If `code-review-graph` is unavailable/disconnected: executes static search fallback with an explicit warning. Status: `DEGRADED (static search, MCP unavailable)`.
   - Verifies compliance with `.along/DECISIONS.md`.
6. **Documentation & Public Surface Parity**: If public interfaces, commands, skills, or entities changed, verifies that BOTH `docs/topic--*.md` articles AND public entry points (`README.md`, `AGENTS.md`) reflect modifications. Status: `EXECUTED` | `SKIPPED (no public interface changes)`.
7. **Typography & Clean ASCII**: Mandatory. Verifies clean UTF-8 ASCII without forbidden typographic characters (em-dash, curly quotes, non-breaking spaces). Status: `EXECUTED`.

### Gate Execution Manifest

Every Reviewer report and session log MUST conclude with an explicit Gate Execution Manifest:

```text
Gate Execution Manifest:
- Workspace Isolation: EXECUTED (PASS) [mode: worktree, path: .along/worktrees/<slug>]
- Environment Readiness: EXECUTED (PASS) [junctions: node_modules, .venv; copied: .env; blackboard: linked]
- File Integrity: EXECUTED (PASS)
- Automated Tests: EXECUTED (PASS) [along test]
- Diff Scope Audit: EXECUTED (PASS)
- Requirement Traceability: EXECUTED (PASS) [REQ-1, REQ-2]
- Blast Radius: DEGRADED (PASS) [static search, code-review-graph offline]
- Documentation Parity: EXECUTED (PASS)
- Clean Typography: EXECUTED (PASS)
```

When operating in standard working tree mode:
```text
Gate Execution Manifest:
- Workspace Isolation: EXECUTED (PASS) [mode: inherit (default)]
- File Integrity: EXECUTED (PASS)
...
```

---

## Sequential State Machine

```text
TASK / GOAL
    |
    v
[Phase 0: Analyze & REQ Extraction] ---> S-Size? --> [Direct Fast-Path] --> [Wrap]
    | (M / L / XL-Size)
    v
[Phase 1: Research] (spawn_readonly_researcher or Single-Agent Scout)
    |
    v
[Phase 2: Architect & Surface Discovery] (Living Plan mapped to REQ-N)
    |
    v
+-----------------------------------------------------------+
| Phase 3: Execute Step N (spawn_worker or Inline Worker)   |
|                   |                                       |
|                   v                                       |
| Phase 4: Review Step N  (spawn_reviewer or Inline Review) |
|                   |                                       |
|                   v                                       |
| Phase 5: Reassess       (Supervisor Evaluation)           |
+-------------------+---------------------------------------+
                    |
         +----------+----------+
         v                     v
      [PASS]                 [FAIL]
         |                     |
   More steps?                 +-- [Fix Loop] Implementation flaw? --> Retry Implementer (max 2)
   +-----+-----+               +-- [Re-plan Loop] Architecture flaw? --> Update Living Plan (Rev N+1)
  YES          NO              +-- Missing knowledge?   --> Trigger Researcher
   |           |
   v           v
[Step N+1]  [Phase 7: Finish & Wrap via along-wrap]
```

---

## Mandatory Execution Protocol (Step-by-Step)

### Phase 0: Analyze & Requirement Extraction (Supervisor)
1. Initialize or resume blackboard: run `along scratch init <slug> [--title <title>] [--steps <N>]`. Inspect status with `along scratch state <slug>`. If `.along/.session/<slug>/state.json` already exists and `--restart` is not passed, resume from `current_step` with recorded step status and retry counters intact.
2. Read target `.along/ISSUES/<type>--<slug>.md` (or user prompt) and `.along/DECISIONS.md`.
3. Construct an explicit **Requirement Traceability Matrix** decomposing the user request into atomic requirements (`REQ-1`, `REQ-2`, `REQ-3`).
4. Classify task size (`S`, `M`, or `L/XL`). Announce routing decision and requirement matrix.
5. **Workspace Mode & Environment Readiness Gate** [gate: worktree-env-readiness]: Evaluate `--worktree` flag, configuration (`workspace: worktree`), and semantic isolation intent. If worktree mode is requested, verify runtime and filesystem readiness via `along worktree status` or engine verification. If readiness prerequisites cannot be guaranteed, agent **MUST IMMEDIATELY HALT WITH AN ERROR**. Silent fallback to primary working directory is prohibited. Announce selected workspace mode (`workspace: worktree` or `workspace: inherit`).

### Phase 1: Research (Scout)
1. Launch read-only research via `spawn_readonly_researcher` (or execute inline Phase 1 in single-agent mode).
2. Gather: 1) Relevant files and symbols, 2) Existing patterns, 3) Constraints/Risks, 4) Unknowns. Zero file modifications allowed.
3. Ingest findings into `.along/.session/<slug>/research.md` (and blackboard).

### Phase 2: Architecture & Public Surface Discovery (Architect)
1. Execute **Public Surface Discovery & Blast Radius Pre-Check**:
   - Search (`grep`) for all occurrences of modified entities across public entry points (`README.md`, `AGENTS.md`, `docs/`, `package.json`).
   - Run `/along-graph-impact` (or `along graph-impact <target>`) on planned modifications to evaluate callers, affected flows, and candidate test suites before finalizing steps.
   - Run `/along-graph-arch` (or `along graph-arch`) when refactoring core modules to detect coupling hotspots and avoid architectural regressions.
2. Formulate a **Living Plan** with 2 to 5 ordered steps mapped to `REQ-N` (`Revision 1 - Baseline`).
3. Each plan MUST declare an explicit `## Execution Mode` (`Direct` | `Role-Based (along-team)`) based on the Adaptive Complexity Escalation thresholds. Each step must define: target files/symbols, expected behavior mapped to `REQ-N`, and verifiable acceptance criteria.
4. **Dual-Track UI & Artifact Projection**:
   - **Track 1 (Host IDE UI Projection)**: When running under Google Antigravity, project the Living Plan to `<appDataDir>/brain/<id>/implementation_plan.md` with `ArtifactMetadata` (`RequestFeedback: true`, `UserFacing: true`). This triggers Antigravity's native interactive design doc card with user checkboxes and the "Proceed" button.
   - **Track 2 (Permanent Along Memory)**: In all environments (Antigravity, Claude Code, OpenAI Codex, OpenCode), write the plan to disk at `.along/.session/<slug>/plan.md` (and `living_plan.md`) and present in chat for confirmation.

### Phase 3 to 5: Step Loop (Step N)
For each step in the Living Plan:
1. **Implement**: Mark step active: `along scratch update <slug> --step <N> --step-status in-progress`. Invoke `spawn_worker` (or execute inline Phase 3) with step instructions and relevant context.
2. **Review**: Invoke `spawn_reviewer` (or execute inline Phase 4) to run tests, audit diff, and execute `/along-graph-impact` across all modified files to confirm zero unexpected blast radius. Save rubric verdict into `.along/.session/<slug>/reviews/step-<N>.md`. Output Gate Execution Manifest.
3. **Reassess & Loop Disambiguation**: Supervisor inspects reviewer verdict:
   - If `PASS`: mark passed (`along scratch update <slug> --step <N> --step-status passed`) and advance to Step N+1.
   - If `FAIL` on localized defects (broken tests, syntax errors, lint, null pointer):
     - Trigger **`[Fix Loop]`**: Provide worker with exact error trace, failing test assertion, and diff. Increment step retry counter on disk: `along scratch update <slug> --step <N> --inc-retry`. If retry count exceeds 2, halt immediately with an escalation alert to the human user.
     - Record attempt in `.along/.session/<slug>/execution_trace.md` (`type: fix_loop`, step, attempt, outcome).
   - If `FAIL` on structural flaws (unforeseen dependencies, missing APIs, invalid assumptions, or Fix Loop retry exhaustion):
     - Trigger **`[Re-plan Loop]`**: Architect increments plan revision (`Revision N+1`), updates `plan_revision` on disk (`along scratch update <slug> --plan-rev <N+1>`), re-architects remaining steps, updates `.along/.session/<slug>/plan.md` (and `living_plan.md`, plus updated `implementation_plan.md` in Antigravity), and restarts Step Loop from the revised step.
     - Record revision in `.along/.session/<slug>/execution_trace.md` (`type: replan_loop`, reason, revision).

### Phase 6: Autonomous Goal Completion (`/goal` Mode)
When running in autonomous `/goal` mode:
- The state machine runs continuously across all steps without prompting for intermediate approvals.
- Halts only when:
  1. All acceptance criteria pass and tests are green.
  2. Max retry limit is exceeded on a blocking flaw.

### Phase 7: Finish & Reconcile
1. Merge branch workspace changes (if isolated worktree was used).
2. **Dual-Track Walkthrough & Gate Projection**:
   - When running under Google Antigravity: project the final diff summary, test logs, and Gate Execution Manifest into `<appDataDir>/brain/<id>/walkthrough.md`.
3. Execute `/along-wrap` checklist with **Engineering Provenance Compilation**:
   - Run full test suite (`along test` or canonical runner).
   - Perform Documentation Blast Radius check and run `/along-kb-sync`.
   - Move issue to `.along/ISSUES/done/`.
   - Update `ISSUES.md` projection (`/along-issue-sync`).
   - Record session log in `.along/SESSIONS/<YYYY>/<date>--<slug>.md` compiling the complete 3-part Engineering Provenance:
     1. `## Initial Implementation Plan (Baseline)`
     2. `## Execution & Loop Trace (Fixes & Re-plans)`
     3. `## Verification Walkthrough & Gate Manifest`
   - Clean up session blackboard via `along scratch purge <slug>` upon successful wrap-up. (On failure, retain blackboard for diagnosis).
4. Present a single concise completion summary.

---

## Provider Smoke Procedures

Validate Phase 0 and Phase 1 execution per provider:

### 1. Google Antigravity
1. **Trigger**: Run `/along-team <issue-slug>`.
2. **Smoke Check**: Supervisor parses issue front-matter, extracts `REQ-1`, and executes `invoke_subagent` with `TypeName: "research"`, `Role: "Scout"`. Verify subagent returns markdown report with zero file edits.

### 2. Claude Code
1. **Trigger**: Run `/along-team <issue-slug>`.
2. **Smoke Check**: Supervisor parses issue front-matter and invokes `Task` tool with prompt: `"Scout: research symbols and dependencies for issue <slug>. Read-only, do not modify files."` Verify report is returned and working tree remains clean.

### 3. OpenAI Codex
1. **Trigger**: Run `along-team <issue-slug>`.
2. **Smoke Check**: Agent detects lack of subagent primitive, emits `=== PHASE 0: SUPERVISOR ===`, writes `REQ-N` matrix, emits `=== PHASE 1: SCOUT ===`, performs read-only file inspections, and writes `.along/.session/<slug>/blackboard.md`.

### 4. OpenCode
1. **Trigger**: Run `/along-team <issue-slug>`.
2. **Smoke Check**: Agent executes single-agent fallback: emits Phase 0 and Phase 1 markers, inspects files via read tools, and outputs Living Plan to session blackboard.

