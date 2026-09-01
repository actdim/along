---
protocol: along
protocol_version: 2.2.8
slug: release-engine-mutates-before-tests-and-reinstalls-globals
type: bug
status: open
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

- [ ] Failed release leaves zero modifications on disk.
- [ ] No global machine state is touched by a version bump.
- [ ] Milestone reconciliation only edits front-matter of the matching milestone.
- [ ] Git tag created (or the claim removed from documentation).
- [ ] Regression tests cover the abort path.
