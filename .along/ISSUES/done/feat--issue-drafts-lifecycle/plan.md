# Plan: issue drafts (untracked) with promotion on start

## Execution Mode
Direct

Target executor: a fast model. Keep it to the steps below.

## Review notes (why this plan is smaller than the first draft)
- `.gitignore` edit: replaced by the repo's own convention, a self-ignoring
  `.gitignore` (`*`) inside the directory (see `migration.backup_root`). It works in every
  consumer repo without editing their `.gitignore`.
- `alongkit.entities.validate_issue_frontmatter` does not exist. Use
  `entities.is_issue_stub` plus a front-matter parse, the same checks `along start` runs.
- Dropped: a separate `along issue draft` command and `along issue drafts` listing
  (`along issue create --draft` plus doctor's list cover them), and the wrap notice (a
  draft is private and unrelated to the issue being wrapped; a notice on every wrap is
  noise). Doctor keeps the stale-draft report.
- Update the ticket's REQ-2 / REQ-4 accordingly when you start.

## Facts verified in code
- `scripts/alongkit/commands/issue.py` `_issue_create(repo_root, args, issues_dir, today)`
  builds the ticket text and writes `target_file = os.path.join(issues_dir, ...)`, then
  syncs the board. Subcommands are dispatched from a dict in `handle_issue_command`.
- Entity walkers skip dot-prefixed names, and `repo.RUNTIME_ONLY_ENTRIES` lists Along's
  runtime-only entries of `.along/`.
- `along start` (`commands/lifecycle.py`): `entities.find_issue_by_slug(repo_root, slug)`;
  not found -> `CommandError("Issue '<slug>' not found ...")`.

## Step 1: `scripts/alongkit/drafts.py`
```python
DRAFTS_DIRNAME = ".drafts"

def drafts_dir(repo_root: str) -> str:          # <state_dir>/.drafts, created with a "*" .gitignore
def find_draft(repo_root: str, slug: str) -> Optional[str]:   # path of <type>--<slug>.md or None
def list_drafts(repo_root: str) -> List[Dict[str, Any]]:      # [{key, path, mtime}]
def promote(repo_root: str, slug: str) -> str:  # returns the new ticket path
```
`promote`: read the draft; refuse (`ValidationError`, exit 2) if `is_issue_stub` reports
placeholders or the front matter does not parse; refuse if a ticket with that slug
already exists; `os.replace` into `.along/ISSUES/<key>.md`; then
`entities.sync_issues_board(repo_root)`.
Add `".drafts"` to `repo.RUNTIME_ONLY_ENTRIES`.

## Step 2: CLI (`commands/issue.py`)
- `along issue create ... --draft`: same code path; only `issues_dir` becomes
  `drafts.drafts_dir(repo_root)` and the board sync is skipped. The duplicate-slug check
  must also look in drafts.
- `along issue promote <slug>`: calls `drafts.promote`, prints the new path.
- Add both to the usage text.

## Step 3: `along start` promotes a draft
In the start handler, when `find_issue_by_slug` returns None:
```python
draft = drafts.find_draft(repo_root, slug)
if draft:
    new_path = drafts.promote(repo_root, slug)
    print(f"-> Promoted draft to {repo.safe_relpath(new_path, repo_root)}")
    issue = entities.find_issue_by_slug(repo_root, slug)
```
then continue as today (status in-progress, bind).

## Step 4: doctor
`_doctor_drafts_checks(repo_root, warnings)`: drafts with mtime older than 7 days ->
`[WARN] N draft(s) older than 7 days in .along/.drafts/: a, b. Promote ('along issue promote <slug>') or delete.`

## Step 5: tests (`tests/test_issue_drafts.py`)
1. `create --draft` writes under `.along/.drafts/`, the dir has a `*` `.gitignore`,
   `ISSUES.md` does not list it, `git status --porcelain` is empty (in a git fixture).
2. `promote` moves it, the board lists it; promoting a stub draft exits 2.
3. `along start <draft slug>` promotes, marks in-progress, binds.
4. `create` refuses a slug that exists as a draft.
5. doctor reports an old draft (set mtime with `os.utime`).

## Verification
```bash
python .along/scripts/test.py tests/test_issue_drafts.py
```
```bash
python .along/scripts/test.py -q
```

## Out of scope
- Wrap notices, a background drainer, interaction with `feat--workspace-activity-tracking`.
