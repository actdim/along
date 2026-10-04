---
protocol: along
protocol_version: "4.4.3"
date: 2026-10-04
slug: init-onboarding-regressions
agent: claude-code
branch: main
commit: 59c9f42
summary: Restore root VISION.md reconcile, FULL/REF and hand-written AGENTS.md adoption via deterministic along init; migration Step 13; wrap/kb-sync onboarding checks
issues_advanced: []
issues_completed: [bug--init-onboarding-regressions]
decisions: [ADR-2026-10-04--single-vision-hybrid-reconcile]
risks_logged: []
spikes_conducted: []
---

# Session: Init onboarding regressions

## Summary
Restore root VISION.md reconcile, FULL/REF and hand-written AGENTS.md adoption via deterministic along init; migration Step 13; wrap/kb-sync onboarding checks

## Decisions
- [ADR-2026-10-04--single-vision-hybrid-reconcile]

## Blackboard Record

Execution mode: role-based; plan revision 2; approved: true.

| Step | Title | Status | Retries | Review |
| --- | --- | --- | --- | --- |
| 1 | Step 1 | passed | 0 | yes |
| 2 | Step 2 | passed | 0 | yes |
| 3 | Step 3 | passed | 0 | yes |
| 4 | Step 4 | passed | 0 | yes |
| 5 | Step 5 | passed | 0 | yes |
| 6 | Step 6 | passed | 0 | yes |

### Plan

#### Plan: bug--init-onboarding-regressions (patch release v4.4.4)

##### Context
The user reported that `/along-init` in a repo with a root `VISION.md` leaves two VISION files.
A previous agent then listed other "lost" rules. Verified against git history (`b3a6ab4^:skills/init-agents/`) and current code:

| Claim | Verdict |
| --- | --- |
| Root `VISION.md` MOVE into state dir + delete source | CONFIRMED lost. Was in old `init-agents/SKILL.md` + `init-agents.sh:208`; absent now. Current code has no VISION template at all |
| FULL vs REF protocol blocks | PARTIAL. Exists in `scripts/along_update.py:262`, undocumented in `along-init/SKILL.md` |
| Hand-written `AGENTS.md` without markers | PARTIAL. `along_update.py` prepends the block, never adds `## Project specifics` |
| No deterministic init script | CONFIRMED. No `init` in `along_exec.py` |
| Interactive re-run prompts | CONFIRMED degraded to a passive table |
| Root `ROADMAP.md`/`ARCHITECTURE.md`/`SPEC.md`/`TODO.md` | NOT a regression (never existed). Valid gap, advisory only |
| Wrap: GLOSSARY / VISION roadmap / README check | CONFIRMED missing |
| "Working guidance" block | Removed on purpose in `178a83c`. User decided: do not restore |

##### Design review (why each decision holds, what changed after review)

1. **VISION move into `.along/` - hybrid (user choice C)**: the script ALWAYS removes the duplicate; the agent restructures in the same run.
   - *README / docs link to `VISION.md`*: `stable-entry-point` forbids relinking into `.along/`. -> Script rewrites those links to `docs/INDEX.md` (reuse `rewrite_inbound_links` machinery in `scripts/along_kb_sync.py`), then moves.
   - *Both files with real content*: script appends root content to `.along/VISION.md` as a section wrapped in `<!-- along:imported-vision needs-restructure -->` ... `<!-- /along:imported-vision -->`, deletes root (migration backup covers it).
   - Agent duty (along-init / along-update SKILL, mandatory before reporting done): decompose a marked section - Scope / Non-goals / Roadmap stay; architecture -> `docs/topic--architecture.md`; backlog -> ISSUES / MILESTONES - then remove the marker.
   - No agent present (plain CLI): marker stays; `along doctor` reports it (new check), so the next agent session finishes it. Two files never coexist.
   - Root notes (`ROADMAP.md` etc.): script lists them; the along-init agent must route them in the same run (not left as advisory).
   - *"Skeleton" detection*: no template exists in code, so a text match is impossible. -> Structural rule: a file is a skeleton when it has only headings, blank lines, italic lines and HTML comments. `along init` writes that kind of template (`# Vision` + `## Scope` / `## Non-goals` / `## Roadmap`).
   - Identical content -> just delete root. Subfolder `VISION.md` -> never touched (belongs to that subproject).
