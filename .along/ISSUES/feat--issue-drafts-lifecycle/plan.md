# Living Plan: First-Class Issue Drafts with Seamless Promotion and Lifecycle Guards

## Execution Mode
Direct

## 1. Context & Technical Scrutiny

Currently in Along, creating an issue immediately places a markdown file inside `.along/ISSUES/<type>--<slug>.md` and adds an entry to `.along/ISSUES.md`. In an environment with concurrent autonomous agents, supervisors, and background daemons, publishing unfinished ideas creates race conditions:
- Background autonomous agents with idle-claim capability may prematurely lock onto incomplete tasks.
- In-progress edits to YAML frontmatter can trigger schema errors during test runs or projection recompilations.
- Drafting directly in Git-tracked storage causes noisy commit churn for early-stage thoughts.

### Architectural Invariants & Separation of Concerns
1. **SSOT vs Ephemeral Drafts**: `.along/ISSUES/` remains the sole Git-tracked source of truth for active project memory. `.along/.drafts/` is strictly machine-local and ignored by Git.
2. **Entity Walker Isolation**: By placing drafts in `.along/.drafts/` (dot-prefixed), all existing entity compilers (`along_issue_sync`, `along_kb_sync`, `test_entities`) automatically ignore them without special-case logic, adhering to `if entry.name.startswith("."): continue`.
3. **Draft Independence from Session Blackboards**: Drafts must NOT be placed inside `.along/.session/` because session blackboards are ephemeral and subject to aggressive garbage collection (`along session gc`). A draft represents an uncommitted domain entity and must have an independent lifecycle.

---

## 2. Requirements & Traceability

- **REQ-1 (Storage Isolation)**: Add `.along/.drafts/` to `.gitignore`. Implement `alongkit.drafts` helper module for draft path resolution and discovery.
- **REQ-2 (CLI Creation and Promotion)**:
  - Add `draft` and `promote` subcommands in `scripts/alongkit/commands/issue.py`.
  - `draft` supports creating minimal drafts without strict validation of milestone or tags.
  - `promote` runs `alongkit.entities.validate_issue_frontmatter`, moves file to `.along/ISSUES/`, and calls `issue_sync`.
- **REQ-3 (Seamless Promotion on Start)**:
  - In `scripts/alongkit/commands/lifecycle.py` (`along start <slug>`), check if `<slug>` exists in `.along/.drafts/`.
  - If found, promote before marking `in-progress` and binding the session.
- **REQ-4 (Wrap Draft Guard)**:
  - In `scripts/alongkit/lifecycle.py` (`execute_wrap`), list files in `.along/.drafts/`.
  - If non-empty, print an informative notice: `[Notice] <N> unpromoted draft(s) remain in .along/.drafts/: <slugs>`.
- **REQ-5 (Doctor Draft Audit)**:
  - In `scripts/alongkit/commands/doctor.py`, audit drafts older than 7 days and report them.
- **REQ-6 (Testing & ASCII Hygiene)**:
  - Implement hermetic unit tests in `tests/test_issue_drafts.py`.
  - Verify ASCII typography via `python scripts/sanitize_typography.py --check`.

---

## 3. Step-by-Step Implementation Changes

### Step 1: Add `.along/.drafts/` to `.gitignore`
Update `.gitignore` to include `.along/.drafts/`.

### Step 2: Create `scripts/alongkit/drafts.py`
Implement core draft management functions:
- `get_drafts_dir(repo_root: str) -> str`
- `find_draft(repo_root: str, slug: str) -> Optional[str]`
- `list_drafts(repo_root: str) -> List[Dict[str, Any]]`
- `save_draft(repo_root: str, slug: str, itype: str, title: str, content: str) -> str`
- `promote_draft(repo_root: str, slug: str) -> str`

### Step 3: Extend `along issue` CLI
In `scripts/alongkit/commands/issue.py`:
- Add `along issue draft <slug> [--type <type>] [--title <title>]`
- Add `along issue promote <slug>`
- Add `along issue drafts` (lists active drafts)

### Step 4: Hook into `along start`
In `scripts/alongkit/commands/lifecycle.py`:
- Before querying `.along/ISSUES/` for the slug, check `drafts.find_draft(repo_root, slug)`.
- If found, call `drafts.promote_draft(repo_root, slug)` and proceed with normal start.

### Step 5: Hook into `along wrap` and `along doctor`
- In `scripts/alongkit/lifecycle.py`, query `drafts.list_drafts(repo_root)` and emit a notice if unpromoted drafts exist.
- In `scripts/alongkit/commands/doctor.py`, add draft hygiene check reporting stale drafts.

---

## 4. Verification Plan

### Automated Test Cases
1. Create a draft via `along issue draft feat--my-idea`.
   - Verify file created in `.along/.drafts/`.
   - Verify `git status` shows clean tree (ignored).
   - Verify `along issue sync` does NOT add it to `ISSUES.md`.
2. Promote draft via `along issue promote my-idea`.
   - Verify moved to `.along/ISSUES/feat--my-idea.md`.
   - Verify updated `ISSUES.md` includes the issue.
3. Start work directly from a draft:
   - Create draft `task--from-scratch`.
   - Run `along start from-scratch`.
   - Verify promoted to `.along/ISSUES/task--from-scratch.md`, marked `in-progress`, and session bound.
4. Wrap notice:
   - Create a draft, wrap another active issue, verify wrap emits a non-fatal notice listing the draft.
5. Doctor audit:
   - Create a simulated old draft, run `along doctor`, verify warning is reported.
