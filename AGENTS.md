<!-- BEGIN ALONG-PROTOCOL root (managed by along-init - do not edit by hand) -->
# ALONG-PROTOCOL v3.1.0

This repo carries its own agent context, provider-agnostically. Follow it every session, whatever tool you are.

## Scope, Precedence & Subproject Placement
- **Nearest Context Boundary**: Any folder may carry its own `AGENTS.md` + `.along/`; use the NEAREST ones for the area you're working in. On conflict, the more specific wins.
- **Subproject Localization** [gate: subproject-boundary]: In monorepos, submodules, or symlinked folders: all entities (issues, sessions, ADRs, history) MUST be created in the NEAREST `.along/`. Agents are STRICTLY FORBIDDEN from dumping subproject changes into the workspace root `.along/`.
- **Uninitialized Subprojects**: If a subproject has a package manifest or `.git` but lacks `.along/`, run `/along-init` there first.
- **Precedence**: Nearest `.along/` > higher-level `.along/` > global config (`~/.claude/CLAUDE.md`, `~/.codex/AGENTS.md`, `~/.gemini/config/GEMINI.md`).

## At session start - read these yourself (they are NOT auto-loaded)
Use the NEAREST `.along/` for the area you're working in (fall back to a higher-level one if the folder has none):
1. `AGENTS.md` (nearest) - conventions to follow.
2. `.along/ISSUES.md` - active issue board (or query `/along-kb-search`).
3. `.along/CONSTRAINTS.md` - active architectural constraints (or full log in `.along/DECISIONS.md` / `.along/DECISIONS/`).
4. Active Issue file `.along/ISSUES/<type>--<slug>.md` for your task.
Also, when relevant: `.along/VISION.md`, `.along/GLOSSARY.md`. These reflect the state WHEN WRITTEN - verify any named file/API/flag against the real code first.

## Multi-Agent & Multi-Branch Concurrency
- **Zero-Manual-Merge Rule** [gate: projection-protection]: On merge conflicts in derived projections (`ISSUES.md`, `INDEX.md`, `DECISIONS.md`), accept either side and run `/along-issue-sync`, `/along-kb-sync`, or `/along-decision-sync` to recompile.
- **Append-Only Merge Driver**: `.along/HISTORY.md` and legacy monolithic `.along/DECISIONS.md` are append-only. Configure `.gitattributes` with `merge=union`. Modular ADR files in `.along/DECISIONS/` are isolated per-file to eliminate merge collisions.
- **Untracked Exports**: `.along/dashboard.html`, `.along/DASHBOARD.md` MUST NOT be tracked in Git.
- **Context Isolation**: Context is localized to the target issue file, session-scoped blackboard (`.along/.session/<slug>/`), and completed session logs.

## Mandatory Issue Anchoring
- **No Code Without Issue** [gate: require-active-issue]: Before modifying source code, agents MUST identify or create an issue in `.along/ISSUES/<type>--<slug>.md` and set `status: in-progress`.
- **Exemptions**: Read-only Q&A and 1-line micro-edits (typo fixes, comments) do not require issues.
- **Commit Binding** [gate: commit-issue-binding]: Every commit via `/along-commit` MUST bind to the active issue slug.

## Entity Ecosystem
- **Entity types**: Issues (`feat`, `bug`, `debt`, `task`, `docs`), Decisions (ADRs), Milestones, Risks, Spikes, Checklists, Sessions. Full YAML schemas: `docs/topic--domain-model.md`.
- **Canonical keys**: `<type>--<slug>` (e.g. `feat--token-refresh`). Reference by key, NEVER by file path.
- **ADRs**: Modular records in `.along/DECISIONS/ADR-YYYY-MM-DD--<slug>.md` (with legacy fallback to monolithic `DECISIONS.md`). Never edit past entries - mark superseded. Recompile projections (`.along/DECISIONS.md` board and `.along/CONSTRAINTS.md`) via `/along-decision-sync` or `along decision sync`.
- **Issue lifecycle**: On completion set `status: done`, `completed: YYYY-MM-DD`, MOVE to `.along/ISSUES/done/`.
- **Auto-entity creation**: Agents MUST automatically detect user intent (build/fix/refactor -> Issue, blocked/rate-limit -> Risk, compare/benchmark -> Spike, release/sprint -> Milestone) and create entities without prompting the user.