2. **FULL/REF** - still right: Codex and Claude Code both load ancestor instruction files, so a FULL copy in every nested folder loads the protocol twice. Hole found: unlimited walk-up (old rule) would give a **git submodule** a REF into its parent repo, broken when the submodule is cloned alone. -> Walk up only inside the same git working tree (stop at a directory holding `.git`); submodule roots and standalone repos get FULL. Known limit: a nested *published package* shipping `AGENTS.md` carries a REF; documented, not solved here.
3. **Hand-written `AGENTS.md`** - block on top, old text byte-for-byte below; add `## Project specifics` only if no heading with that name exists (keeps `alongkit/rules.py:270` injection working).
4. **`along init` scope** - a script that only writes files would still leave rules attach / git setup / hooks / migrate to the LLM, which is exactly what agents skip. -> `along init` runs the whole mechanical pipeline (scaffold, `rules attach`, `git setup` if git, `hook install --runtime all`, `migrate --apply`), each skippable (`--no-hooks`, `--no-rules`, `--no-git`). The SKILL keeps only judgment work: VISION decomposition, root-notes routing, Project specifics, the re-run dialog.
5. **Migration trigger** - forcing all migration steps whenever a root `VISION.md` exists would rerun everything on every update for a repo that deliberately keeps a linked root VISION. -> The VISION/root-notes check runs as a cheap standalone pass in `run_migrations` even on the "already at version" path; the full step chain is not re-triggered.
6. **Root notes** - many root files are legitimate (`CHANGELOG`, `CONTRIBUTING`, `SECURITY`). Fixed narrow list, never a gate, never auto-moved by the script; the along-init agent routes them in the same run (point 1).
7. **Wrap** - GLOSSARY / VISION / README cannot be verified mechanically; skill checklist + one protocol line + a printed reminder is the honest level.
8. **Versioning** - adding `along init` is a feature (semver minor). Shipping as patch 4.4.4 per user request, framed as a regression fix; noted in CHANGELOG.

##### Execution Mode: Role-Based (along-team)
>3 files across scripts/skills/tests. `along scratch init init-onboarding-regressions --steps 6`, sequential loop with `reviews/step-N.md`.

##### Steps

###### Step 1 - shared module `scripts/alongkit/scaffold.py`
Only home for these helpers (`TestNoDuplicateHelpers`, `tests/test_alongkit.py:604`):
`find_full_protocol_ancestor(root)` (git-bounded), `render_protocol_block(text, ref_path=None)` (moved out of `along_update.py`), `merge_protocol_block(existing, block)`, `vision_template()`, `is_skeleton(text)`, `reconcile_root_vision(ctx_dir, writer)` -> `moved | removed-duplicate | replaced-skeleton | merged-needs-restructure | none` (+ rewritten links list), `find_imported_vision_markers(ctx_dir)`, `find_root_notes(root)`. New `along doctor` check reports leftover `needs-restructure` markers. Writer = `alongkit.migration.Migration` (dry-run + backup) or a thin direct writer for init.

###### Step 2 - `scripts/along_init.py` + `init` in `TOOL_MAPPINGS` (`scripts/along_exec.py:50`)
`along init [<dir>] [--dry-run] [--json] [--no-hooks] [--no-rules] [--no-git]`. Root: arg > git toplevel > cwd. AGENTS.md, CLAUDE.md import line, `.gitattributes`, `.along/` skeleton create-only, VISION reconcile, `docs/INDEX.md` if missing, then the pipeline from design point 4. Report: CREATED / UPDATED (FULL|REF) / UNTOUCHED / MOVED (deleted source) / MERGED (needs restructure) / LINKS REWRITTEN / root notes to route; on re-run a `RE-RUN QUESTIONS` block.

