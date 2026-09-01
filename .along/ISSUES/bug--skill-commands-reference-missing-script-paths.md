---
protocol: along
protocol_version: 2.2.8
slug: skill-commands-reference-missing-script-paths
type: bug
status: open
priority: critical
created: 2026-09-01
updated: 2026-09-01
agent: claude-code
tags: [skills, distribution, path-resolution, cli, packaging]
milestone: v3.0.0-global-quality-revision
blocked_by: []
related: [extract-shared-python-library]
parent: protocol-quality-audit-remediation
---

# Skills document script paths that do not exist in consumer repositories

## Problem

Every `SKILL.md` documents its engine with a path relative to the Along source repository:

```text
skills/along-kb-sync/SKILL.md:40      python scripts/along_kb_sync.py [REPO_ROOT] [--check] [--strict]
skills/along-kb-search/SKILL.md:24    python scripts/along_kb_search.py "<query>" ...
skills/along-dep-scan/SKILL.md:33     python scripts/along_dep_scan.py [--root <path>]
skills/along-version-bump/SKILL.md:17 python scripts/along_version_bump.py patch
skills/along-history-sync/SKILL.md:18 python scripts/along_history_sync.py [repo_root]
skills/along-init/SKILL.md:50         python scripts/migrate_protocol.py <target_root>
skills/along-commit/SKILL.md:22       python scripts/along_commit.py "message"
skills/along-decision-sync/SKILL.md:26 python scripts/along_exec.py decision create ...
skills/along-feedback/SKILL.md:19-57  python scripts/along_exec.py feedback ...
skills/along-team/SKILL.md:68         python scripts/along_exec.py test
skills/along-build|test|dev/SKILL.md  python .along/scripts/build.py | test.py | dev.py
```

The installers place these engines somewhere else entirely:

- `install.ps1:119-134` (`Install-AlongScripts`) copies `scripts/*` to `~/.along/bin/`.
- `install.sh:104-111` does the same.

A consumer repository has neither `scripts/` nor, initially, `.along/scripts/`. So every
documented command fails with "can't open file 'scripts/along_kb_sync.py'".

A correct hierarchical resolver already exists and is unused by every skill and by every
engine except one:

```python
# scripts/along_exec.py:74-89
def resolve_tool_script(script_name, repo_root):
    candidates = [
        os.path.join(exec_dir, script_name),
        os.path.join(repo_root, "scripts", script_name),
        os.path.expanduser(f"~/.along/bin/{script_name}"),
        ...
    ]
```

Not a single `SKILL.md` mentions `~/.along/bin/` or `along_exec.py` as the entry point.

## Secondary problem: nothing is installable

- There is no `pyproject.toml` / `setup.py`, so the toolchain cannot be `pip install`ed or
  `uv tool install`ed.
- `package.json` is `"private": true` with no `bin` entry.
- No console entry point named `along` exists on `PATH`.
- Distribution is therefore "clone the git repository and run install.ps1".

This directly contradicts the repository's own rule packs, which prescribe packaging AI
docs into npm / NuGet / PyPI / crates artifacts (`rules/languages/*.md`, section 6 of each).
Along preaches distribution hygiene it does not practice for itself.

## Related gap: `along-build` / `along-test` / `along-dev`

These three skills document `python .along/scripts/build.py`, but `along-init` Step 3
(`skills/along-init/SKILL.md:35-45`) does not scaffold `.along/scripts/` at all. The
directory is created lazily and only by `along_exec.py` lifecycle synthesis
(`along_exec.py` `synthesize_lifecycle_script`), which the skills never invoke.

## Impact

The product's core promise is that a repository carries its context and that skills work
in any repository, under any provider. In practice, in any repository other than this one,
the documented commands fail. The agent then improvises, which is exactly the behavior the
protocol exists to prevent. This is the single largest functional gap found in the audit.

## Requirements

- REQ-1: Choose and document one canonical invocation for every skill. Recommended:
  `python <resolved>/along_exec.py <subcommand>` with resolution via
  `resolve_tool_script`, or a real `along` console script.
- REQ-2: Add packaging metadata (`pyproject.toml` with `[project.scripts] along = ...`) so
  the toolchain is installable, and make the installers prefer the installed entry point.
- REQ-3: Every engine must resolve sibling engines through the shared resolver instead of
  assuming `repo_root/scripts/`. Current offenders:
  `along_commit.py:28` (sanitizer), `along_version_bump.py:399,452`,
  `migrate_protocol.py:618,744`, `along_update.py:304,317,373,379,385`.
- REQ-4: Rewrite all `SKILL.md` usage blocks to the canonical form, including a documented
  fallback for the case where Along is not on `PATH`.
- REQ-5: `along-init` must either scaffold `.along/scripts/` or the build/test/dev skills
  must document the auto-synthesis behavior instead of a path that does not exist yet.
- REQ-6: A test must execute at least one skill's documented command inside a temporary
  repository that contains no `scripts/` directory, and assert it succeeds.

## Acceptance Criteria

- [ ] Fresh temporary repository + global install: every documented skill command runs.
- [ ] Zero `SKILL.md` references to `scripts/<engine>.py` as a user-facing command.
- [ ] `pyproject.toml` present; `along --help` works after install.
- [ ] Regression test proves consumer-repository execution.
