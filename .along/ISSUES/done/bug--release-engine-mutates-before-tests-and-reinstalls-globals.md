---
protocol: along
protocol_version: 2.2.8
slug: release-engine-mutates-before-tests-and-reinstalls-globals
type: bug
status: done
completed: 2026-09-01
priority: critical
created: 2026-09-01
updated: 2026-09-01
agent: claude-code
tags: [version-bump, release, side-effects, rollback, global-state]
milestone: v3.0.0-global-quality-revision
blocked_by: []
related: [installer-parity-and-destructive-rules-overwrite, issue-done-corrupts-status-and-drops-completed]
parent: protocol-quality-audit-remediation
---

# Release engine mutates the repo before testing, cannot roll back, and silently reinstalls global config

## Problem 1: quality gate runs after the mutations it is supposed to guard

`scripts/along_version_bump.py:435-449` executes in this order:

```python
new_version = detect_and_bump_project(repo_root, bump_arg_clean)   # writes version files
sanitize_typography(repo_root)                                     # rewrites files repo-wide
update_along_milestones(repo_root, new_version)                    # flips milestone status
subprocess.run([sys.executable, dash_script, "--markdown"], ...)   # regenerates dashboard
if do_commit:
    run_precommit_tests(repo_root)                                 # <- tests run here
```

`run_precommit_tests` exits with code 1 and prints "Release aborted. Fix failing tests
before releasing." At that point the version has already been written, the whole repository
has been rewritten by the sanitizer, milestone files have been flipped to `completed`, and
the dashboard has been regenerated. There is no rollback. "Aborted" leaves a dirty,
half-released tree.

Additionally, tests run only when `--commit` is passed, so `along_version_bump.py patch`
without flags bumps the version with no verification at all.

## Problem 2: a version bump silently reinstalls the user's global agent configuration

```python
# along_version_bump.py:473, 478-493
sync_local_global_install(repo_root)
...
subprocess.run(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass",
                "-File", ps1, "-Target", "all"], cwd=repo_root, capture_output=True)
print("-> [Along Core] Global skills & scripts synchronized on local machine.")
```

Consequences of that one call:

- `install.ps1:112` executes `Remove-Item -Recurse -Force ~/.claude/rules` and recreates it,
  destroying any user-authored rules in that directory.
- Skill folders in `~/.claude`, `~/.codex`, `~/.gemini/config` are removed and recopied.
- MCP configuration files are edited (`~/.claude.json`, `mcp_config.json` variants).
- `install.ps1:297-302` then runs `migrate_protocol.py` against the repository.

All of it with `capture_output=True` and no return-code check, so the success line prints
even when the install fails. "Increment the patch version" is not a command a user expects
to rewrite machine-global agent configuration.

## Problem 3: milestone reconciliation uses unanchored regex over the whole file

```python
# along_version_bump.py:406-413
if new_version in os.path.basename(mf):
    u = re.sub(r'status:\s*(?:open|in-progress)', 'status: completed', c)
    u = re.sub(r'progress_pct:\s*\d+', 'progress_pct: 100', u)
```

- Substring match on the filename: bumping to `1.5.0` matches `v1.5.0-dashboard-and-analytics.md`,
  but any milestone whose name merely contains the version string also matches.
- The substitutions are global, so `status: open` or `progress_pct: 40` appearing in the
  milestone body (for example inside a target-issue table) is rewritten as well.
- Same defect class already fixed for `issue done` in
  `[bug--issue-done-corrupts-status-and-drops-completed]`; this call site was left behind
  and should reuse `update_frontmatter_fields()`.

## Problem 4: incomplete release semantics

- No git tag is created, despite the skill being described as a "release orchestrator".
- No CHANGELOG generation or update.
- `git add -A` (line 460) stages the entire working tree into the release commit.
- Push failures are reported as warnings only.

## Requirements

- REQ-1: Run the full quality gate (tests, sanitizer in check mode, link integrity) BEFORE
  any mutation, unconditionally, not only when `--commit` is passed.
- REQ-2: Make the release transactional: stage all edits, verify, then apply; on failure
  restore the pre-run state and report what was rolled back.
