---
name: along-commit
description: Smart, ASCII-safe, and issue-linked Conventional Committer for Along. Automatically checks typography cleanliness, binds commit messages to active .along/ issues, and creates clean Git commits.
---

# Along Commit (`/along-commit`) [v2.2.9]

Routine development committer that enforces clean typography and links Git history directly to active `.along/` issues.

---

## Features
1. **Pre-Commit Typography Check**: Automatically sanitizes forbidden non-breaking spaces (NBSP), zero-width characters (ZWSP), and curly quotes.
2. **Issue Traceability**: Extracts the active issue from `.along/ISSUES.md` and appends `(refs #<slug>)`.
3. **Conventional Commits**: Auto-prefixes message types (`feat:`, `fix:`, `refactor:`, `docs:`, `chore:`).

---

## Usage

```bash
python scripts/along_commit.py "add cytoscape graph view"
python scripts/along_commit.py "fix null reference in auth handler" --push
```

### Flags
- `--push`: Automatically execute `git push` after successful commit.

