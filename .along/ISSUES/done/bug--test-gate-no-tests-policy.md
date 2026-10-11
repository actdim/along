---
protocol: along
protocol_version: "4.4.9"
slug: test-gate-no-tests-policy
type: bug
status: done
completed: 2026-10-11
priority: high
created: 2026-10-11
updated: 2026-10-11
agent: claude-code
tags: [test-gate, commit, hooks]
milestone: v4.5.0-multi-user-merge-automation
blocked_by: []
related: [bug--cross-context-parent-dangling, bug--lifecycle-test-false-pass, feat--test-gate-cost-reduction]
parent: task--field-report-fixes
---

# Test gate: no explicit tests policy, misconfigured hook looks like failing tests, test count depends on output flags

Reported from field use (2026-10-11). Blocker.

## Problem

Fixture A (no tests): Node project without a `test` script in `package.json`; the generated
`.along/scripts/test.py` runs `npm test`. `along commit -a -m "x"` prints
`npm error Missing script: "test"` and then "Commit aborted. Fix failing tests before
committing." A broken hook looks like failing tests, and the gate cannot be passed without
`--no-verify`.

Fixture B (output suppressed): `test.py` runs `npm test -- --silent` (vitest); tests pass,
exit 0. `along test` reports "exited 0 but executed no tests: nothing is verified".

## Requirements

- REQ-1: Explicit test policy in `.along/config.json`:

  ```json
  {
    "verify": {
      "tests": "required",
      "reason": "",
      "tracked_by": "",
      "checks": []
    }
  }
  ```

- REQ-2: `tests: "required"` (default, backward compatible): tests must actually run;
  "executed no tests" stays an error (catches a broken hook).
- REQ-3: `tests: "none"`: tests are not run; non-empty `reason` and `tracked_by` are required,
  `tracked_by` must be an existing issue key (resolved per `bug--cross-context-parent-dangling`)
  so missing tests stay visible as debt; declared `checks` (e.g. `["typecheck", "build"]`)
  run via the matching along hooks and any failure fails the gate; `along doctor` and the
  dashboard show `tests: none - <reason> (<tracked_by>)`.
- REQ-4: Hook misconfiguration is its own error type, not "failing tests" (script not found,
  runner config missing, runner did not start). Example:
  `Test hook misconfigured: npm script "test" not found. Fix .along/scripts/test.py or set verify.tests = "none"`.
- REQ-5: Executed-test counting does not depend on output flags: the `test.py` generator does
  not add `--silent`, or the gate counts from a machine-readable report (JSON reporter /
  JUnit XML into a temp file) instead of stdout.
- REQ-6: Never suggest empty placeholder tests as a fix (contradicts `anti_stub_injection`).
- REQ-7 (optional): change-aware mode; a commit touching only `*.md`, `.along/**`, `docs/**`,
  `llms*.txt` and the `version` field of `package.json` skips tests with an explicit note.

## Acceptance Criteria
- [ ] Fixture A + `tests: none` + `tracked_by` + `checks: [build]`: commit passes without `--no-verify`, build runs
- [ ] Fixture A without a declared policy: hook misconfiguration error with a hint about `tests: none`
- [ ] Fixture B (`--silent`): tests are counted, gate passes
- [ ] `tests: none` without `reason` or `tracked_by`: error
- [ ] `tests: required` and the runner executed 0 tests: "executed no tests" error
- [ ] Automated tests passing
