---
protocol: along
protocol_version: "4.8.1"
slug: issue-test-scoping-policy
type: feat
status: open
priority: high
created: 2026-11-13
updated: 2026-11-13
agent: antigravity
tags: [lifecycle, gates, test, wrap, protocol, instructions]
blocked_by: []
related: [feat--test-gate-scope, bug--test-gate-no-tests-policy, feat--test-gate-cost-reduction, bug--tests-mutate-working-tree]
plan_status: approved
---

# Scoped Test Execution and Issue Verification Policy

## Problem

In large monorepos or multi-service repositories, closing an isolated issue via `along wrap` runs the whole repository test suite: minutes of unrelated webapp, backend and domain suites.

An incident in a downstream repository showed three pain points:

1. **Double test suite execution.** `along wrap` ran the `Wrap Quality Gate` (full suite), then `_auto_commit_wrapped_work` invoked `along_commit.py`, whose `Pre-Commit Quality Gate` ran the full suite a second time.
2. **Irrelevant test execution on isolated components.** A task about GPU worker benchmarks ran webapp and backend integration tests, while the GPU worker itself was not covered by the repository's `test.py` at all.
3. **Accidental commit of experiment artifacts.** A local benchmark notebook (`.ipynb`) was committed by `along wrap`, because wrap auto-commits every session-attributed file unless `--no-commit` is given.

## Current State

What the engine already provides, and what this issue builds on rather than duplicates:

- **Test-inert paths.** `ignore_paths` for the `test_before_stop` gate in `.along/rules/gates.yaml` is implemented (`feat--test-gate-scope`): `verify.test_inert_globs` merges it with built-ins, `verify.docs_only_change` skips tests in `test_before_stop`, the `Wrap Quality Gate` and the `Pre-Commit Quality Gate`, and `testruns.tree_hash` drops those paths from the tree hash.
- **Repository-level verify policy.** `.along/config.json` carries `{"verify": {"tests": "required" | "none", "reason", "tracked_by", "checks"}}` (`bug--test-gate-no-tests-policy`). `tests: none` requires a `reason` and a `tracked_by` issue key so the missing tests stay on the board as debt, and runs the declared `checks` (`build`, `lint`, `typecheck`) instead. Validation lives in `verify.policy_problems`.
- **Green-run reuse.** `gates.run_test_gate` records every run with its `tree_hash` and reuses a green run on an identical tree (`feat--parallel-session-closeout` REQ-8). The pre-commit run after wrap is therefore reused whenever the tree did not change in between.
- **Auto-commit bypass.** `_auto_commit_wrapped_work` already forwards `-n --reason` to `along_commit.py`, but only when `along wrap` itself was run with `-n`.
- **What `-n` costs.** In `along_commit.py`, `-n` skips the syntax, link-integrity, test and typography gates together, and goes through `bypass.guard`, which records a bypass in `along gates stats`. A bypass is the user's decision by protocol.

Corrected diagnosis of the incident:

- Pain point 1 happens only when the test run itself changes the working tree (untracked artifacts that are not in `.gitignore`), so the second `tree_hash` differs and the green run is not reused. That is a hermeticity defect of the target repository's tests, which the engine can detect and name, but should not hide with a blanket `-n`.
- Pain point 2 needs a real scoping mechanism: there is none today.
- Pain point 3 is wrap working as designed. `ignore_paths` makes a path test-inert, not uncommittable, and it must stay that way.

## Requirements

- REQ-1 (double run): `along wrap` MUST NOT pass `-n` to `along_commit.py` on its own; the gates that `-n` skips (syntax, links, typography) stay mandatory and no bypass is recorded for a normal wrap. Instead:
  - the `Pre-Commit Quality Gate` keeps reusing the `Wrap Quality Gate` green run through `tree_hash`;
  - when the tree hash after the wrap test run differs from the hash before it, wrap MUST print a hermeticity warning listing the paths the test run created or changed, and suggest `.gitignore` or `ignore_paths` for them.
