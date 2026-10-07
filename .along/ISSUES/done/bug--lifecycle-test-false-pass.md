---
protocol: along
protocol_version: "4.4.6"
slug: lifecycle-test-false-pass
type: bug
status: done
completed: 2026-10-06
priority: high
created: 2026-10-06
updated: 2026-10-06
agent: claude-code
tags: [lifecycle, tests, gates]
milestone: v4.5.0-multi-user-merge-automation
blocked_by: []
related: [bug--subproject-model-overdetection]
---

# along test reports PASS when no test ran; test-before-stop counts doc edits as source

Field report (2026-10-06), verified against the code:

1. `along test` in a .NET library folder without a hook synthesized `.along/scripts/test.py`
   running `dotnet test -v q` there (`lifecycle.detect_lifecycle_action`: any `*.csproj` or
   `Directory.Build.props` selects it; no solution or test project lookup). The folder held only
   the library project: zero tests ran, and the run printed `PASS ... (code 0)` and was recorded
   green (`testruns.record_run`, session ledger), which also satisfies closeout gates.
2. In a nested context with its own `.along/` but no hook, a new hook is synthesized locally
   instead of falling back to an enclosing context's hook.
3. test-before-stop: after a passing `along test`, editing only `docs/*.md`, `README.md` or
   `CHANGELOG.md` re-triggers "Source files were modified ... tests have not been executed":
   `predicates.is_source_edit` excludes `.along/**` only. (Raw runners not counting where a
   lifecycle hook exists is by design; the message already says so.)

## Requirements
- REQ-1: A run whose output shows zero executed tests (dotnet `Total tests: 0` / "No test is
  available", pytest "no tests ran", vitest/jest "No test files found") is not a pass: non-zero
  exit, not recorded green.
- REQ-2: dotnet detection selects `dotnet test` only with a solution (`*.sln` / `*.slnx`) or a
  test project (`Microsoft.NET.Test.Sdk` / `<IsTestProject>`) in the folder, and passes it as the
  target; otherwise it reports that no test project was found.
- REQ-3: Without a local hook, a nested context runs the nearest enclosing context's hook of the
  same git repository before synthesizing one.
- REQ-4: `is_source_edit` ignores Markdown (`*.md`) and `docs/**` at any depth.

## Acceptance Criteria
- [x] REQ-1..REQ-4 covered by hermetic tests
- [x] Automated tests passing

## Resolution
- REQ-1: `lifecycle.executed_tests` reads runner summaries (unittest, pytest, vitest/jest,
  dotnet, cargo, mocha, go); `run_lifecycle_command` turns an exit-0 run that shows zero tests
  into `FAIL ... executed no tests`, exit 5 (`NO_TESTS_EXIT_CODE`), recorded not green. Raw mode
  streams through `_run_tee` so the summary can be read there too. Output silent about counts
  is judged by the exit code.
- REQ-2: `.NET` test detection targets the first `*.sln` / `*.slnx`, else a test project
  (`_is_dotnet_test_project`); a library project alone detects nothing and says so.
- REQ-3: `lifecycle.enclosing_hook` (stops at a `.git`); `along_exec` uses it before
  synthesizing, and resolves the lifecycle root with `repo.writable_context_root`.
- REQ-4: `predicates.is_doc_edit`; doc edits set `last_doc_edit_time`, counted by
  `check_test_before_stop` only with the gate option `count_docs: true` (set in this
  repository's `.along/rules/gates.yaml`, since its suite tests Markdown).
- Tests: `tests/test_lifecycle_test_evidence.py`. Docs: `topic--cli-reference`,
  `topic--runtime-hooks-and-gates`, `topic--declarative-gates-and-traceability`.
