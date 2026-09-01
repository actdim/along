---
protocol: along
protocol_version: 2.2.8
slug: commit-stages-all-and-dead-test-detection
type: bug
status: open
priority: high
created: 2026-09-01
updated: 2026-09-01
agent: claude-code
tags: [along-commit, git, dead-code, safety]
milestone: v3.0.0-global-quality-revision
blocked_by: []
related: [commit-binds-arbitrary-active-issue, typography-sanitizer-destroys-non-utf8-files]
parent: protocol-quality-audit-remediation
---

# along-commit stages the entire working tree and has a never-executing test-detection branch

## Problem 1: unconditional `git add -A`

```python
# scripts/along_commit.py:144
subprocess.run(["git", "add", "-A"], cwd=repo_root, check=True)
```

Every commit stages the whole working tree: unrelated work in progress, local scratch files,
accidentally created credentials, editor artifacts, and anything the typography sanitizer
rewrote moments earlier (line 134). There is no `--dry-run`, no path selection, no
confirmation, and no preview of what will be committed.

This contradicts the protocol's own "Minimal Edit Scope" principle and combines badly with
the sanitizer: a repository-wide silent rewrite followed by `git add -A` commits that
rewrite without the user ever seeing it.

## Problem 2: `json` is used but never imported (dead branch)

```python
# scripts/along_commit.py:12-15  (imports: sys, os, re, subprocess -- no json)
...
# scripts/along_commit.py:44-51
elif os.path.exists(os.path.join(repo_root, "package.json")):
    try:
        with open(os.path.join(repo_root, "package.json"), "r", encoding="utf-8") as f:
            pkg = json.load(f)                     # NameError: name 'json' is not defined
        if "scripts" in pkg and "test" in pkg["scripts"]:
            cmd = ["npm", "test", "--", "--silent"]
    except Exception:
        pass                                       # swallowed forever
```

Node-based test detection has never worked. The `NameError` is caught by a bare
`except Exception: pass`, so a JavaScript/TypeScript repository silently commits with no
tests run, while the tool claims a "Pre-Commit Quality Gate".

## Problem 3: dead flag and inconsistent argument parsing

```python
# scripts/along_commit.py:115
all_files = "--all" in flags or "-a" in flags or len(args) > 0
```

`all_files` is computed and never used. The `len(args) > 0` clause makes it unconditionally
true whenever a message is supplied, which is meaningless. Additionally,
`args = [a for a in sys.argv[1:] if not a.startswith("-")]` silently swallows any message
beginning with a hyphen.

## Problem 4: repo-relative sanitizer lookup

```python
# scripts/along_commit.py:28
sanitizer = os.path.join(repo_root, "scripts", "sanitize_typography.py")
if os.path.exists(sanitizer):
```

In a consumer repository this path never exists, so the typography gate is silently skipped
while the skill advertises "ASCII-safe" commits. Same root cause as
`[bug--skill-commands-reference-missing-script-paths]`.

## Problem 5: push failure exits zero

```python
# scripts/along_commit.py:162-166
res = subprocess.run(["git", "push"], ...)
if res.returncode == 0: ... else: print("[Warning] Git push failed ...")
```

The process still exits 0, so an automation wrapper cannot detect a failed push.

## Requirements

- REQ-1: Stage explicitly. Default to committing only already-staged changes; support
  `--paths <p1> <p2>` and require an explicit `--all` for whole-tree staging.
- REQ-2: Print the list of files to be committed and, in interactive use, require
  confirmation for anything not explicitly requested.
- REQ-3: Add `import json`; add a test that exercises the Node detection branch.
- REQ-4: Remove the dead `all_files` computation; parse arguments with `argparse` so a
  message may start with a hyphen (support `--message` / `-m` and `--`).
- REQ-5: Resolve the sanitizer through the shared resolver; if it cannot be found, say so
  instead of skipping silently.
- REQ-6: Exit non-zero when push fails; distinguish commit success from push failure in the
  exit code and the message.
- REQ-7: Replace the bare `except Exception: pass` blocks with explicit handling and
  diagnostics recording.
- REQ-8: Tests: staging respects `--paths`; Node repo runs `npm test`; hyphen-leading
  message accepted; push failure yields non-zero exit.

## Acceptance Criteria

- [ ] No `git add -A` on the default path.
- [ ] Node test detection executes (covered by test).
- [ ] Argument parsing via argparse; hyphen-leading messages work.
- [ ] Push failure produces a non-zero exit code.
- [ ] Sanitizer resolution failure is reported, not swallowed.