###### Step 3 - along-update migration
`scripts/migrate_protocol.py`: Step 13 + standalone pass (point 5). `scripts/along_update.py::apply_migration_to_context` switches to Step 1 helpers (git-bounded REF, Project specifics heading).

###### Step 4 - skills and protocol text
`skills/along-init/SKILL.md` (run `along init`; FULL/REF, hand-written, VISION rules + decomposition, root-notes routing, mandatory re-run dialog), `skills/along-wrap/SKILL.md` (docs/conventions, GLOSSARY, VISION roadmap), `skills/along-init/protocol.md` checklist item 5 one line (budget headroom ~2.8 KB), `skills/along-kb-sync/SKILL.md` + `scripts/along_kb_sync.py` advisory, `skills/along-update/SKILL.md`, `scripts/along_wrap.py` reminder.

###### Step 5 - tests (hermetic, `tempfile.mkdtemp()`)
`tests/test_scaffold_init.py`: every VISION branch incl. README-linked (link rewritten) and divergent (marker section, root deleted), doctor marker check, subfolder untouched, REF inside a tree, FULL at a nested `.git`, no-marker migration preserves bytes, idempotent re-run, dry-run writes nothing. Extend `tests/test_migration.py` (standalone pass on an already-migrated repo) and `tests/test_kb_sync.py`.

###### Step 6 - docs, release, wrap
Doc blast radius (CLI reference topic via `/along-kb-search`), CHANGELOG, `/along-kb-sync`, `/along-version-bump` (patch 4.4.4), `along wrap init-onboarding-regressions --no-decisions`, projections, HISTORY.

##### Verification
- `python .along/scripts/test.py -q` zero failures.
- Manual in temp repos: root VISION only -> one `.along/VISION.md`; README links root VISION -> link points to docs/INDEX.md, file moved; divergent pair -> single file with marker section, `along doctor` flags it; nested folder -> REF; nested `.git` -> FULL; `along migrate --apply` on an already-4.4.4 repo still heals a newly added root VISION.
- `along context-budget --check`, `along sanitize`, `git status -u`.

### Research

#### Research & Findings: init-onboarding-regressions

##### Target Symbols and Files

##### Constraints & Risks

##### Architectural Patterns

### Review step-1

#### Step 1 review - alongkit/scaffold.py + doctor check

Verdict: PASS

- New module `scripts/alongkit/scaffold.py`: protocol block render (FULL/REF), git-bounded FULL ancestor walk, managed-block merge (in-place replace; hand-written file gets block on top + `## Project specifics`), VISION template, structural skeleton detection, root VISION reconcile (moved / replaced-skeleton / removed-duplicate / merged-needs-restructure), link rebasing of moved content, link repointing (public -> docs/INDEX.md, state -> .along/VISION.md), root file backup, imported-marker and root-notes finders.
- `along doctor` reports root VISION next to `.along/`, unresolved imported-vision markers, root notes.
- Smoke test in a temp repo (scratchpad script): merged case, README and issue links repointed, root copy in `.migration-backup/<ts>/root/`, REF `../../AGENTS.md` inside a tree, FULL at nested `.git`, hand-written AGENTS.md preserved.
- Compiles (`python -m compileall -q`). Full test suite runs in Step 5.

### Review step-2

#### Step 2 review - `along init`

Verdict: PASS

- New engine `scripts/along_init.py`, mapped as `init` in `TOOL_MAPPINGS` and added to the wheel engine list in `pyproject.toml`.
- Scaffolds AGENTS.md (FULL/REF via `alongkit.scaffold`), CLAUDE.md import, `.gitattributes` lines, `.along/` skeleton create-only, VISION (reconcile or template), `docs/INDEX.md`; then runs rules attach, git setup (git root only), hook install, migrate --apply; each skippable.
- Report lists CREATED/UPDATED/UNTOUCHED, VISION action, repointed links, pipeline status, AGENT ACTIONS (imported VISION, root notes, adopted hand-written AGENTS.md) and RE-RUN QUESTIONS when `.along/` pre-existed.
- Smoke run in temp git repo: dry run wrote nothing; apply moved VISION, repointed README link, preserved hand-written AGENTS.md text, listed ROADMAP.md; second run all UNTOUCHED + re-run questions; nested folder got REF `../../AGENTS.md`.
- Protocol source lookup reuses `along_update.get_source_protocol_paths/get_global_skill_paths` (no duplicate helper).

