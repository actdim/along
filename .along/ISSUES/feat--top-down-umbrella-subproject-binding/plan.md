# Plan: top-down umbrella -> subproject child binding (`children:`)

## Execution Mode
Direct

Target executor: a fast model. Follow the steps in order.
Do `bug--subproject-boundary-issue-folder-files` FIRST: Step 4 below edits the same
function (`_bound_subproject_owns_root_entity`) and relies on its folder-aware `stem`.

## Review notes (why this plan differs from the first draft)
- Already in code (do NOT re-add): `validate_entities` already checks `children`
  entries (`scripts/alongkit/entities/validation.py`, around line 204); the board already
  renders qualified `children` as "External Children" (`entities/projections.py`);
  `_ref_key` / `resolve_entity_reference` already parse and resolve `<path>:<key>`
  (`entities/query.py`). All from `feat--cross-repo-entity-references`.
- Design conflict: `ADR-2026-08-27--entity-relationships-unidirectional-graph-and-canonical-slugs`
  says reciprocal fields (`children`) are NOT stored because LLM agents let them drift, and
  `docs/topic--domain-model.md` ("Unidirectional Graph Storage") says the same. Storing
  `children:` is only defensible as the ONE stored direction of a link the child cannot
  point up from (a submodule that forbids `parent:` to the superproject). Record that as a
  new ADR that supersedes the old one (Step 1) and enforce it with a warning (Step 2).
- Dropped: the `umbrella:` field (first draft Step 3.5 and the ticket's third AC). It is
  a second name for `parent:`, not in any requirement. Use `parent: root:<key>` (made
  portable by Step 3) or `children:`.
- Dropped: hand edits of `.along/PROTOCOL.md` (managed copy; it is refreshed from
  `skills/along-init/`). Edit the skill sources and the domain-model doc only.

## Step 0: update the ticket
Strike `umbrella: root:<key>` from the third acceptance criterion; note under REQ-4 that
`children` validation already exists; add `ADR` reference once Step 1 is done.

## Step 1: ADR (via `/along-decision-sync`, never hand-edit projections)
New ADR "children: allowed for cross-context links only", superseding
`ADR-2026-08-27--entity-relationships-unidirectional-graph-and-canonical-slugs`. Content:
keep everything of the old ADR, plus one rule: a parent/child link is stored in exactly
one direction; `parent:` by default; `children:` only with a path-qualified entry
(`<subproject-path>:<key>`) when the child context does not name its parent. Never both
for the same pair.

## Step 2: vocabulary + single-direction warning
- `scripts/alongkit/entities/vocabulary.py`: add `"children"` to `REFERENCE_FIELDS`
  (rename/supersede then rewrite it in the same context).
- `scripts/alongkit/entities/mutation.py`: add `"children"` to `_DELETE_BLOCKING_FIELDS`.
- `validation.py`, in the existing `children` loop: if an entry has no qualifier
  (`_ref_key(c)[0] == ""`), append a WARNING (not an error):
  `"unqualified children entry '<c>': store the link as 'parent:' on the child (ADR ...)"`.
  If the referenced child (qualified) itself has `parent:` naming this issue, append a
  warning `"link stored in both directions: drop 'children: <c>' or the child's parent"`.
  Only check this when the child's front matter is readable; never an error.

## Step 3: `root:` in a standalone clone is a warning (`entities/query.py`)
In `resolve_entity_reference`, the `qualifier == ROOT_QUALIFIER` branch, before returning
the dangling error:
```python
if not ancestor_contexts(repo_root):
    return False, f"unverified root reference '{ref}': no enclosing context (standalone checkout)", True
```
`ancestor_contexts` is defined in the same module. Known trade-off (write it in the
ADR): a dangling `root:x` in a top-level repo becomes a warning too; unqualified refs
there are unaffected.

## Step 4: gate `subproject-boundary` (`scripts/alongkit/hooks/predicates.py`)
Import `_ref_key` from `alongkit.entities` (it is exported).

Helper:
```python
def _children_in_context(repo_root: str, fm: Optional[Dict[str, Any]], context_root: str) -> List[str]:
    """Slugs of `fm`'s `children:` entries whose qualifier resolves to `context_root`."""
    out = []
    for c in (fm or {}).get("children") or []:
        q, k = _ref_key(c)
        if q and q != "root" and repo._same_path(os.path.normpath(os.path.join(repo_root, q)), context_root):
            out.append(entities.parse_key(k)[1])
    return out
```
a) `_subproject_issue_ok`: after `root_fm` is loaded and before the directory scan:
```python
for cslug in _children_in_context(repo_root, root_fm, context_root):
    if _issue_frontmatter(context_root, cslug, include_done=True):
        return True
```
(the child must exist: a typo must not open a whole subproject).

b) `_bound_subproject_owns_root_entity`: after the existing parent-chain check returns
`None` for chain members, add:
```python
target_slug = entities.parse_key(stem)[1]
target_fm = _issue_frontmatter(repo_root, target_slug, include_done=True)
if str(slug) in _children_in_context(repo_root, target_fm, ctx):
    return None
```

c) `check_subproject_boundary`: extend both violation messages with the top-down remedy:
`..., or list it in the root umbrella issue ('children: [<sub>:<child key>]').`

## Step 5: docs
- `docs/topic--domain-model.md`, "Unidirectional Graph Storage" and "Cross-Context
  Resolution": add the Step 1 rule and the `children` field to the field list.
- `skills/along-init/protocol-reference.md` (subproject-boundary section): one line on the
  top-down remedy. Do not touch `.along/PROTOCOL.md` by hand.

## Step 6: tests
`tests/test_subproject_and_team_gates.py` (reuse the umbrella/subproject fixtures):
1. root issue `children: [sub:task--child]`, child has no `parent:`, session bound to root
   -> edit `sub/src/code.py` allowed.
2. same, but `children: [sub:task--missing]` -> denied.
3. `children: [other:task--foo]` -> edit in `sub/` denied.
4. session bound to `sub` child (no `parent:`), root `task--umbrella` lists it ->
   writes to `.along/ISSUES/task--umbrella.md` and `.along/ISSUES/task--umbrella/plans/01--x.md`
   allowed; `.along/ISSUES/task--other/plan.md` denied.
5. existing bottom-up (`parent:`) tests unchanged.

`tests/test_entity_reference_integrity.py`:
6. standalone context (no ancestors), `parent: root:task--u` -> a warning, no error.
7. unqualified `children: [task--x]` -> warning.
8. `tests/test_cross_repo_entities.py` still passes.

## Verification
```bash
python .along/scripts/test.py tests/test_subproject_and_team_gates.py tests/test_entity_reference_integrity.py tests/test_cross_repo_entities.py
```
```bash
python .along/scripts/test.py -q
```
```bash
along sanitize
```

## Out of scope
- `umbrella:` field, umbrellas in a middle-level subproject (qualifiers resolve against
  the workspace root only), a reciprocal sync of `parent` and `children`.