## Knowledge Base & Documentation
- **Stable Entry Point Rule**: Files outside `.along/` (`README.md`, `docs/`, manifests) MUST NOT link into `.along/`. Route references through `docs/INDEX.md` or `docs/topic--<slug>.md`.
- **Portable Links**: All cross-references MUST use relative Markdown links (`[Title](./target.md)`), never `file://` or backslashes.
- **Fact Grounding**: Agents MUST extract facts from actual code, `README.md`, `docs/`, and `package.json`. Generic LLM placeholders are strictly prohibited.
- **Fast Retrieval**: Agents MUST query `/along-kb-search` before reading whole documentation files.
- **Doc Blast Radius**: After non-trivial code changes, agents MUST map affected symbols to `docs/topic--*.md` articles and update them before completing the task.

## While working
- **Decisions**: Create new ADRs via `/along-decision-sync` or `along decision create <slug> --title "..."`. Add terms to `.along/GLOSSARY.md`.
- **Token hygiene**: Use quiet flags (`pytest -q`, `dotnet test -v q`), filter outputs, inspect targeted line ranges.
- **Lifecycle hooks first**: Agents MUST use `/along-test`, `/along-build`, `/along-dev` (or `.along/scripts/*.py`) before raw shell commands.
- **Post-change review**: Agents MUST inspect diffs and evaluate blast radius via `code-review-graph` MCP (or static search fallback). Silent skips are forbidden.

## Stage & Session Completion Checklist
When a stage or session completes, agents MUST execute in this order:
1. [ ] **Tests** [gate: test_before_stop]: Run via `/along-test` with quiet flags. Zero failures.
2. [ ] **File Integrity**: `git status -u` - all new/modified files non-zero size, no empty placeholders.
3. [ ] **Code Review**: Inspect diff for side effects, verify REQ-N coverage, evaluate blast radius via `code-review-graph` (or static search), verify architectural decision compliance.
4. [ ] **Entity Reconciliation**: Close issues (`done` + move to `done/`), update milestones, resolve risks, conclude spikes.
5. [ ] **Doc Blast Radius**: Update affected `docs/topic--*.md` and run `/along-kb-sync`.
6. [ ] **Session Log** [gate: wrap_before_stop]: Write `.along/SESSIONS/<YYYY>/<date>--<slug>.md`.
7. [ ] **Projections** [gate: projection_sync_before_stop]: Run `/along-issue-sync` and `/along-decision-sync`.
8. [ ] **HISTORY**: Append line to `.along/HISTORY.md`.
9. [ ] **Compaction**: Advise user to run `/compact`.

## Rules
- **Contract-First Lifecycle**:
  - Agents MUST execute `.along/scripts/<action>.py` or `/along-test`, `/along-build`, `/along-dev` before raw shell commands.
  - When `.along/scripts/` is missing, `along test`/`along build` auto-detects and synthesizes hooks.
  - In submodules, execute the hook from that subproject's own `.along/scripts/`.
- **Environment Isolation**:
  - Agents MUST NOT install system-wide or global packages when a script fails. Fix the architecture (missing `bootstrap.ensure_deps()`, incorrect `uv` wrapper), not the environment.
- **File Modification & Anti-Deletion**:
  - Never delete, truncate, or overwrite existing documentation, comments, or code unless explicitly instructed.
  - After batch edits or migrations, agents MUST run `git diff --stat` and inspect unexpected size reductions.
  - It is strictly forbidden to replace populated files with stubs or skeletons (`// ... rest of code`) [gate: anti_stub_injection].
  - Anchor edits on minimal unique chunks. Restore unintended deletions immediately.
- **Clean ASCII & Forbidden Characters** [gate: typography]:
  - NEVER use em-dash (U+2014), en-dash (U+2013), math minus (U+2212) - use ASCII hyphen `-`.
  - NEVER use typographic quotes or guillemets - use ASCII `"` or `'`.
  - NEVER use unicode ellipsis (U+2026) - use `...`.
  - NEVER use NBSP, ZWSP, ZWNJ, ZWJ, BOM - use ASCII spaces.
  - NEVER use bullet glyphs (U+2022, U+2023, U+2043) - use `-`.
