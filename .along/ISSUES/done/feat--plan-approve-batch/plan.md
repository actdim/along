# Living Plan: Batch Plan Approval & Draft Plan Status Header

## Execution Mode
Direct

## 1. Context & Technical Scrutiny
In complex feature work or epic breakdowns, agents write dozens of decomposed plans (e.g. 20-30 plans in an epic workspace folder). Approving these plans currently requires running `along plan approve <slug> --plan-file <path>` 20-30 separate times.

Additionally:
1. Plans are sometimes work-in-progress or exploratory drafts. There is no standard declarative header to indicate that a plan is a draft and should not be approved.
2. An agent may accidentally approve an unfinalized plan if approval is scripted across a folder.

### Technical Boundaries & Invariants
- Precedence: Frontmatter metadata (`issue: <key>` or `slug: <slug>`) inside the plan file must strictly override filename heuristics (`NN--<key>.md`).
- Draft Guard: If a plan file contains frontmatter `status: draft` or `draft: true`, approval MUST be refused both in batch mode and in single-file mode (`along plan approve <slug> --plan-file <draft-path>`).
- Atomicity and Diagnostics: A dry run (`--dry-run`) must be available to preview approvals across all matched files before committing changes to issue folders and approval logs.
- Canonical Storage: Approving a plan writes it into the canonical issue plan location (`.along/ISSUES/<key>/plan.md`), marks `plan_status: approved` on the ticket, and appends an approval event to the local approvals log.

---

## 2. Requirements & Traceability
- **REQ-1 (Batch Approval Command)**: Extend `handle_plan_command` in `scripts/alongkit/commands/lifecycle.py` to parse `--from <dir>`.
- **REQ-2 (Draft Plan Refusal)**: Implement `is_plan_draft(plan_text: str) -> Tuple[bool, Optional[str]]` and refuse approval if draft status is detected.
- **REQ-3 (Target Resolution)**: Support frontmatter `issue:` / `slug:` with fallback to regex filename parsing `^(?:\d+[-_]+)?(?P<type>feat|bug|debt|task|docs|spike)--(?P<slug>[a-z0-9_-]+)(?:\.plan)?\.md$`.
- **REQ-4 (Dry Run Output)**: Format a tabular preview of batch actions under `--dry-run`.
- **REQ-5 (Batch Execution)**: For each valid non-draft plan, invoke `_approve_ahead()` logic, write `.along/ISSUES/<key>/plan.md`, update ticket frontmatter, and log the approval event.
- **REQ-6 (Hermetic Tests)**: Test suite in `tests/test_plan_approve_batch.py`.

---

## 3. Step-by-Step Implementation Changes

### Step 1: Draft Parser and Matcher in `scripts/alongkit/session.py`
1. Add `is_plan_draft(text: str) -> bool`:
   - Parse YAML frontmatter of the plan if present.
   - Check `fm.get("status") == "draft"` or `fm.get("draft") is True`.
2. Update `check_cli_approval`:
   - If plan text has draft status, return `("plan is marked with status: draft; finalize plan before approving", None)`.

### Step 2: Batch Discovery Engine in `scripts/alongkit/commands/lifecycle.py`
1. Add `_discover_batch_plans(repo_root: str, plans_dir: str) -> List[Dict[str, Any]]`:
   - Iterate over `.md` files in `plans_dir`.
   - Read content; parse frontmatter.
   - Extract target issue key from `fm.get("issue")` or `fm.get("slug")` or filename pattern.
   - Check if plan is draft.
   - Check if target issue exists in `repo_root` using `entities.find_issue_by_slug`.
   - Return list of item dicts: `{"path": p, "issue_key": key, "slug": slug, "is_draft": is_draft, "issue_found": bool, "issue": issue_obj}`.

### Step 3: CLI Router Integration in `handle_plan_command`
1. Check for `--from <dir>` in `along plan approve`.
2. Parse `--dry-run`.
3. If `--dry-run`:
   - Print table of discovered plans:
     ```text
     Batch Plan Approval Preview:
       plans/01--task--setup.md -> task--setup [READY]
       plans/02--feat--api.md   -> feat--api   [REFUSED: status is draft]
       plans/03--feat--ui.md    -> feat--ui    [ERROR: issue not found]
     ```
   - Exit 0.
4. If not dry run:
   - Abort if any plan has errors or is draft unless `--skip-invalid` is passed.
   - Execute approvals for each plan sequentially:
     - Write `.along/ISSUES/<key>/plan.md`.
     - Update ticket frontmatter `plan_status: approved`.
     - Record approval event in `.along/.session/plan-approvals.jsonl`.
   - Sync issues board: `entities.sync_issues_board(repo_root)`.

### Step 4: Hermetic Tests in `tests/test_plan_approve_batch.py`
1. Test single plan approve refuses `status: draft`.
2. Test batch approve `--dry-run` displays accurate status.
3. Test batch approve applies approvals for multiple valid tickets.
4. Test batch approve with mix of draft, valid, and missing issues.

---

## 4. Verification Plan
1. Run hermetic tests: `python .along/scripts/test.py tests/test_plan_approve_batch.py`.
2. Run `along plan --help` to verify updated usage instructions.
3. Typography check: `along sanitize`.
