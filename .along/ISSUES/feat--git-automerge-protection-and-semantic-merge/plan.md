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