- **Markdown Standards**: Explicit code fence languages. Relative links only. UTF-8 without BOM.
- **File Content Via Tools Only** [gate: cli_safety]: Create/edit files with the agent's file tools. NEVER carry content in heredocs, `python -c`, or inline shell. Write scripts to a file first.
- **Verify Written Files**: After writing/patching, confirm parsing (`python -m compileall -q`, `bash -n`, etc.) before moving on.
- **Hermetic Tests**: Tests MUST target throwaway fixtures (`tempfile.mkdtemp()`), never the live repository. Read-only access to live state is allowed. Keep a meta-test that verifies `git status --porcelain -u` stays clean.
- **Inquiry Read-Only Invariance (Zero-Mutation Rule on Questions)**: On interrogative prompts ("is X done?", "why did Y fail?"), write/modify tools are STRICTLY PROHIBITED. Return a read-only audit report and ask for confirmation before modifying anything.
- **Mandatory Adaptive Complexity Escalation & Execution Mode Routing**: When scope touches > 3 files, crosses subsystems, or refactors core engines: single-agent execution is forbidden - route to `along-team`. Plans MUST declare `Execution Mode: Direct` or `Role-Based`.
- Windows-safe filenames: dates `YYYY-MM-DD` (no `:`), date first.
- Keep `ISSUES.md` compact - it costs context every session.
- Never write secrets/credentials/tokens/keys into tracked files.
<!-- END ALONG-PROTOCOL -->
## Project specifics

<!-- BEGIN ALONG-RULES -->
See the following engineering guidelines:
- `[languages/python.md](.along/rules/languages/python.md)`
- `[languages/typescript.md](.along/rules/languages/typescript.md)`
- `[platforms/web.md](.along/rules/platforms/web.md)`
<!-- END ALONG-RULES -->

This repository is `Along` (`actdim-along`) - the provider-agnostic agent-context protocol and skills suite.

- **Skills Source**: `skills/` (`along-init`, `along-update`, `along-dash`, `along-wrap`, `along-commit`, `along-build`, `along-test`, `along-dev`, `along-team`, `along-kb-sync`, `along-kb-search`, `along-issue-sync`, `along-decision-sync`, `along-history-sync`, `along-graph-check`, `along-dep-scan`, `along-version-bump`, `along-feedback`).
- **Engines**: `scripts/` (one per skill) on shared `scripts/alongkit/` package. Helpers defined there only; `tests/test_alongkit.py` enforces no duplicates. Runtime dep: `ruamel.yaml`.
- **Typography**: `along sanitize` checks (writes with `--write`). `/along-commit` and `/along-version-bump` verify and abort (rewrite with `--fix-typography`). Scope: `.md`, `.py`, `.sh`, `.ps1`, `.bat`.
- **Release**: `/along-version-bump` runs pre-mutation gates, transactional rollback via `alongkit.transaction.FileTransaction`.
- **Migration**: `migrate_protocol.py` preserves destinations, union-merges append-only files, backs up to `.along/.migration-backup/`.
- **Install**: Windows: `install.ps1 -Target all` (or `install.bat`). Unix: `bash install.sh`. Uninstall: `-Uninstall` / `--uninstall`. Manifest: `~/.along/install-manifest.json`.
- **Lifecycle**: Tests: `python .along/scripts/test.py`. Dev: `npm run dev`. Build: `npm run build`.
- **Tests**: Plain `unittest` on throwaway fixtures (`tests/hermetic.py`), never repo root. Live access read-only. See `[docs/topic--setup-and-workflow.md](./docs/topic--setup-and-workflow.md)`.
- **Frontend** (`packages/dashboard-ui/`): Strict `@actdim/dynstruct` + MobX (zero `useState`/`useEffect`). NSwag-generated API client via `@actdim/msgmesh/adapters`. 100% typed (zero `any`/`as`). Full rules: `[docs/topic--frontend-frameworks.md](./docs/topic--frontend-frameworks.md)`.
