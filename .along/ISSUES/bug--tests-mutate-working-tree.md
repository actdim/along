---
protocol: along
protocol_version: 2.2.8
slug: tests-mutate-working-tree
type: bug
status: open
priority: high
created: 2026-09-01
updated: 2026-09-01
agent: claude-code
tags: [tests, hygiene, hermetic, side-effects]
milestone: v3.0.0-global-quality-revision
blocked_by: []
related: [migration-deletes-destination-without-backup, generated-dashboard-artifact-committed]
parent: protocol-quality-audit-remediation
---

# Test suite runs the engines against the live repository and mutates it

## Problem

Three tests execute real engines with `REPO_ROOT` as the target:

```python
# tests/test_skills_and_scripts.py:173     dashboard generation
cmd = [sys.executable, dash_script, REPO_ROOT, "--cli"]
...
# :184-185  asserts the engine wrote into the working tree
self.assertTrue(os.path.exists(os.path.join(REPO_ROOT, ".along", "DASHBOARD.md")))
self.assertTrue(os.path.exists(os.path.join(REPO_ROOT, ".along", "dashboard.html")))

# tests/test_skills_and_scripts.py:192     protocol migration
res = subprocess.run([sys.executable, mig_script, REPO_ROOT], ...)

# tests/test_skills_and_scripts.py:201     update engine
res = subprocess.run([sys.executable, update_script, REPO_ROOT, "--check-only", "--local-only"], ...)
```

Consequences observed during this audit:

1. `test_07` (migration) rewrote the front-matter quoting of a newly created issue file
   mid-session, changing `protocol_version: "2.2.8"` to `protocol_version: 2.2.8`. The test
   silently edited a file the developer was working on.
2. `test_06` regenerates `.along/DASHBOARD.md` and the 205 KB `.along/dashboard.html` on
   every run, so `git status` is dirty after testing and the artifact churns in history
   (18 of 109 commits touch it). See `[debt--generated-dashboard-artifact-committed]`.
3. Because `along_commit.py:34-64` runs the suite before every commit, every commit made
   through the protocol's own committer regenerates those artifacts and, with
   `git add -A`, commits them.

The migration engine has no `--dry-run` (see
`[bug--migration-deletes-destination-without-backup]`), so `test_07` is running a
destructive engine against real project memory with no safety net. It passes today only
because the repository happens to already be migrated.

## Additional test-suite defects

- `test_06` asserts on `res.stdout` without checking it is not `None`, which converts the
  encoding bug into a misleading `TypeError`
  (`[bug--subprocess-encoding-breaks-on-non-utf8-locale]`).
- `test_09` claims to verify installer coverage but compares only skill folder names, which
  is why the missing rules installation in `install.sh` went unnoticed
  (`[bug--installer-parity-and-destructive-rules-overwrite]`).
- Tests that do use `tempfile` (`test_11` onward) are correct and should be the model.
- No test asserts that running the suite leaves the working tree unchanged.

## Impact

A test suite that mutates the repository it tests cannot be trusted as a gate: it produces
false diffs, can corrupt in-progress work, and makes "the suite is green" and "the tree is
clean" mutually exclusive. It also means CI cannot distinguish a real change from test
noise.

## Requirements

- REQ-1: Every engine invocation in tests must target a `tempfile.mkdtemp()` fixture, never
  `REPO_ROOT`. Where a realistic repository is needed, build a minimal fixture or copy the
  needed subset into the temp directory.
- REQ-2: Add a meta-test that snapshots `git status --porcelain -u` before and after the
  suite and fails if the suite dirtied the tree.
- REQ-3: Tests that must read live repository content (for example the ADR format guard in
  `tests/test_kb_search.py`) must open files read-only and never invoke engines that write.
- REQ-4: Fix `test_06` to check `returncode` and non-`None` output before asserting content,
  and to skip cleanly when `uv` is absent.
- REQ-5: Strengthen `test_09` to compare installed artifact sets (skills, rules, scripts,
  configuration writes) between `install.ps1` and `install.sh`.
- REQ-6: Document the hermetic-test rule in `AGENTS.md` and in
  `docs/topic--setup-and-workflow.md`, since agents write these tests.

## Acceptance Criteria

- [ ] No test passes `REPO_ROOT` to a writing engine.
- [ ] Meta-test proves the suite leaves the tree clean.
- [ ] `test_06` reports the real failure cause.
- [ ] `test_09` compares full artifact sets.
- [ ] Hermetic-test rule documented.