### Review step-3

#### Step 3 review - along-update migration

Verdict: PASS

- `scripts/migrate_protocol.py`: Step 13 `step_reconcile_root_vision_and_notes` (VISION reconcile + root-notes AGENT ACTION lines) runs in the full chain; the "already at version" path runs it as a standalone pass when a root VISION.md coexists with `.along/`, without re-running the version chain.
- `scripts/along_update.py::apply_migration_to_context` now uses `scaffold.protocol_block_for` (git-bounded REF) and `scaffold.merge_protocol_block` (in-place replace; hand-written file -> `## Project specifics`). Signature kept (tests mock it).
- Dogfood: `along init` on this repo refreshed the managed block in place with a one-line diff.
- Full suite: 894 tests OK (`python .along/scripts/test.py -q`), incl. `TestMigrationStandalonePass`.

### Review step-4

#### Step 4 review - skills and protocol text

Verdict: PASS

- `skills/along-init/SKILL.md`: engine/agent division; Step 1 runs `along init` and documents FULL/REF (git-bounded), hand-written AGENTS.md adoption, VISION rules incl. link repointing, root notes, pipeline; Step 2 mandatory agent actions (VISION decomposition, root notes routing, Project specifics, `along doctor`); Step 3 mandatory re-run dialog; onboarding table and migration notes kept.
- `skills/along-wrap/SKILL.md`: new Phase A item 2 (README, Project specifics, GLOSSARY, VISION roadmap); later items renumbered. `along wrap` prints the reminder on success.
- `skills/along-init/protocol.md` checklist item 5 extended (one line); AGENTS.md block regenerated; `test_03b_managed_block_matches_its_source` passes.
- `skills/along-kb-sync/SKILL.md` capability 12 + engine advisory; `skills/along-update/SKILL.md` documents per-context changes and mandatory agent actions.
- Working guidance block not restored (user decision).

### Review step-5

#### Step 5 review - tests

Verdict: PASS

- New `tests/test_scaffold_init.py` (19 tests, temp dirs only): every VISION branch (moved with link rebase, skeleton replaced, CRLF-identical duplicate removed, divergent merged under marker with root backup, link repointing public/state, subfolder untouched, dry run), structural skeleton detection, FULL/REF (nested REF, submodule `.git` file -> FULL, walk stops at git boundary), hand-written AGENTS.md adoption, in-place block replacement, `along init` first run / idempotent re-run with RE-RUN QUESTIONS / dry run / nested REF, migration standalone pass on an already-migrated fixture.
- Helper names unique per `TestNoDuplicateHelpers`.
- Full suite 894 OK; hermetic meta-test (`test_zz_hermetic_suite`) passes.

### Review step-6

#### Step 6 review - docs, glossary, decision

Verdict: PASS

- Docs blast radius: `docs/topic--cli-reference.md` (new `along init`, doctor vision checks, update behavior), `docs/topic--migrations.md` (Step 13), `docs/topic--setup-and-workflow.md` (bootstrapping via `along init`), `docs/topic--skills-reference.md` (along-init rationale), `README.md` skills row.
- `.along/GLOSSARY.md`: FULL/REF block, imported VISION section, root notes.
- ADR `ADR-2026-10-04--single-vision-hybrid-reconcile` recorded; an accidental `--help` ADR created by `along decision create --help` was removed and the projections restored.
- `along sanitize`: 706 files clean. `along context-budget --check`: pass. `along kb-sync`: 420 links verified.
- Release (`/along-version-bump` patch -> 4.4.4) follows after wrap and the issue commit.
