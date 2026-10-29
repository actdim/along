---
protocol: along
protocol_version: "4.5.4"
slug: test-gate-scope
type: feat
status: done
completed: 2026-10-30
priority: high
created: 2026-10-29
updated: 2026-10-30
agent: claude-code
tags: [gates, protocol, judgment-rules, scope-creep]
blocked_by: []
related: [feat--test-gate-cost-reduction, bug--lifecycle-test-false-pass, debt--gate-config-layers]
plan_status: approved
---

# Test gate scope: inert config edits and pre-existing failures

Two field reports about the same gate family (`test_before_stop` at Stop; the test gate of
`along commit` / `along wrap` / `along bump` / closeout), merged into one issue. The gate
errs in both directions: it demands tests where no test can be affected (A), and it says
nothing about failures the active issue did not cause, so agents "fix" them (B).

## Problem

**A. The Stop gate fires on edits that cannot affect tests.** `predicates.is_source_edit`
counts every file outside `.along/` that is not documentation as source. Editor and agent
harness configuration (`.vscode/`, `.idea/`, `.claude/settings.local.json`, ...) re-arms the
gate and costs a full suite run. There is no per-repository way to say "this path never
needs tests", and the Stop message does not name the file that armed it.

**B. Pre-existing failures turn into scope creep.** Reported from another repository: an
agent on a narrow task (version bump, docs, config) runs the suite, sees failures in
unrelated subsystems, and edits application code, tests and mock fixtures across the repo
to get green, leaving dozens of unauthorized diffs instead of an atomic change. Cause: the
protocol says "before stopping: tests green" and the checklist says "Zero failures", with no
rule for failures the issue did not cause, and nothing forbids editing tests to make them pass.

The report's premise is partly wrong: the Stop gate requires a test run after the last
source edit, not a green one. Green is required by the commit / wrap / bump gates, which
already accept a user-approved bypass (`-n --reason`, recorded as an `Along-Bypass`
trailer). The scope creep is driven by the protocol text, not by the Stop gate code.

## Analysis of the proposals in report B

1. Judgment rule "scope containment" - accepted, shortened to fit the 6 KB `protocol.md`
   budget (5513 B used), and extended: tests and fixtures are never edited to make a
   failure pass unless the issue is about those tests.
2. Spec of the test gate for pre-existing failures - accepted, in the completion checklist of
   `skills/along-init/protocol-reference.md` (rendered to `docs/topic--along-protocol.md`).
   The bypass commands named in the report already exist.
3. Classify failures by comparing failing test paths with `git diff` / `graph-impact` -
   rejected: runner-agnostic output has no reliable path for a failure, and a change in a
   config or a shared module breaks tests in untouched files, so the heuristic would label
   real regressions "pre-existing" and license ignoring them. Replaced by a recorded
   baseline: the result of the last test run on HEAD's tree (red at HEAD = pre-existing,
   green at HEAD = caused by the working-tree changes). No extra run, any stack.

## Requirements
- REQ-1: `verify` MUST treat built-in test-inert paths (`.vscode/**`, `.idea/**`, `*.code-workspace`, `.editorconfig`, `.claude/**`, `.codex/**`, `.cursor/**`) as changes that need no tests.
- REQ-2: `test_before_stop` MUST accept `ignore_paths` (globs) in `.along/rules/gates.yaml`; matching edits MUST NOT arm the Stop gate, MUST NOT make a commit run tests on their own, and MUST be left out of the test-run tree hash.
- REQ-3: The Stop gate message MUST name the files that armed it.
- REQ-4: `protocol.md` (and the managed block of `AGENTS.md`) MUST say the Stop gate needs a test run after the last edit, and MUST carry a scope-containment rule: failures the active issue did not cause are reported and filed as an issue, not fixed under it; tests and fixtures are not edited to make a failure pass unless the issue is about them; a bypass only after the user's reply.
- REQ-5: The completion checklist MUST define the pre-existing failure procedure (halt, report the exact failures, file an issue, bypass with the user's agreement).
- REQ-6: A failed full-suite run MUST be recorded, and a failing test gate MUST print a baseline note: red at HEAD (pre-existing), green at HEAD (introduced by the working-tree changes), or no record for HEAD.

## Acceptance Criteria
- [x] Editing `.vscode/settings.json` or `.claude/settings.local.json` does not arm `test_before_stop`; editing `package.json` still does.
- [x] A path in `ignore_paths` does not arm the gate, a commit of only such paths skips tests, and the tree hash ignores it.
- [x] The Stop message lists the edited source files.
- [x] `protocol.md` stays within its 6 KB budget and `AGENTS.md` within 7 KB; both carry the scope-containment rule, including the ban on editing tests to make them pass.
- [x] The completion checklist defines the pre-existing failure procedure.
- [x] A failing `run_test_gate` prints the HEAD baseline note; regression tests cover red, green and unknown baselines.
- [x] Full suite green.
