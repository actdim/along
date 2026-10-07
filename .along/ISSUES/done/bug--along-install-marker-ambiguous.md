---
protocol: along
protocol_version: "4.4.6"
slug: along-install-marker-ambiguous
type: bug
status: done
completed: 2026-10-07
priority: high
created: 2026-10-07
updated: 2026-10-07
agent: claude-code
tags: [contexts, subprojects, cli, kb]
milestone: v4.5.0-multi-user-merge-automation
blocked_by: []
related: [bug--subproject-model-overdetection, bug--lifecycle-test-false-pass]
---

# What makes a folder an Along context is ambiguous: AGENTS.md, a bare or hook-made .along, and any command can start a context

Audit (2026-10-07) of what "Along is installed in this folder" means in the code:

1. `repo.ROOT_MARKERS = (".along", ".git", "AGENTS.md")`: `find_repo_root` (35 call sites:
   every CLI command, wrap, commit, kb/dep/graph engines, lifecycle hooks) stops at the first
   folder with an `AGENTS.md`, or with any `.along` entry at all. A nested `AGENTS.md` is an
   ordinary progressive-disclosure guide (instructions for that folder); it is not an Along
   context, yet `along issue create` / `session create` / `start` run from such a folder treat
   it as the root and create `<folder>/.along/` there.
2. `repo.find_agent_contexts` counts a folder with only an `AGENTS.md` as a context: `along
   update` writes the managed protocol block (REF) into it, and `kb-sync` cascades only into
   such folders. A package guide shipped inside a NuGet/npm package gets a dead reference to
   the repository's root `AGENTS.md`, and a package `docs/` without an `AGENTS.md` is never
   compiled.
3. `repo.is_along_state_dir` uses a negative list: any `.along/` holding anything besides
   `diagnostics` / `.gitignore` counts, an empty one too. Along writes `.along/scripts/`
   (lifecycle synthesis), `.along/artifacts/`, `.along/.session/`, `.along/.migration-backup/`
   on its own, so a folder becomes a "context" by side effect.
4. `repo.diagnostics_dir` writes into an existing `.along/` of any kind (existence check).
5. A test hook that runs a known runner (`dotnet test`, `pytest`, `cargo test`, ...) and prints
   no test summary at all exits 0 and is recorded green.

## Requirements
- REQ-1: One definition. A folder has Along installed when it holds Along state: a `.along/`
  with at least one state entry (`ISSUES`, `ISSUES.md`, `DECISIONS`, `DECISIONS.md`,
  `MILESTONES`, `SESSIONS`, `HISTORY.md`, `VISION.md`, `GLOSSARY.md`, `CONSTRAINTS.md`,
  `RISKS`, `SPIKES`, `CHECKLISTS`, `.protocol-version`, legacy `KB`), a legacy `.agents/` with
  its state entries, or an explicit root pointer (`<!-- along-root: ... -->`). An empty or
  side-effect-only `.along/` (`scripts`, `artifacts`, `.session`, `diagnostics`,
  `.migration-backup`, `worktrees`, `.gitignore`) is not an installation.
- REQ-2: `AGENTS.md` is never a context or root marker. `find_repo_root` stops at an installed
  context or a `.git`; `find_agent_contexts` lists installed contexts only, so `update` writes
  no protocol block into a folder guide.
- REQ-3: Only `along init` starts a context (and `along update` migrating an installed legacy
  `.agents/`). Every other command that writes Along state refuses with exit 2 when the
  resolved root has no installation. `along test|build|dev` without an installation run the
  detected command and write no hook. Diagnostics go to `~/.along` unless the root is installed.
- REQ-4: `kb-sync` compiles every package documentation root below the context: a folder with
  `docs/` plus an `AGENTS.md`, `llms.txt` or a package manifest, no `.along/` needed.
- REQ-5: A test run of a known runner that exits 0 without any test summary counts as no tests
  ran (fails, not recorded green).

## Acceptance Criteria
- [x] REQ-1..REQ-5 covered by hermetic tests
- [x] Automated tests passing

## Resolution
- REQ-1: `repo.STATE_ENTRIES` (positive list), `repo.is_along_state_dir` needs a state entry,
  `repo.RUNTIME_ONLY_ENTRIES` lists Along's side effects, `repo.is_installed`.
- REQ-2: `repo.ROOT_MARKERS = (".git",)`; `find_repo_root` stops at `is_installed` or `.git`;
  `find_agent_contexts` lists installations only; the hook template fallback looks for `.git`
  or `.along` state; `writable_context_root` removed (folded into `find_repo_root`).
  `along update` still refreshes a root whose AGENTS.md carries the managed block;
  hook cleanup also visits folders with a managed block (`repo.find_managed_agents_md_dirs`).
- REQ-3: `along_exec._require_installation` for board commands (exit 2); lifecycle runs the
  detected command without a hook outside an installation; `along_history_sync --synthesize`
  refuses; `repo.diagnostics_dir` and `lifecycle.raw_log_path` use `is_installed`.
- REQ-4: `repo.find_package_doc_roots`; `along_kb_sync` cascades into them.
- REQ-5: `lifecycle.tests_ran` (known runner, or a hook's `-> Running:` line, with no summary
  counts as zero); go `ok` lines and dotnet MTP `total:` counted.
- Tests: `tests/test_install_marker.py`; fixtures that used an empty `.along/` as a context
  now create a state entry. Docs: `topic--runtime-hooks-and-gates`, `topic--architecture`,
  `topic--cli-reference`; ADR-2026-10-07--along-installation-is-state-not-agents-md; glossary.
