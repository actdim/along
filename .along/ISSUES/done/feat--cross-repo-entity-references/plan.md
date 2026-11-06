# Living Plan: Cross-Repo & Submodule Entity References

## Execution Mode
Direct

## 1. Context & Technical Scrutiny
In modular architectures and monorepos with submodules, an umbrella epic in a superproject often coordinates tasks distributed across separate repositories or subprojects (e.g. `src/packages/ui-core`, `src/app-core`).
Currently, `scripts/alongkit/entities/query.py` only implements upward reference resolution:
```python
def _resolve_ref(ref: Any, known: set, root_keys: Optional[set] = None) -> bool:
    qualifier, clean = _ref_key(ref)
    if qualifier == ROOT_QUALIFIER and root_keys is not None:
        known = root_keys
    ...
```
If an umbrella issue lists child issues located in submodules, or if a child references a parent in a sibling subproject using `<subproject-path>:<key>`, `validate_entities()` treats it as an invalid dangling reference and `[gate: entity-reference-integrity]` blocks turn completion or git commits.

### Technical Boundaries & Invariants
- Reference syntax: `<subproject-path>:<key>` where `<subproject-path>` is a normalized POSIX relative path from the current context to the target subproject containing `.along/`.
- Directional semantics:
  - `parent`: Points UP to the parent issue (either `root:<key>` or `<parent-context-path>:<key>`).
  - `related` / `children`: Can point to sibling or descendant subprojects (`<subproject-path>:<key>`).
- Non-blocking Uninitialized Submodules: In CI or fresh clones where submodules are not yet initialized, references to uninitialized subprojects must not cause gate failures; they must be surfaced as non-blocking diagnostics.

---

## 2. Requirements & Traceability
- **REQ-1 (Path-Qualified Reference Parser)**: Update `_ref_key(ref)` in `scripts/alongkit/entities/query.py` to recognize relative filesystem paths containing slashes or directory names.
- **REQ-2 (Cross-Context Entity Key Lookup)**: Implement `_resolve_cross_context_ref(repo_root: str, qualifier: str, key: str) -> bool` to inspect the target subproject's `.along/` state directory.
- **REQ-3 (Validator Integration)**: Extend `validate_entities()` in `scripts/alongkit/entities/validation.py` to validate cross-context references without dangling errors when target keys exist.
- **REQ-4 (Projection Board Rendering)**: Update `compile_issues_board()` in `scripts/alongkit/entities/projections.py` to display external children on umbrella issues.
- **REQ-5 (Git Gate Protection)**: Ensure `check_entity_references()` in `scripts/alongkit/gitgates.py` accounts for cross-context keys during snapshot diffs.
- **REQ-6 (Hermetic Tests)**: Test suite in `tests/test_cross_repo_entities.py`.

---

## 3. Step-by-Step Implementation Changes

### Step 1: Reference Resolver in `scripts/alongkit/entities/query.py`
1. Update `_ref_key(ref: Any) -> Tuple[str, str]`:
   - Strip leading/trailing whitespaces and brackets.
   - If `:` in string:
     - Split on first `:` into `(qualifier, key)`.
     - Normalize `qualifier`: Posix path, lowercase.
     - Return `(qualifier, key)`.
2. Implement `resolve_entity_reference(repo_root: str, ref: Any, local_keys: set, root_keys: Optional[set] = None) -> Tuple[bool, Optional[str]]`:
   - If no qualifier: check `local_keys`.
   - If `qualifier == "root"`: check `root_keys`.
   - If `qualifier` is a relative path:
     - Resolve target directory: `target_ctx = os.path.normpath(os.path.join(repo_root, qualifier))`.
     - If not `os.path.isdir(target_ctx)`:
       - Return `(False, f"subproject path '{qualifier}' does not exist")`.
     - Read target keys via `_context_entity_keys(repo.state_dir(target_ctx), target_keys)`.
     - Check if `key` in `target_keys`:
       - If yes: return `(True, None)`.
       - If no: return `(False, f"entity '{key}' not found in subproject '{qualifier}'")`.

### Step 2: Entity Validation in `scripts/alongkit/entities/validation.py`
1. Update loop over issue reference fields (`parent`, `related`, `blocked_by`, `children`).
2. Delegate reference checking to `resolve_entity_reference`.
3. If target subproject is missing `.along/` because of an uninitialized git checkout, record a warning rather than a fatal integrity error.

### Step 3: Projection Compilation in `scripts/alongkit/entities/projections.py`
1. In `compile_issues_board()`, when rendering an issue carrying `children` or external `related` references:
   - Check for references with `<subproject-path>:<key>`.
   - Render a sub-list under the issue:
     `- External Children: [ui-core:feat--button](src/packages/ui-core/.along/ISSUES/feat--button.md)`

### Step 4: Hermetic Tests in `tests/test_cross_repo_entities.py`
1. Set up temporary root repo with nested subproject repo `sub/`.
2. Create `feat--child` in `sub/.along/ISSUES/`.
3. Create `feat--umbrella` in root with `children: ["sub:feat--child"]`.
4. Create child in `sub` with `parent: "root:feat--umbrella"`.
5. Run `validate_entities`: verify zero integrity errors.
6. Test dangling cross-repo reference: verify descriptive error.
7. Verify `compile_issues_board` outputs link to external child.

---

## 4. Verification Plan
1. Run hermetic tests: `python .along/scripts/test.py tests/test_cross_repo_entities.py`.
2. Run `along doctor --entities` in test fixture and root repo.
3. Typography check: `along sanitize`.
