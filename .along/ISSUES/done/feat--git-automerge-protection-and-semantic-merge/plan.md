# Implementation Plan: Preventive Git Auto-Merge Protection, Update Propagation, and Stage-Aware Semantic Conflict Resolution

- Issue: `feat--git-automerge-protection-and-semantic-merge`
- Execution Mode: Direct
- Verification Policy: automated tests (`test_merge_driver.py`, `test_along_resolve_docs.py`, and `along doctor`)

## 1. Architectural Overview & Invariants

### 1.1 Invariants
- **Zero Silent Mangling**: Git line-merges MUST NEVER silently combine concurrent edits in `.along/`, `docs/`, `AGENTS.md`, or `CLAUDE.md`.
- **Zero Config Dependency for Blocking**: If a repository is cloned without `along git setup` having run, Git MUST still refuse automatic 3-way merge on these files (achieved via native `text -merge` in `.gitattributes`).
- **Deterministic Projections**: Projections (`ISSUES.md`, `CONSTRAINTS.md`, `INDEX.md`, `DECISIONS.md`) are derived artifacts. When drivers are registered, they keep `ours` and resync via `along git sync`. When drivers are absent, `-merge` prevents corruption.
- **Update Propagation**: Running `along update` in any existing repository MUST automatically apply these `.gitattributes` and `.git/config` settings.
- **Stage-Aware Resolution**: `along resolve` MUST be able to resolve conflicts not only from textual conflict markers (`<<<<<<<`), but also directly from Git index stages (`:1:`, `:2:`, `:3:`) produced when `-merge` stops an automatic merge.
- **ASCII Typography & Linting**: All generated files and modified scripts MUST strictly adhere to standard ASCII characters (no typographic quotes, no em-dashes, no non-breaking spaces).

---

## 2. Step-by-Step Implementation

### Step 1: Preventive Auto-Merge Lock in `.gitattributes` (`scripts/alongkit/merge.py`)
- Define base protective patterns in `alongkit.merge`:
  - `PREVENTIVE_LOCK_PATTERNS = ("**/.along/**/*.md", "**/docs/**/*.md", "AGENTS.md", "CLAUDE.md")`
- Update `desired_attributes(repo_root)`:
  - Add `text -merge` lines for all preventive patterns.
  - Retain projection patterns with `merge=along-projection`.
  - Retain frontmatter patterns with `merge=along-frontmatter`.
  - Ensure the ordering in `.gitattributes` is correct: base `text -merge` comes first, specific drivers (`along-projection`, `along-frontmatter`) come after, ensuring specific drivers take precedence when configured, while unconfigured clones fall back to `-merge` instead of line-merge.
- Update `render_gitattributes()` and `tests/test_merge_driver.py` to assert the new managed block structure.

### Step 2: Update Propagation (`scripts/along_update.py` & `scripts/along_init.py`)
- In `scripts/along_update.py`:
  - Ensure `along_merge.setup(ctx_dir)` is executed during update for the root context (and any subproject roots).
  - Explicitly report when `.gitattributes` managed merge protection block is updated:
    `[OK] Refreshed Git auto-merge protection and merge drivers (.gitattributes)`
  - Update `skills/along-update/SKILL.md` to document that `along update` now enforces Git auto-merge protection.
- In `scripts/along_init.py`:
  - Ensure `along git setup` applies the updated managed block on repository scaffold.

### Step 3: Diagnostic Verification in `along doctor` (`scripts/alongkit/commands/doctor.py`)
- Add a dedicated check in `along doctor`:
  - Check `.gitattributes` for presence of `text -merge` on `.along/` and `docs/`.
  - Report `[OK] Git auto-merge protection: active (.gitattributes blocks silent line-merge)` or `[WARN] Git auto-merge protection: missing (run along git setup or along update)`.

