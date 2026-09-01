---
protocol: along
protocol_version: 2.2.8
slug: commit-binds-arbitrary-active-issue
type: bug
status: open
priority: critical
created: 2026-09-01
updated: 2026-09-01
agent: claude-code
tags: [along-commit, traceability, issues, projection]
milestone: v3.0.0-global-quality-revision
blocked_by: []
related: [commit-stages-all-and-dead-test-detection]
parent: protocol-quality-audit-remediation
---

# along-commit attaches every commit to an arbitrary issue, producing false traceability

## Problem

`AGENTS.md` states: "Every commit created by `/along-commit` MUST bind to the active issue
slug." The implementation picks the first regex match inside the `## Active` section of the
compiled board:

```python
# scripts/along_commit.py:66-87
in_active = False
for line in lines:
    if line.startswith("## Active"):
        in_active = True
        continue
    elif line.startswith("## "):
        in_active = False
        continue
    if in_active:
        m = re.search(r'\[[ ~]\]\s*`\((\w+)\)`\s*\[([^\]]+)\]', line)
        if m:
            return {"type": m.group(1), "slug": m.group(2)}
```

`.along/ISSUES.md` is generated sorted alphabetically by slug, and this repository has six
active issues. Every commit therefore gets tagged:

```text
<message> (refs #automated-ui-screenshots-and-visual-verification)
```

regardless of what was actually changed. There is no way to pass the intended slug: the
CLI accepts only a message plus `--push` / `--no-verify` flags.

## Impact

Worse than having no traceability. The commit log, `history-sync` reconstruction, and any
dashboard metric derived from commit-to-issue binding are populated with confidently wrong
data. A formally satisfied "MUST" produces misinformation, and the protocol offers no
signal that the binding is a guess.

## Additional coupling defect

The regex hard-codes the exact rendering of the projection (`- [ ] \`(feat)\` [slug](...)`).
Any change to the board format in `issue sync` silently disables issue binding, with no
test covering the pair. The projection generator and this parser are in different files
with no shared contract.

## Requirements

- REQ-1: Accept an explicit issue: `--issue <slug>` (and short `-i`).
- REQ-2: Infer the issue deterministically when not given, in this priority order:
  1. explicit `--issue`;
  2. issue whose front-matter has `status: in-progress` AND matches the current git branch
     name, if the branch encodes a slug;
  3. the single issue with `status: in-progress` if exactly one exists;
  4. otherwise refuse to guess: warn and commit without a `refs` suffix, or fail if a
     strict mode flag is set.
- REQ-3: Read issue state from the SSOT entity files in `.along/ISSUES/*.md`, not from the
  derived `ISSUES.md` projection. The protocol itself designates the projection as derived.
- REQ-4: Never emit a `refs #<slug>` for a slug that is not verifiably related to the diff.
  When more than one in-progress issue exists, list them and ask, or bind none.
- REQ-5: If the projection must still be parsed anywhere, the format has to be produced and
  consumed through one shared function, covered by a round-trip test.
- REQ-6: Tests: single in-progress issue binds; multiple in-progress issues do not
  silently bind to the alphabetically first; explicit `--issue` always wins; unknown slug
  is rejected.

## Acceptance Criteria

- [ ] Commits never reference an issue chosen by alphabetical accident.
- [ ] `--issue` supported and documented in `skills/along-commit/SKILL.md`.
- [ ] Issue state read from entity files, not the projection.
- [ ] Regression tests cover zero / one / many in-progress issues.
