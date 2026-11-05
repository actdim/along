# Living Plan: Scope entity-deletion-protection to Canonical Entity Files

## Execution Mode
Direct

## 1. Context & Technical Scrutiny
In ALONG-PROTOCOL 4.6.0, runtime predicate `check_entity_deletion_protection` in `scripts/alongkit/hooks/predicates.py` uses a crude directory regex:
```python
_ENTITY_DIR_PATTERN = re.compile(
    r"\.along[/\\]+(?:ISSUES|DECISIONS|MILESTONES)(?:[/\\]|$)",
    re.IGNORECASE,
)
```
Whenever an agent invokes a file deletion tool (`delete_file`, `remove_file`) or a shell deletion command (`rm`, `del`, `Remove-Item`), any target containing `.along/ISSUES/` triggers a hard rejection. This blocks deleting temporary plan drafts (e.g. `.along/ISSUES/<epic>/plans/14c--old-name.md`), obsolete notes, or untracked scratch artifacts.

Furthermore:
1. The error message erroneously cites `[gate: entity-reference-integrity]` instead of `[gate: entity-deletion-protection]`.
2. In `scripts/alongkit/gitgates.py`, `touches_entities()` checks if any directory segment after `.along/` matches `ENTITY_SUBDIRS`, incorrectly marking any file under `.along/ISSUES/...` as an entity mutation during commit gates.

### Technical Boundaries & Invariants
- Canonical entities are:
  - Issues: `.along/ISSUES/<type>--<slug>.md` or legacy `.along/ISSUES/<key>/<key>.md` where `<type>` is in `feat|bug|debt|task|docs|spike`.
  - Canonical approved plans: `.along/ISSUES/<key>/plan.md`.
  - Decisions: `.along/DECISIONS/ADR-*.md`.
  - Milestones: `.along/MILESTONES/<slug>.md`.
- Non-entity files:
  - Any file in subdirectories under an issue folder other than `plan.md` (e.g. `<key>/plans/*`, `<key>/attachments/*`, `<key>/notes/*`).
  - Files not matching canonical entity naming patterns.
- Deletions of untracked or auxiliary non-entity files must succeed without bypass or gate acknowledgements.

---

## 2. Requirements & Traceability
- **REQ-1 (Path Matcher Narrowing)**: Implement a strict predicate helper `is_canonical_entity_path(path: str) -> bool` that matches ONLY canonical entity files and canonical plans.
- **REQ-2 (Hook Predicate Update)**: Update `check_entity_deletion_protection` in `scripts/alongkit/hooks/predicates.py` to use `is_canonical_entity_path` instead of `_ENTITY_DIR_PATTERN`.
- **REQ-3 (Error Citation Fix)**: Change denial error string in `check_entity_deletion_protection` to cite `[gate: entity-deletion-protection]`.
- **REQ-4 (Git Gate Alignment)**: Update `touches_entities` in `scripts/alongkit/gitgates.py` to leverage entity path validation so auxiliary issue files do not trigger full entity graph recalculations.
- **REQ-5 (Hermetic Test Coverage)**: Verify both deletion rejection for canonical entities/plans and deletion allowance for attachment/draft files in `tests/test_gates_entity_deletion.py`.

---

## 3. Step-by-Step Implementation Changes

### Step 1: Entity Path Matcher in `scripts/alongkit/entities/vocabulary.py`
1. Define regex patterns for canonical entity files:
   - Issue: `r"\.along[/\\]+ISSUES[/\\]+(?:done[/\\]+)?(?P<type>feat|bug|debt|task|docs|spike)--[a-z0-9_-]+\.md$"`
   - Issue Plan: `r"\.along[/\\]+ISSUES[/\\]+(?:done[/\\]+)?[^/\\]+[/\\]+plan\.md$"`
   - ADR: `r"\.along[/\\]+DECISIONS[/\\]+ADR-[a-z0-9_-]+\.md$"`
   - Milestone: `r"\.along[/\\]+MILESTONES[/\\]+[a-z0-9_-]+\.md$"`
2. Implement `is_canonical_entity_path(path: str) -> bool`.
3. Ensure auxiliary paths like `.along/ISSUES/<key>/plans/draft.md` return `False`.

### Step 2: Hook Predicate Update in `scripts/alongkit/hooks/predicates.py`
1. Replace `_ENTITY_DIR_PATTERN` in `check_entity_deletion_protection` with `is_canonical_entity_path`.
2. For shell commands, extract file targets using `shellparse` and test each target against `is_canonical_entity_path`.
3. Update error message:
   ```text
   Entity file deletion rejected by [gate: entity-deletion-protection]: Deleting an issue, ADR, milestone, or canonical plan is forbidden. Use 'along issue supersede' / 'along issue rename'.
   ```

### Step 3: Git Gate Alignment in `scripts/alongkit/gitgates.py`
1. Update `touches_entities(paths: Iterable[str]) -> bool` to check `is_canonical_entity_path(p)` rather than general path segments.

### Step 4: Unit Tests in `tests/test_gates_entity_deletion.py`
1. Test deleting `.along/ISSUES/task--sample.md` -> BLOCKED.
2. Test deleting `.along/ISSUES/task--sample/plan.md` -> BLOCKED.
3. Test deleting `.along/ISSUES/task--sample/plans/14c--old-name.md` -> ALLOWED.
4. Test deleting `.along/ISSUES/task--sample/attachments/data.csv` -> ALLOWED.
5. Test shell command `rm .along/ISSUES/feat--epic/plans/draft.md` -> ALLOWED.
6. Test shell command `rm .along/ISSUES/feat--epic.md` -> BLOCKED with `[gate: entity-deletion-protection]`.

---

## 4. Verification Plan
1. Run hermetic tests: `python .along/scripts/test.py tests/test_gates_entity_deletion.py`.
2. Verify Along doctor: `along doctor --entities`.
3. Typography check: `along sanitize`.