### Step 4: Stage-Aware Conflict Resolution (`scripts/alongkit/resolve.py` & `scripts/along_resolve.py`)
- In `scripts/alongkit/resolve.py`:
  - Add `get_unmerged_stages(path, cwd=None) -> Optional[Tuple[str, str, str]]`:
    - Checks `git ls-files -u -- <path>`
    - Reads blob content for stage 1 (`:1:` base), stage 2 (`:2:` ours), stage 3 (`:3:` theirs).
  - Add `resolve_staged_conflict(path, repo_root, strict=False) -> Tuple[str, bool, List[str]]`:
    - Reads stages 1, 2, 3.
    - If entity with front-matter: merges front-matter using `alongkit.merge.merge_frontmatter_values`, then performs structural reconciliation on the body.
    - If markdown doc: runs 3-way structural reconciliation between base, ours, and theirs.
    - Verifies link integrity and typography.
- In `scripts/along_resolve.py`:
  - Update `run_resolve()`:
    - If files are in unmerged state (`git ls-files -u`), detect whether they have textual markers or stage-only conflicts.
    - Resolve stage-only conflicts, write resolved content to the working file, and optionally run `git add` when clean.

### Step 5: Test Suite Verification
- Update `tests/test_merge_driver.py`:
  - Verify `render_gitattributes` outputs `text -merge` for `.along/**`, `docs/**`, `AGENTS.md`, `CLAUDE.md`.
  - Verify `along git setup` and uninstall.
- Update `tests/test_along_resolve_docs.py`:
  - Add test for stage-aware resolution from index stages (`:1:`, `:2:`, `:3:`).
- Run full test runner: `python .along/scripts/test.py`.

## Revision 2 (2026-11-15T13:07:19Z, along plan revise)

Reason: Rev 1 relied on -merge fallback that git does not perform for undefined drivers, and would have overridden HISTORY.md merge=union; drivers move to .git/info/attributes, REQ-4 and entity coverage added.

# Implementation Plan (rev 2): Preventive Git Auto-Merge Protection, Update Propagation, and Stage-Aware Semantic Conflict Resolution

- Issue: `feat--git-automerge-protection-and-semantic-merge`
- Execution Mode: Direct
- Verification Policy: automated tests (`tests/test_merge_driver.py`, `tests/test_along_resolve_docs.py`) plus full `python .along/scripts/test.py`

## 0. Why rev 2

Rev 1 put `text -merge` first and `merge=<driver>` lines after it in the committed `.gitattributes`, expecting unconfigured clones to fall back to `-merge`. Git does not work that way:

- the last matching line wins per attribute, so `merge=along-frontmatter` replaces `-merge`;
- an undefined driver name falls back to the built-in 3-way TEXT merge (`ll-merge.c`: "default to the 3-way"), not to binary.

So on a fresh clone the entity files and projections would still be line-merged silently. Rev 1 would also have overridden the existing `.along/HISTORY.md merge=union` (written above the managed block), turning the append-only log into a conflict on every concurrent append.

## 1. Invariants

- **Zero silent mangling** in `.along/**/*.md`, `docs/**/*.md`, `AGENTS.md`, `CLAUDE.md`.
- **Zero config dependency for blocking**: the committed `.gitattributes` alone (no `.git/config`, no `.git/info/attributes`) makes Git refuse a line merge of those files.
- **Drivers are a per-clone upgrade**: `along git setup` binds `merge=along-projection` / `merge=along-frontmatter` in `$GIT_COMMON_DIR/info/attributes` (highest attribute precedence, never committed), only in a clone where the drivers are also registered in `.git/config`. Driver binding and driver registration therefore always come together.
- **Append-only logs stay union**: `HISTORY.md` (and a legacy monolithic `DECISIONS.md` log) keep the built-in `merge=union`, which needs no config.
- **Stage-aware resolution**: `along resolve` resolves `-merge` conflicts (no text markers; stages `:1:`, `:2:`, `:3:` in the index).
- ASCII typography in all touched files.

## 2. Steps

