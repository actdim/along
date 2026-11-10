# Plan: an approved plan grants its "Files to change" as write scope

## Execution Mode
Direct

Target executor: a fast model. Depends on `bug--start-dirty-check-misattribution`
(do that one first).

## Scope decisions vs the ticket
- REQ-1: implemented as "grant and report" (no confirmation prompt: approval already is
  the user's yes, and hooks cannot prompt).
- REQ-2: implemented.
- REQ-3 (`along scope add`): DROPPED. After `bug--start-dirty-check-misattribution`
  REQ-2, `along start <bound slug> --write-scope <path>` skips the dirty checks, so a
  re-start already extends scope with no new command. Update the ticket: strike REQ-3
  and note "covered by bug--start-dirty-check-misattribution REQ-2".

## Facts verified in code
- Every approval path ends in `session.approve_issue_plan(ctx, slug, via, key)`
  (`scripts/alongkit/session.py`, around line 1608). Callers: ExitPlanMode
  (`session.py` around line 646), `along plan approve` (`commands/lifecycle.py` around
  lines 323, 429, 544). This is the single place to hook.
- `approve_issue_plan` already writes the ticket front matter via `set_plan_status`; use
  the same writer for `write_scope`.
- The write-scope gate reads `write_scope` + `allowed_roots` from the bound issue's front
  matter, resolved against the issue's context (`predicates._bound_scope_covers`).
- There is NO plan template with a "Files to change" section today. Agents write it in
  free form. The parser must be tolerant and must never fail an approval.

## Step 1: new module `scripts/alongkit/planscope.py`
Imports: `os`, `re`, `typing`, `from . import repo`. No `entities`, no `session` imports.
```python
_HEADING = re.compile(r"^#{1,6}\s+.*\b(files?\s+to\s+(change|modify|edit)|critical\s+files)\b",
                      re.IGNORECASE)
_PATH = re.compile(r"`([^`\s]+)`")

def plan_paths(plan_text: str) -> List[str]:
    """Paths in backticks inside the plan's "Files to change" section (until the next
    heading of the same or higher level). Keeps only tokens with a '/' or a '.' in the
    last segment; strips a trailing ':line' suffix; dedups, keeps order."""

def split_grantable(paths, ctx: str, workspace_root: str, allowed_roots: List[str]):
    """(grant, rejected): resolve each path against `ctx`; skip paths inside `ctx`
    (already in scope); grant paths inside `workspace_root` or any of `allowed_roots`;
    reject the rest."""
```
Use `repo.is_within` and `os.path.normpath(os.path.join(ctx, p))` (absolute paths as-is).
For each granted path store the path RELATIVE to `ctx` in POSIX form (that is how
`--write-scope` entries resolve).

## Step 2: call it from `approve_issue_plan`
After `set_plan_status(...)`:
```python
from . import planscope
paths = planscope.plan_paths(read_plan(repo_root, slug))
if paths:
    grant, rejected = planscope.split_grantable(paths, repo_root, binding_root(repo_root),
                                               current_allowed_roots)
    # merge `grant` into the ticket's write_scope (no duplicates), same writer as set_plan_status
    # print one line each:  -> Plan grants write scope: a, b   /   [Notice] Not granted (outside workspace): c
```
Wrap the whole block in `try/except (OSError, ValueError)` and print a notice on failure:
an approval must never fail because of this.
`current_allowed_roots`: the ticket's `allowed_roots` list (same parsing as
`containment._as_list`).

## Step 3: tests (new file `tests/test_plan_scope.py`)
1. `plan_paths` unit cases: section with backticked paths; paths with `:12`; heading
   variants ("Files to change", "Critical files"); text outside the section is ignored;
   no section -> `[]`.
2. `split_grantable`: inside ctx -> skipped; `../other/x.ts` inside workspace -> granted;
   an absolute path outside the workspace -> rejected.
3. End to end: subproject issue, plan lists `../other/x.ts`, `along plan approve
   --plan-file` (follow the approval pattern in `tests/test_issue_plans.py`); the
   ticket's `write_scope` now holds the path and a write to it passes the
   write-scope check (`predicates._bound_scope_covers` returns True).

## Verification
```bash
python .along/scripts/test.py tests/test_plan_scope.py tests/test_issue_plans.py
```
```bash
python .along/scripts/test.py -q
```

## Out of scope
- A plan template change, `along scope add`, revoking scope when a plan is revised.
