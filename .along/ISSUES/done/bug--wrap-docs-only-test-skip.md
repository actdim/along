---
protocol: along
protocol_version: "4.4.10"
slug: wrap-docs-only-test-skip
type: bug
status: done
completed: 2026-10-12
priority: high
created: 2026-10-11
updated: 2026-10-12
agent: claude-code
tags: [wrap, test-gate]
milestone: v4.5.0-multi-user-merge-automation
blocked_by: []
related: [bug--test-gate-no-tests-policy]
---

# along wrap demands tests for documentation / .along-only work

## Problem

Observed 2026-10-11 in `mempart/src/packages/webmold` (Along 4.4.10): a task that only
removed nested `.along/` stubs could not be wrapped. The test hook runs `npm test`, the
package has no `test` script, so the gate reported "Test hook misconfigured" and the wrap
wrote no session log, projections or HISTORY line. The documentation-only skip of
`bug--test-gate-no-tests-policy` REQ-7 was applied to `along commit` only; also
`verify.is_doc_only_path` recognised only a top-level `.along/`, not a nested
`apps/server/.along/...`.

## Requirements

- REQ-1: `along wrap` skips the test gate, with a note, when the work of the issue touches
  only documentation and Along state: the issue's attributed files (session ledger) when
  there are any, else the working-tree changes under the context root.
- REQ-2: Any `.along/` path segment counts as Along state (except `.along/scripts/`), for
  commit and wrap alike.
- REQ-3: Unknown changes (git unavailable, nothing changed and no ledger) keep the gate.

## Acceptance Criteria
- [ ] Wrap of a docs/.along-only change with a misconfigured test hook succeeds and says tests were skipped
- [ ] Wrap with a source change still runs (and fails on) the test gate
- [ ] Nested `.along/` paths classify as state; `.along/scripts/` does not
- [ ] Automated tests passing
