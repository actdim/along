---
protocol: along
protocol_version: "4.4.9"
slug: cross-context-parent-dangling
type: bug
status: done
completed: 2026-10-11
priority: high
created: 2026-10-11
updated: 2026-10-11
agent: claude-code
tags: [entity-graph, subproject, gates]
milestone: v4.5.0-multi-user-merge-automation
blocked_by: []
related: [feat--subproject-boundary-by-active-issue]
parent: task--field-report-fixes
---

# Cross-context parent reported as dangling

Reported from field use in a workspace with a nested subproject (2026-10-11). Blocker.

## Problem

Fixture:

```text
ws/                      # git repo, along init
  .along/ISSUES/task--umbrella.md
  sub/                   # nested git repo (submodule), along init
    .along/ISSUES/bug--child.md   # frontmatter: parent: task--umbrella
```

1. `cd ws/sub && along issue sync` reports `dangling parent reference: 'task--umbrella'`.
2. `cd ws/sub && along commit -i child -a -m "x"`: the Pre-Commit Quality Gate rejects with
   the same error.
3. `cd ws/sub && along wrap child --no-decisions --force-reason "..."` fails the same way;
   `--force-reason` does not help.

The "Multi-Subproject Work" rule and the `subproject-boundary` gate hint require exactly
this layout (child issue in the subproject with `parent: <root umbrella key>`), while
`entity-reference-integrity` rejects it. One gate demands a cross-context `parent`, another
rejects it.

Second defect (self-parent): with `ws/.along/ISSUES/task--x.md` and
`ws/sub/.along/ISSUES/task--x.md` carrying `parent: task--x`, the validator resolves
`parent` to the child itself and passes. There is no real link to the root.

## Requirements

- REQ-1: Reference fields (`parent`, `blocked_by`, `related`, `superseded_by`,
  `duplicate_of`) resolve along the context chain: current `.along/` -> nearest `.along/`
  above -> ... -> workspace root. Each context searches `ISSUES/` and `ISSUES/done/`.
- REQ-2: A key found in any context of the chain is valid; a key found nowhere stays a
  dangling error.
- REQ-3: `parent` equal to the issue's own key either fails with a "self-parent" error or
  starts resolution from the next context up (pick one, record it in an ADR).
- REQ-4 (optional): explicit context qualifier, e.g. `parent: root:task--umbrella`.
- REQ-5: Sync output and the dashboard show the context where the reference was found.

## Acceptance Criteria
- [ ] Parent in root, child in sub: sync, commit and wrap pass
- [ ] Parent in the same sub: passes
- [ ] Parent missing everywhere: dangling error
- [ ] Child key equal to parent key: self-parent error, or resolution to root (chosen variant)
- [ ] Three levels of nesting (ws/sub/subsub) resolve through all levels
- [ ] Hermetic tests on tempfile fixtures; automated tests passing