- REQ-3: Remove `sync_local_global_install` from the release path. Global installation is a
  separate, explicit user action (`/along-update` or `install.ps1`).
- REQ-4: Every `subprocess.run` in this engine must check its return code and surface
  failures; no success message may print on a failed child process.
- REQ-5: Replace the milestone regex with `update_frontmatter_fields()`; match milestones by
  front-matter `slug`, not filename substring.
- REQ-6: Stage only intended paths (version manifests, milestone, dashboard, changelog);
  never `git add -A`.
- REQ-7: Create an annotated git tag `v<version>` and update a CHANGELOG, or drop the
  "release orchestrator" wording from the skill description.
- REQ-8: Tests: failing tests leave the tree byte-identical; bump without `--commit` still
  verifies; milestone body text is not rewritten; no installer invocation occurs.

## Acceptance Criteria

- [x] Failed release leaves zero modifications on disk.
- [x] No global machine state is touched by a version bump.
- [x] Milestone reconciliation only edits front-matter of the matching milestone.
- [x] Git tag created (or the claim removed from documentation).
- [x] Regression tests cover the abort path.

## Resolution

The release is now two phases with a hard boundary between them: gates on the untouched
tree, then mutations recorded by `alongkit/transaction.py` (`FileTransaction`), a new shared
module that snapshots a file's exact bytes - or its absence - before anything writes to it
and restores every one of them on failure.

| REQ | Where |
| :--- | :--- |
| REQ-1 gate first, unconditionally | `release_preflight()` runs the tests, the typography check (check mode), and `gates.link_integrity_gate` before the first write, on every invocation. `-n` / `--no-verify` is the only way past, matching `along_commit.py`. |
| REQ-2 transactional | `alongkit/transaction.py`. Every write goes through `tx.write`; `main` catches `ReleaseAborted` (and any unexpected exception), calls `report_rollback`, and names each restored path on stderr. Nothing in the engine calls `sys.exit` past argument parsing, because an exit would skip the rollback. The transaction closes at the commit. |
| REQ-3 no global install | `sync_local_global_install` deleted, not gated. `TestReleaseTouchesNoGlobalState` fails on an installer literal in engine code (docstrings excluded, so the defect can still be documented) or on any `expanduser`. |
| REQ-4 return codes | Every child process is checked: the custom bump hook, `git add`, `git commit`, `git tag`, `git push`, and the link gate. The dead `along_dash.py --markdown` call is removed - that flag has never existed, and `.along/DASHBOARD.md` is a derived projection under review in `[debt--generated-dashboard-artifact-committed]`. No success line can print over a failed child. |
| REQ-5 front-matter writer | `update_along_milestones` uses `frontmatter.update`; `milestone_matches_version` requires the version as a whole hyphen-separated slug component, so `v1.4.30` survives a release of `1.4.3` and a milestone matched only by filename is left alone. |
| REQ-6 explicit staging | `create_release_commit` stages `tx.changed()` - exactly the paths this release wrote. `git add -A` is gone. |
| REQ-7 tag and changelog | Annotated `v<version>` tag; `update_changelog` prepends a `## v<version>` section listing `git log <last tag>..HEAD` subjects. A tag or push failure exits non-zero rather than warning. |
| REQ-8 tests | `tests/test_release_engine.py`, 19 cases: the gate records the pre-bump version it saw, a failing hook leaves the tree byte-identical, a mid-release failure rolls back and names the files, milestone body text survives, the decoy and neighbour milestones are untouched, an unrelated dirty file stays out of the release commit, the tag is annotated, and the transaction primitive is unit-tested for byte-exact restore. |

Also changed in passing: the ten duplicated read-substitute-write blocks in
`bump_along_dev_repo` became one `rewrite_version_in_file` call each, with a strict UTF-8
read - the version bump could previously have been the operation that lossily rewrote a
file, the same defect class as
`[bug--typography-sanitizer-destroys-non-utf8-files]`. `gates.link_integrity_gate` is new
and available to any engine; a repository without the Knowledge Base engine passes it.
