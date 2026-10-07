---
protocol: along
slug: subproject-boundary-is-git-or-explicit-init
type: decision
title: "Subproject boundary is a nested .git or an explicit along init"
date: 2026-10-06
status: accepted
tags: [adr, architecture, decision, monorepo, subprojects]
---

# ADR-2026-10-06--subproject-boundary-is-git-or-explicit-init - Subproject boundary is a nested .git or an explicit along init

- Date: 2026-10-06
- Status: accepted
- Context: The protocol rule "If a subproject has a package manifest or `.git` but lacks `.along/`, run `/along-init` there first", the update hint for every manifest folder, and a subproject-boundary branch keyed on `package.json` made every project folder of a monorepo a subproject. In a .NET solution every `*.csproj` is a manifest, so a single git repository collected one `AGENTS.md` + `.along/` per project folder; entities were scattered, gates blocked a library fix plus its tests under one issue, and each update refreshed the nested installs again. Nothing in Along can tell such an accidental install from an intentional one (a user ran `along init` there, a team owns that folder, the folder will be extracted into its own repository).
- Decision: (1) A subproject boundary is a nested `.git` (repository, submodule, worktree) or an explicit `along init` run by the user in that folder. A package manifest alone (`*.csproj`, `package.json`, `pyproject.toml`, `Cargo.toml`, ...) never triggers, suggests or implies initialization. (2) Monorepo root markers (`*.sln`, `*.slnx`, `Directory.Build.props`, `Directory.Packages.props`, `pnpm-workspace.yaml`, Cargo `[workspace]`, `[tool.uv.workspace]`) mean one installation at the root. (3) `along update` refreshes existing installs only and never creates one. (4) No automatic migration, consolidation or deletion of existing nested installs, in any release. (5) Detection instead of migration: `along doctor` lists nested `.along/` without `.git`; a context marks itself intentional with `.along/config.json` `"subproject": {"intentional": true}` and is then not reported.
- Consequences: New repositories get one board per git repository unless the user decides otherwise. Repositories already fragmented by older versions stay as they are until their owners consolidate them by hand (a per-repository task: move entities with `git mv`, resolve slug collisions, merge HISTORY by date, remove nested `AGENTS.md` / `.along/`); doctor keeps pointing at them until then. Existing intentional nested installs keep working and can silence the warning. Code that keys behaviour on manifests (subproject-boundary gate, update hint, manifest project discovery) must not treat a manifest as a context boundary; manifests stay valid inputs for rule-pack selection and dependency scanning.
