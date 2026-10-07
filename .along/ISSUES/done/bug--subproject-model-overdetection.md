---
protocol: along
protocol_version: "4.4.6"
slug: subproject-model-overdetection
type: bug
status: done
completed: 2026-10-06
priority: high
created: 2026-10-06
updated: 2026-10-06
agent: claude-code
tags: [monorepo, subprojects, gates, protocol]
milestone: v4.5.0-multi-user-merge-automation
blocked_by: []
related: [bug--update-maintenance-friction]
---

# Package manifests are taken for subprojects: nested Along installs per project folder, sibling refs dangle, gates block cross-folder work

Field report (2026-10-06): in a single git repository holding a .NET solution (central package
management, ~16 library project folders plus test projects, no submodules, no nested `.git`),
every project folder ended up with its own `AGENTS.md` and `.along/`. Issues, sessions,
milestones and history were scattered over 17 contexts; a library fix plus its tests in a
sibling test folder could not be done under one issue.

Root causes, verified against the code:

1. The protocol rule "Uninitialized Subprojects: If a subproject has a package manifest or `.git`
   but lacks `.along/`, run `/along-init` there first" (`skills/along-init/protocol.md`) makes
   every `*.csproj` / `package.json` / `pyproject.toml` folder a subproject.
2. `along update` prints "run '/along-init' in this directory" for every manifest folder
   (`repo.find_manifest_projects`, which also lists `Directory.Build.props`, a .NET repository
   root marker, as a subproject manifest). No code reads monorepo root markers (`*.sln`, `*.slnx`,
   `Directory.Packages.props`, `pnpm-workspace.yaml`, Cargo `[workspace]`, `[tool.uv.workspace]`).
3. `check_subproject_boundary` refuses writes to the root `.along/` when the working folder has a
   `package.json`, even without a `.along/` there, and tells the agent to use a nested one.
4. Side creators of a fresh nested `.along/`: `along history-sync` (`os.makedirs` at
   `find_repo_root`), lifecycle hook synthesis (`along test/build/dev` in a folder with
   `AGENTS.md` or `.git`), migration of a legacy nested `.agents/`.
5. `along doctor` never looks below the root: nested installs without `.git` go unnoticed.
6. The require-active-issue excludes and the plan-gate whitelist match only the root `.along/`
   and root `docs/`: writing a subproject's `.along/ISSUES/*.md` or `docs/**` falls through to
   the root issue check, so an agent cannot even create the subproject issue that would unlock
   the subproject. (A plain `**/` prefix is wrong: `fnmatch` `*` crosses `/`, so
   `**/.along/*.md` would also open `.along/rules/**`.)
7. `validate_entities` resolves references against ancestor and descendant contexts only; a
   reference between sibling subprojects is reported dangling though both entities exist.
8. `require-active-issue` ignores the bound issue's `allowed_roots` / `write_scope`
   (`along start --allow-root/--write-scope`); containment reads them only from root issues,
   never from the bound subproject issue.

Decision: [ADR-2026-10-06--subproject-boundary-is-git-or-explicit-init].

## Requirements
- REQ-1: A subproject boundary is a nested `.git` (repository, submodule, worktree) or an
  explicit `along init` run by the user in that folder. A package manifest alone never
  triggers or suggests initialization. Monorepo root markers mean one installation at the root.
  The managed protocol block is reworded accordingly.
- REQ-2: `along update` refreshes existing installs only; it never creates a new nested one and
  never suggests `/along-init` for a manifest folder.
- REQ-3: No automatic migration, consolidation or deletion of existing nested installs: Along
  cannot tell an accidental install from an intentional one (manual init, team split, future
  repository extraction). Consolidating a repository is a per-repository manual task.
- REQ-4: `along doctor` warns about nested `.along/` without `.git` and lists them; a context
  with `.along/config.json` `"subproject": {"intentional": true}` is silent. Doctor fixes nothing.
- REQ-5: `check_subproject_boundary` no longer treats a `package.json` folder without `.along/`
  as a subproject. History sync and lifecycle synthesis do not create a fresh nested `.along/`.
- REQ-6: Gate excludes and the plan-gate whitelist match relative to the owning context:
  a subproject's Along state and `docs/**` pass; its `.along/rules/**`, `.along/scripts/**` and
  sources stay gated.
- REQ-7: `validate_entities` resolves references against every other `.along/` context of the
  same git repository (siblings); nested git repositories and ignored dirs stay out.
- REQ-8: `require-active-issue` allows an edit inside the bound issue's `write_scope` /
  `allowed_roots`; containment reads the scope of the bound issue in its own context.

## Acceptance Criteria
- [x] Fixture: root `.sln` + `Directory.Packages.props` + 3 project folders, no nested `.git`:
      `along init` / `along update` create or refresh exactly one `.along/` (root), print no
      init hint for the project folders
- [x] Existing nested installs are left untouched by update (no deletion, no new ones)
- [x] `along doctor` reports unmarked nested installs; marked ones are silent
- [x] REQ-5..REQ-8 covered by hermetic tests
- [x] Automated tests passing

## Resolution
- REQ-1: protocol rule "Subproject Boundary" (`skills/along-init/protocol.md`, managed block);
  `repo.monorepo_root_markers`; `Directory.Build.props` left `repo.STANDARD_MANIFESTS`.
- REQ-2: `along_update.find_uninitialized_subprojects` lists nested git repositories only
  (`repo.find_nested_git_roots`), as a note; the manifest hint is gone. `along init` already
  never recursed.
- REQ-3: no migration step touches existing nested installs (fixture asserts it).
- REQ-4: `repo.find_unmarked_nested_contexts`, `repo.is_intentional_subproject`, doctor warning.
- REQ-5: `check_subproject_boundary` dropped the `package.json` branch; `along history-sync`
  resolves its root with `repo.writable_context_root` (no stray `.along/` next to a lone
  `AGENTS.md`). Lifecycle hook synthesis is handled in [bug--lifecycle-test-false-pass].
- REQ-6: `predicates._matches_in_context` for the require-active-issue excludes and the
  plan-gate whitelist. Note: the existing `.along/*.md` pattern already matched any depth
  under `.along/` (`fnmatch` `*` crosses `/`), now in subprojects as in the root; managed rule
  packs stay protected by `rule_pack_protection`.
- REQ-7: `entities.sibling_entity_keys` (`validate_entities(..., siblings=True)`).
- REQ-8: `predicates._bound_scope_covers` in `check_active_issue`; `containment.issue_scope`
  follows `session.resolve_bound`, resolves entries against the issue's context and keeps that
  context writable when a write scope is declared.
- Tests: `tests/test_subproject_model.py`, updated `test_skills_and_scripts` test 15 and
  `test_workspace_containment` scope tests. Docs: `topic--cli-reference`,
  `topic--declarative-gates-and-traceability`, `topic--runtime-hooks-and-gates`.
