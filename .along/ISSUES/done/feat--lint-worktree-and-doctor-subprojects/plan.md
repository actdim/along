# Living Plan: Unstaged File Linting & Recursive Subproject Protocol Version Audit

## Execution Mode
Direct

## 1. Context & Technical Scrutiny
In ALONG-PROTOCOL, `along lint` is an alias for `along gates check`.
In `scripts/alongkit/commands/gates.py`, the default action without `--hook` or `--ci` is:
```python
violations = gitgates.check_pre_commit(repo_root)
```
`check_pre_commit()` inspects only staged changes (`git diff -z --name-status -M --cached`).
When an agent writes a plan draft, edits docs, or writes code before staging with `git add`, running `along lint` reports nothing (or fails to catch typography or formatting errors). Agents are forced to stage changes just to run linting, and unstage them if edits are needed.

Additionally:
In repositories containing nested subprojects or submodules, the root repository may run protocol `4.5.4` while a newly initialized subproject runs `4.6.0` (or vice versa). Currently, `along doctor` only checks root `.along/` and does not report subproject protocol version mismatches, leading agents to format tickets with incorrect schema versions.

### Technical Boundaries & Invariants
- Content vs Commit Gates:
  - Content gates: `clean-ascii-typography`, `fence-language`, `relative-markdown-links`, `safe-filenames`, `secrets`, `stubs`, `rule-pack-integrity`. These apply to arbitrary file contents on disk.
  - Commit gates: `commit-issue-binding`, `commit-no-conflict-markers`, `commit-msg`. These require git commit context or staged index state and must NOT run on arbitrary unstaged file paths.
- Recursive Doctor Scans: Scanning subprojects must be hermetic and avoid traversing `node_modules`, `.venv`, `.git`, or directories ignored by `.gitignore`.

---

## 2. Requirements & Traceability
- **REQ-1 (Path-Targeted Linting)**: Extend `handle_lint_command` in `scripts/alongkit/commands/gates.py` to accept file and directory paths.
- **REQ-2 (Worktree Lint Flag)**: Add `--worktree` flag to `along lint` to collect all modified, staged, and untracked files from `git status --porcelain`.
- **REQ-3 (Content Gate Runner)**: Implement `check_files(repo_root: str, file_paths: Sequence[str]) -> List[Violation]` in `scripts/alongkit/gitgates.py` executing strictly content-level checks directly on disk contents.
- **REQ-4 (Recursive Doctor Audit)**: Extend `along doctor` in `scripts/alongkit/commands/doctor.py` to discover nested `.along/` contexts, read `.protocol-version`, and warn on version skew.
- **REQ-5 (Recursive Protocol Update)**: Add `--recursive` flag to `along update` (`scripts/along_update.py`) to migrate all subproject contexts.
- **REQ-6 (Hermetic Tests)**: Test suite in `tests/test_lint_unstaged.py`.

---

## 3. Step-by-Step Implementation Changes

### Step 1: Content Gate Runner in `scripts/alongkit/gitgates.py`
1. Define `CONTENT_ONLY_GATES = frozenset({"typography", "doc_routing_compliance", "fence_language", "relative_markdown_links", "safe_filenames", "secrets", "stubs"})`.
2. Implement `check_files(repo_root: str, paths: Sequence[str]) -> List[Violation]`:
   - Filter paths: resolve absolute paths and verify file existence.
   - Run each content gate handler on the file list reading directly from disk (`open(p, "rb")`).
   - Format violations as standard `Violation` objects.

### Step 2: CLI Routing in `scripts/alongkit/commands/gates.py`
1. In `handle_lint_command`:
   - Parse positional file arguments and `--worktree` flag.
   - If positional paths are given:
     - Run `gitgates.check_files(repo_root, paths)`.
     - Print report; exit 1 if violations, else 0.
   - If `--worktree` is passed:
     - Collect modified/untracked files via `repo.uncommitted_files(repo_root)`.
     - Run `gitgates.check_files(repo_root, uncommitted_files)`.
     - Print report; exit 1 if violations, else 0.
   - If neither: retain existing staged check behavior (`gitgates.check_pre_commit(repo_root)`).

### Step 3: Subproject Protocol Version Audit in `scripts/alongkit/commands/doctor.py`
1. Implement `audit_subproject_protocol_versions(repo_root: str) -> List[Dict[str, str]]`:
   - Find all `.along/` state directories under `repo_root` excluding vendor/ignored paths.
   - Read `.along/.protocol-version` for each.
   - Compare with root `.protocol-version`.
2. In `handle_doctor_command`:
   - Print summary:
     ```text
     Protocol Versions:
       . (root)                   : 4.6.0
       src/packages/ui-core       : 4.6.0
       src/legacy-service         : 4.5.4 [WARNING: mismatch; run 'along update --recursive']
     ```
   - If mismatch found, print actionable update hint.

### Step 4: Recursive Update in `scripts/along_update.py`
1. Add `--recursive` argument to `along update`.
2. If set, iterate through all detected subproject contexts and run protocol reconciliation in each.

### Step 5: Hermetic Tests in `tests/test_lint_unstaged.py`
1. Test `along lint path/to/draft.md` with non-ASCII characters: fails with typography error without staging.
2. Test `along lint --worktree`: catches errors across untracked files.
3. Test `along doctor` detects subproject version mismatch.

---

## 4. Verification Plan
1. Run hermetic tests: `python .along/scripts/test.py tests/test_lint_unstaged.py`.
2. Run `along lint .along/ISSUES/feat--lint-worktree-and-doctor-subprojects/plan.md`.
3. Typography check: `along sanitize`.
