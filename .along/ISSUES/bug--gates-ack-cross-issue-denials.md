---
protocol: along
protocol_version: "4.8.0"
slug: gates-ack-cross-issue-denials
type: bug
status: in-progress
priority: high
created: 2026-11-10
updated: 2026-11-10
agent: antigravity
tags:
  - gates
  - denial
  - subproject
blocked_by: []
related: []
---

# Fix cross-issue denial resolution and ack in rebound sessions

Gate denials are recorded under the issue the session was bound to at denial time. When a session rebinds to another issue (for example, across subprojects or tasks), `along gates ack --all` acted only on the issue bound now, acknowledging older unrelated denials while leaving newly incurred denials unresolved. In addition, successful retries under rebound issues failed to resolve denials in the original issue ledger, and `along gates ack <id>` failed for denials recorded under another issue.

## Requirements
- REQ-1: `along gates ack --all` MUST acknowledge every open gate denial of the current agent session across all blackboards, recording the acknowledgment in each respective issue ledger.
- REQ-2: `along gates ack <id>` MUST resolve/acknowledge the named denial even when recorded under another issue, updating the specific issue ledger where the denial was recorded.
- REQ-3: An allowed retry of a denied tool call (same tool, same target path) MUST auto-resolve the denial in its originating issue ledger, attaching a note pointing to the successful call.
- REQ-4: The output of `along gates ack` MUST show the issue under which each denial was originally recorded, not only the currently bound issue.
- REQ-5: Stop gate `unresolved_gate_denial` MUST check all open denials of the current session across all blackboards from the current turn.

## Acceptance Criteria
- [ ] `along gates ack --all` acknowledges all open denials of the current agent session across issues.
- [ ] `along gates ack <id>` resolves denials recorded under another issue.
- [ ] Successful retries auto-resolve denials in their originating issue ledger with a note pointing to the successful call.
- [ ] The ack output reports the issue name for each acknowledged denial.
- [ ] Stop gate `unresolved_gate_denial` enforces unresolved denials across all rebound issues in the turn.
- [ ] Automated tests passing with clean typography.
