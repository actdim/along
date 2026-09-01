---
protocol: along
protocol_version: 2.2.8
slug: line-ending-churn-vs-gitattributes
type: debt
status: open
priority: low
created: 2026-09-01
updated: 2026-09-01
agent: claude-code
tags: [git, line-endings, windows, noise]
milestone: v3.0.0-global-quality-revision
blocked_by: []
related: [typography-sanitizer-destroys-non-utf8-files, generated-dashboard-artifact-committed]
parent: protocol-quality-audit-remediation
---

# Working copy is CRLF while .gitattributes declares LF, producing constant conversion noise

## Problem

`.gitattributes:3-8` declares LF for text sources:

```gitattributes
*.md text eol=lf
*.py text eol=lf
*.json text eol=lf
*.yaml text eol=lf
*.yml text eol=lf
*.sh text eol=lf
*.ps1 text eol=crlf
*.bat text eol=crlf
```

In practice almost every tracked `.md` file in the working copy has CRLF endings. Any `git`
invocation emits a wall of warnings:

```text
warning: in the working copy of '.along/HISTORY.md', CRLF will be replaced by LF the next time Git touches it
warning: in the working copy of '.along/ISSUES.md', CRLF will be replaced by LF ...
... (about 80 lines, one per file)
```

Causes:

1. The attributes were added after the files were committed with CRLF, and the working tree
   was never renormalized (`git add --renormalize .`).
2. Generators write inconsistently. Python engines write `newline='\n'` in some places
   (`sanitize_typography.py:87`) and use the platform default elsewhere, while PowerShell
   helpers and editors produce CRLF.
3. `sanitize_typography.py` forces LF onto `.ps1` and `.bat` files, contradicting the
   `eol=crlf` declaration for those extensions
   (`[bug--typography-sanitizer-destroys-non-utf8-files]` REQ-2).

## Impact

Low severity, real cost:

- Every `git status` / `git diff` is buried in warnings, so genuine warnings are missed and
  agents waste context reading them.
- Diff noise: a tool that touches a file for one field can rewrite its entire line endings,
  turning a one-line change into a whole-file diff and making review harder.
- Interacts badly with the append-only `merge=union` files: line-ending differences can
  duplicate lines on merge.

## Requirements

- REQ-1: Renormalize the repository once (`git add --renormalize .`) in a dedicated commit
  containing nothing else, so the noise commit is reviewable.
- REQ-2: Make every generator write the newline style declared by `.gitattributes` for that
  extension, via one shared writer helper in the shared package
  (`[debt--extract-shared-python-library]`).
- REQ-3: Preserve existing line endings when editing a file in place, rather than rewriting
  the whole file's style as a side effect of a field update. The
  `update_frontmatter_fields()` helper added in
  `[bug--issue-done-corrupts-status-and-drops-completed]` already does this and should be the
  model.
- REQ-4: Add a test that every tracked text file matches the newline style declared for its
  extension.
- REQ-5: Document the convention in `docs/topic--setup-and-workflow.md` and recommend
  `core.autocrlf=false` with the repository relying on `.gitattributes`.

## Acceptance Criteria

- [ ] `git status` produces no CRLF/LF conversion warnings.
- [ ] Generators honor the declared newline style per extension.
- [ ] In-place edits preserve existing line endings.
- [ ] Newline-style test in place.
- [ ] Convention documented.
