---
name: along-commit
description: Smart, ASCII-safe, and issue-linked Conventional Committer for Along. Automatically checks typography cleanliness, binds commit messages to active .along/ issues, and creates clean Git commits.
---

# Along Commit (`/along-commit`) [v2.2.26]

Routine development committer that enforces clean typography and links Git history directly to active `.along/` issues.

---

## Features
1. **Pre-Commit Typography Gate**: Reports forbidden non-breaking spaces (NBSP), zero-width characters (ZWSP), curly quotes, and byte order marks by file and line, and aborts the commit. It does not rewrite the working tree unless `--fix-typography` is passed. Files that are not valid UTF-8 are skipped and named, never rewritten.
2. **Issue Traceability**: Deterministically resolves the active issue from SSOT entity files (`.along/ISSUES/*.md`) via explicit `--issue`, current Git branch, or single `in-progress` issue, appending `(refs #<slug>)` without arbitrary guessing.
3. **Conventional Commits**: Auto-prefixes message types (`feat:`, `fix:`, `refactor:`, `docs:`, `chore:`).

---

## Usage

```bash
along commit "add cytoscape graph view" -i feat--cytoscape-graph
along commit "fix null reference in auth handler" --push
```
*(Or fallback: `python ~/.along/bin/along_exec.py commit "message"` or `/along-commit`)*

### Flags
- `-i`, `--issue <slug>`: Explicitly bind commit to a specific issue slug.
- `--strict`: Abort if the active issue cannot be determined unambiguously instead of committing without refs.
- `-p`, `--push`: Automatically execute `git push` after successful commit.
- `--fix-typography`: Apply the ASCII replacements the gate found, then continue. Without it the gate only reports and the commit is aborted.
- `-n`, `--no-verify`: Skip both pre-commit gates (tests and typography).