- REQ-2 (issue-level policy): issue front matter MAY carry a `verify:` block that extends the existing `VerifyPolicy`, not a parallel schema:
  ```yaml
  verify:
    tests: required | affected | scoped | none
    scope: worker-gpu          # only with tests: scoped
    reason: "Why the full suite is not required"
    tracked_by: debt--some-key # required with tests: none, except for type: spike
    checks: [build, lint]      # optional, as in .along/config.json
  ```
  - `required` runs the full suite (today's behavior); `affected` lets the repository's runner choose tests from the files attributed to the session; `scoped` runs one named scope; `none` runs only `checks`.
  - Precedence: the issue block overrides `.along/config.json` for gates run in a session bound to that issue (`along start <slug>`); without a bound issue the repository policy applies.
  - Validation reuses `verify.policy_problems`: any mode other than `required` needs a non-empty `reason`; `none` needs `tracked_by` for every type except `spike`; `scoped` needs a `scope` that is declared in `.along/config.json` under `verify.scopes` (`{"<name>": ["<glob>", ...]}`).
- REQ-3 (plan approval): an issue-level policy other than `required` takes effect only through an approved plan. `along plan approve` snapshots the issue's `verify` block into the approval record; gates use the snapshot. A `verify` block edited after approval is ignored with a warning until the plan is re-approved.
- REQ-4 (CLI): `along issue create` and `along issue update` MUST accept `--verify-tests <mode>`, `--verify-scope <name>`, `--verify-reason "<text>"` and `--verify-tracked-by <key>`; `along issue show` MUST print the effective policy and its source (issue, repository or default).
- REQ-5 (runner contract): the engine passes scope to `.along/scripts/test.py` through environment variables only, so existing hooks that ignore them keep running the full suite:
  - `ALONG_TEST_MODE` = `full | affected | scoped`;
  - `ALONG_TEST_SCOPE` = the scope name (mode `scoped`);
  - `ALONG_ATTRIBUTED_FILES` = path of a temporary file listing the session-attributed files, one repo-relative POSIX path per line (a file, not a value, because of the Windows environment size limit).
  - `along test --scope <name>` and `along test --affected` set the same variables for manual runs. With no variables set, `test.py` MUST run the full suite (CI and developer default).
- REQ-6 (run records): `testruns.record_run` MUST store the mode and scope of each run. A green run is reused only when it covers the requested run: a full run covers every mode; a scoped or affected run covers only the same mode and scope on the same tree.
- REQ-7 (gate output): `test_before_stop`, the `Wrap Quality Gate` and the `Pre-Commit Quality Gate` MUST print the effective policy and its source, e.g. `-> [Wrap Quality Gate] tests: scoped (worker-gpu) - GPU worker only (issue feat--x)`, and a clean skip notice for `none`.
- REQ-8 (protocol): `skills/along-init/protocol.md` stays within its 6 KB budget: at most one line saying the test gate follows the effective `verify` policy (issue over repository) approved in the plan. Details go to `skills/along-init/protocol-reference.md`: completion checklist item 1 (Tests) and `## Testing Invariants` (`ignore_paths`, `verify` modes, `ALONG_TEST_*` variables, `ALONG_ATTRIBUTED_FILES`).
- REQ-9 (skills and KB): `skills/along-wrap/SKILL.md` documents the effective policy in the test gate and `--no-commit` for sessions that touched local experiment files; `skills/along-test/SKILL.md` documents `--scope`, `--affected` and the runner contract; the affected `docs/topic--*.md` describe the policy, scopes and target-repository guidance below.
- REQ-10 (doctor): `along doctor` reports the effective policy, validates `verify.scopes`, `ignore_paths`, and every open issue's `verify` block via `verify.policy_problems`.

## Architecture

- `scripts/alongkit/verify.py`: `VerifyPolicy` gains `mode`, `scope` and `source`; new `load_effective_policy(repo_root, slug)` merges the approved issue snapshot over `.along/config.json`; `policy_problems` covers both levels and `verify.scopes`.
- `scripts/alongkit/gates.py`: `run_test_gate(repo_root, label, slug=None)` resolves the effective policy, sets the `ALONG_TEST_*` environment for the hook, and passes mode and scope to `testruns`.
- `scripts/alongkit/testruns.py`: run records carry `mode` and `scope`; `green_run_for` applies the coverage rule of REQ-6.
- `scripts/alongkit/lifecycle.py`: wrap passes the slug to the test gate and prints the hermeticity warning of REQ-1; `_auto_commit_wrapped_work` keeps its current `-n` behavior.
- `scripts/along_commit.py` and `scripts/alongkit/hooks/predicates.py` (`check_test_before_stop`): pass the bound slug to the test gate.
- Issue CLI (`along issue create|update|show`) and `along plan approve` (snapshot of REQ-3).
- Execution: the scope crosses engine, CLI, hooks, skills and protocol, so it runs through `along-team` with `Execution Mode: Role-Based`, in phases that can each land on their own:
  1. REQ-1 (hermeticity warning, no blanket bypass).
  2. REQ-2, REQ-3, REQ-4, REQ-7 (issue-level policy and gates).
  3. REQ-5, REQ-6 (runner contract and run records).
  4. REQ-8, REQ-9, REQ-10 (protocol, skills, KB, doctor).

## Target Repository Guidance

Standard practices for repositories consuming Along; part of the KB and skill updates of REQ-8 and REQ-9.

### 1. Marking research and scratch files as test-inert

Already supported. Repositories with notebooks, benchmarks or scratch files configure `ignore_paths` in `.along/rules/gates.yaml`:

```yaml
gates:
  - id: test_before_stop
    ignore_paths:
      - "*.ipynb"
      - "notebooks/**"
      - "benchmarks/**"
```

When only test-inert files changed, `docs_only_change` is true and the tests are skipped in `test_before_stop`, the `Wrap Quality Gate` and the `Pre-Commit Quality Gate`. Test-inert files are still committed by wrap (see section 4).

### 2. Choosing the issue type and verify policy

- Use `type: spike` for research, prototyping, hardware benchmarks and feasibility work; a spike ends with an `## Outcome` section and may declare `verify: {tests: none, reason: "..."}` without `tracked_by`.
- For isolated components, declare `verify: {tests: scoped, scope: <name>, reason: "..."}` or `tests: affected` in the plan.
- For operational tasks that should not run tests (data updates, local scripts), declare `tests: none` with a `reason` and a `tracked_by` key.

### 3. Implementing scoped `.along/scripts/test.py`

- Without `ALONG_TEST_*` variables (CI, manual runs) the script runs the full or standard suite.
- With `ALONG_TEST_MODE=scoped`, it runs the suite of `ALONG_TEST_SCOPE`; with `affected`, it reads `ALONG_ATTRIBUTED_FILES` and maps paths to suites, for example:
  - `src/apps/server/**` -> backend unit and integration tests;
  - `src/apps/webapp/**` -> webapp tests;
  - `src/apps/worker-gpu/**` -> GPU worker tests, or an explicit skip notice when no GPU is present;
  - root configuration, shared packages or several subsystems -> full suite.
- Test runs must not leave untracked files in the working tree; otherwise wrap warns (REQ-1) and the pre-commit gate reruns the suite.

### 4. Keeping local experiment files out of commits

- When a session touched a file that must stay local (ad-hoc notebook, scratch data), wrap with `along wrap <slug> --no-commit --summary "..." --no-decisions` and commit the rest via `/along-commit`.
- Better: add exploratory paths to `.gitignore` before starting the task.

### 5. Documenting test boundaries in the target `AGENTS.md`

```markdown
## Project specifics
- Subsystems: `server/`, `webapp/`, `worker-gpu/`; scopes declared in `.along/config.json` under `verify.scopes`.
- Scoped testing: for changes isolated to `src/apps/worker-gpu/`, declare `verify: {tests: scoped, scope: worker-gpu, reason: "..."}` in the issue and the plan.
- Spikes and benchmarks: `type: spike` with `verify: {tests: none, reason: "GPU benchmark"}`.
- Test-inert paths: `notebooks/**`, `benchmarks/**` and `*.ipynb` do not trigger test gates.
```

## Open Questions

- Should a scoped or affected green run be enough for the final `Pre-Commit Quality Gate`, or should the commit require the full suite when the repository has no CI? Proposed default: enough, since CI runs `test.py` without variables (full suite).
- Should `affected` fall back to the full suite when the attributed file list is empty or contains root configuration, inside the engine or only in `test.py`? Proposed: only in `test.py`, the engine stays a black box over the mapping.

## Acceptance Criteria

- [ ] A normal `along wrap` still runs the syntax, link and typography gates on auto-commit and records no bypass; the pre-commit test run reuses the wrap green run on an unchanged tree.
- [ ] Wrap prints a hermeticity warning naming the paths a test run created or changed.
- [ ] Issue front matter `verify` block is parsed and validated by the shared `verify.policy_problems` (modes, `reason`, `tracked_by` except for spikes, declared scopes).
- [ ] The effective policy (approved issue snapshot over `.along/config.json`) drives `test_before_stop`, the `Wrap Quality Gate` and the `Pre-Commit Quality Gate`, and each prints the policy and its source.
- [ ] A `verify` block edited after plan approval is ignored with a warning until re-approval.
- [ ] `along issue create|update` accept `--verify-tests`, `--verify-scope`, `--verify-reason`, `--verify-tracked-by`; `along issue show` prints the effective policy.
- [ ] `.along/scripts/test.py` receives `ALONG_TEST_MODE`, `ALONG_TEST_SCOPE` and `ALONG_ATTRIBUTED_FILES`; a hook that ignores them still runs the full suite.
- [ ] Run records carry mode and scope; a scoped green run is never reused as a full run.
- [ ] `protocol.md` stays within 6 KB; `protocol-reference.md`, `along-wrap` and `along-test` skills and the KB document the policy, scopes, runner contract, `ignore_paths` and `--no-commit`.
- [ ] `along doctor` reports the effective policy and validates `verify.scopes`, `ignore_paths` and open issues' `verify` blocks.
- [ ] Automated tests cover each requirement and pass.
