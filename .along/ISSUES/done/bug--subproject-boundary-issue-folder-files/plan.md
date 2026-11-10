# Plan: subproject-boundary allows files inside an umbrella issue's folder

## Execution Mode
Direct

Target executor: a fast model. One function changes, plus tests.

## Facts verified in code
- `scripts/alongkit/hooks/predicates.py`, `_bound_subproject_owns_root_entity`
  (around line 1937) derives the entity from the basename:
  ```python
  stem = os.path.basename(rel_path)
  stem = stem[:-3] if stem.endswith(".md") else stem
  ```
  For `.along/ISSUES/task--umbrella/plans/01--x.md` the stem is `01--x`, so
  `entities.parse_key(stem)[1]` is `x`, never the umbrella slug. Root cause confirmed.
- The parent chain is read live (`_issue_frontmatter(ctx, slug, include_done=True)` then
  `_parent_chain_slugs`). No cache. REQ-4 only needs a test.
- `rel_path` reaching this function is POSIX and starts with `.along/` (see the caller in
  `check_subproject_boundary`, which excludes `.along/.session/`).

## Step 1: derive the key from the issue folder
Replace the two `stem = ...` lines with:
```python
parts = rel_path.split("/")
in_done = len(parts) >= 3 and parts[1] == "ISSUES" and parts[2] == "done"
# A file inside .along/ISSUES/<key>/ or .along/ISSUES/done/<key>/ belongs to <key>.
if parts[1:2] == ["ISSUES"] and len(parts) >= (5 if in_done else 4):
    stem = parts[3] if in_done else parts[2]
else:
    stem = os.path.basename(rel_path)
stem = stem[:-3] if stem.endswith(".md") else stem
```
Expected results (put each in the tests below):
- `.along/ISSUES/task--u.md` -> `task--u` (basename, unchanged).
- `.along/ISSUES/done/task--u.md` -> `task--u` (basename, unchanged).
- `.along/ISSUES/task--u/plan.md` -> `task--u`.
- `.along/ISSUES/task--u/plans/01--x.md` -> `task--u`.
- `.along/ISSUES/done/task--u/plans/01--x.md` -> `task--u`.
- `.along/DECISIONS/adr--x.md` -> `adr--x` (basename, unchanged).

Update the docstring: one line saying files in `ISSUES/<key>/` count as entity `<key>`,
with the tag `[bug--subproject-boundary-issue-folder-files]`.

## Step 2: tests
Add to `tests/test_subproject_and_team_gates.py` (reuse the fixture that already tests the
root-entity branch; search for `_bound_subproject_owns_root_entity` or the message text
"root entities on the bound issue's parent chain"):
1. `test_umbrella_folder_file_allowed_on_parent_chain`: bound subproject issue has
   `parent: task--umbrella`; write `.along/ISSUES/task--umbrella/plans/01--x.md` -> allowed.
2. `test_other_root_issue_folder_file_denied`: write `.along/ISSUES/task--other/plan.md` -> denied.
3. `test_done_ticket_path_unchanged`: `.along/ISSUES/done/task--umbrella.md` behaves as before
   (allowed when on the chain).
4. `test_parent_added_mid_session_takes_effect`: write denied; add `parent:` to the bound
   issue's front matter on disk; the same write is allowed.

## Verification
```bash
python .along/scripts/test.py tests/test_subproject_and_team_gates.py tests/test_subproject_model.py
```
```bash
python .along/scripts/test.py -q
```

## Out of scope
- Any change to how the parent chain is resolved.