### Step 1: Split bindings (`scripts/alongkit/merge.py`)
- `PROTECTED_PATTERNS = ("**/.along/**/*.md", "**/docs/**/*.md", "AGENTS.md", "CLAUDE.md")` -> `-merge`.
- `UNION_PATTERNS = ("**/.along/HISTORY.md",)` -> `merge=union`, written after the protected lines; `**/.along/DECISIONS.md merge=union` too when no modular `.along/DECISIONS/` exists.
- `desired_attributes(repo_root)` returns the committed baseline (protected + union lines).
- New `desired_driver_attributes(repo_root)` returns the driver bindings (current projection + frontmatter lines).
- New `info_attributes_path(repo_root)` via `git rev-parse --git-common-dir` (worktree safe); `render_info_attributes()` manages its own marked block there.
- `setup()` writes both blocks (and `.git/config`); `--uninstall` removes both plus config. Report gains `info_attributes_changed`.
- `status()` reports `gitattributes` (baseline present) and `info_attributes` (driver bindings present); `is_configured()` requires both plus config.
- New `protection_status(repo_root)`: (a) baseline: every `desired_attributes()` line is present in the committed `.gitattributes`; (b) effective: `git check-attr merge` on sample paths (`.along/ISSUES/x.md`, `.along/ISSUES.md`, `docs/x.md`, `AGENTS.md`, `.along/HISTORY.md`) yields `unset`, `union`, or a driver that is registered in `.git/config`. Any `set`/`unspecified`/unregistered driver value = unprotected.

### Step 2: Rollout (`scripts/along_update.py`, `scripts/along_init.py`, `commands/gates.py`)
- `along update` already calls `merge.setup()` on the root context; print `[OK] Refreshed Git auto-merge protection and merge drivers` when either attributes block or config changed.
- `along init`: call `merge.setup(root)` after `scaffold_gitattributes` so a new repo gets protection immediately.
- `along git setup` / `along git status` print the new info-attributes line.
- `skills/along-update/SKILL.md`: one line documenting the protection refresh.

### Step 3: Doctor (`scripts/alongkit/commands/doctor.py`)
- `[OK] Git auto-merge protection: active` when every sample path is protected/union per the committed baseline; `[WARN] ... missing (run along git setup or along update)` otherwise.
- Keep the driver-registration check; reword the old `merge=union` message.

### Step 4: Stage-aware resolve (`scripts/alongkit/resolve.py`, `scripts/along_resolve.py`)
- `get_unmerged_stages(path, repo_root) -> Optional[Tuple[str, str, str]]`: `git ls-files -u -z`, then `git show :N:path`; base may be absent (add/add -> empty base); returns None when ours or theirs is absent (delete/modify stays manual).
- `resolve_staged_conflict(rel_path, repo_root, strict)`:
  - projection (`merge.is_projection` on ours): keep ours, `merge.mark_resync`, note "run along git sync";
  - front-matter on both sides: `merge.merge_entity_text(base, ours, theirs)`;
  - otherwise: `merge.text_merge(base, ours, theirs)`;
  - leftover markers go through the existing `resolve_markdown_content()` structural reconcilers.
- `get_unmerged_docs()`: every unmerged `*.md` (adds `.along/**`, `CLAUDE.md`, nested `*/docs/`).
- `resolve_file()`: when the file is unmerged and has no markers, use the staged path; write the result; `git add` it when clean and not `--check`.

### Step 5: Post-merge workflow (`commands/gates.py`, REQ-4)
- `along git sync` after a merge: (1) stage-aware resolve of unmerged `*.md`, (2) projection recompilation (existing `resync`), (3) `along lint --worktree` on the touched files, report remaining conflicts; exit 1 when anything is left.

### Step 6: Tests
- `tests/test_merge_driver.py`: update `TestGitattributesBlock` for the split; assert HISTORY union line comes after the protected line; e2e: (a) with drivers -> clean merge as today; (b) clone WITHOUT setup (only committed `.gitattributes`) -> concurrent edits of an entity and a doc stop with a conflict and the working file has no markers; (c) HISTORY appends union-merge.
- `tests/test_along_resolve_docs.py`: stage-aware resolution of an entity and a doc from a real `-merge` conflict; projection kept as ours + resync marker.
- Full suite: `python .along/scripts/test.py`.
