# Living Plan: Partial Wrap & Phase Checkpoints for Multi-Session Issues

## Execution Mode
Direct

## 1. Context & Technical Scrutiny
In ALONG-PROTOCOL, work often spans multiple independent agent turns or sessions (e.g. Phase A, Phase B, Phase C of an architectural migration).
Currently, `scripts/alongkit/lifecycle.py` (`execute_wrap`) enforces that wrapping an issue always closes it:
```python
if status not in entities.CLOSED_ISSUE_STATUSES:
    print(f"[Error] Invalid closing status '{status}'...", file=sys.stderr)
    return 1
```
The wrap pipeline then relocates the issue file to `.along/ISSUES/done/` and deletes `.along/.session/<slug>/`. Agents attempting to end a session without closing the issue were forced to run `along wrap --dry-run` and halt execution, which leaves session logs unwritten and history unrecorded.

### Technical Boundaries & Invariants
- Lifecycle Separation:
  - `along session wrap <slug> --keep-open`: Wraps the *agent session*, writes the session record, appends history, runs tests, releases the session lock, but preserves the issue ticket in `status: in-progress`.
  - `along wrap <slug>` (or `along session wrap <slug> --status done`): Closes the *issue ticket*, relocates it to `done/`, and archives the issue.
- Plan Preservation: When `--keep-open` is used, the approved plan in `.along/ISSUES/<key>/plan.md` must not be deleted or invalidated. The next session starting on the issue must see `plan_status: approved` and resume directly.
- Markdown Phase Checkboxes: Rather than corrupting YAML frontmatter with complex checkbox structures, phases are represented as standard markdown checkboxes (`- [ ] Phase 1`) under `## Phases` in the issue body. `--phase <name>` ticks the matching checkbox.

---

## 2. Requirements & Traceability
- **REQ-1 (CLI Option & Status Handling)**: Add `--keep-open` flag to `along session wrap` and `along wrap`. When present, allow `status="in-progress"`.
- **REQ-2 (Issue File Preservation)**: In `execute_wrap`, skip moving issue file to `done/` when `keep_open=True`. Update `updated` timestamp in frontmatter.
- **REQ-3 (Phase Checkbox Ticking)**: Implement `tick_issue_phase(issue_file_path: str, phase_name: str) -> bool` to update markdown task lists in the ticket body.
- **REQ-4 (Session Logging & History)**: Write the blackboard record into `.along/SESSIONS/<date>--<slug>.md` and append entry to `.along/HISTORY.md`.
- **REQ-5 (Blackboard & Binding Reset)**: Clear agent session bindings in `bindings.json` and reset turn-specific session state while preserving the canonical issue plan.
- **REQ-6 (Hermetic Tests)**: Test suite in `tests/test_session_wrap_partial.py`.

---

## 3. Step-by-Step Implementation Changes

### Step 1: Wrap Pipeline Refactoring in `scripts/alongkit/lifecycle.py`
1. Update `execute_wrap()` parameter signature:
   ```python
   def execute_wrap(
       repo_root: str,
       slug: str,
       status: str = "done",
       summary: Optional[str] = None,
       dry_run: bool = False,
       no_verify: bool = False,
       agent: Optional[str] = None,
       decisions: Optional[List[str]] = None,
       force_reason: Optional[str] = None,
       guard_bypass: bool = False,
       bypass_reason: Optional[str] = None,
       no_commit: bool = False,
       keep_open: bool = False,
       phase: Optional[str] = None,
   ) -> int:
   ```
2. If `keep_open` is `True`:
   - Override `status = "in-progress"`.
   - Relax `status not in entities.CLOSED_ISSUE_STATUSES` validation when `keep_open` is set.
3. In Step 3 (Issue Finalization):
   - If `keep_open` is `True`:
     - Do NOT move issue to `.along/ISSUES/done/`.
     - Update YAML frontmatter: `updated = today`.
     - If `phase` is provided: call `tick_issue_phase(src_file, phase)`.
   - If `keep_open` is `False`:
     - Retain existing behavior (move to `done/`, set `completed = today`, update links).
4. In Step 7 (Blackboard Purge):
   - If `keep_open` is `True`:
     - Remove turn state and release agent binding.
     - Keep `.along/ISSUES/<key>/plan.md` intact.

### Step 2: Phase Checkbox Helper in `scripts/alongkit/frontmatter.py` or `lifecycle.py`
1. Implement `tick_issue_phase(file_path: str, phase_name: str) -> bool`:
   - Read file content.
   - Match regex `r"-\s*\[\s*\]\s*(?:\*\*)?" + re.escape(phase_name)`.
   - Replace with `- [x] ` + phase name.
   - Write updated file.

### Step 3: CLI Option Exposure in `scripts/alongkit/commands/session.py`
1. Add `--keep-open` flag to `along session wrap` parser.
2. Add `--phase <name>` argument to `along session wrap` parser.
3. Pass `keep_open` and `phase` to `lifecycle.execute_wrap()`.
4. Mirror same options in `scripts/along_wrap.py`.

### Step 4: Hermetic Tests in `tests/test_session_wrap_partial.py`
1. Create issue with `## Phases` containing `- [ ] Phase 1` and `- [ ] Phase 2`.
2. Start session on issue; make edits; run `along session wrap <slug> --keep-open --phase "Phase 1" --summary "Phase 1 done" --no-decisions`.
3. Assert:
   - Issue remains in `.along/ISSUES/<type>--<slug>.md` with `status: in-progress`.
   - Body contains `- [x] Phase 1` and `- [ ] Phase 2`.
   - Session log is written to `.along/SESSIONS/<date>--<slug>.md`.
   - Entry appended to `.along/HISTORY.md`.
   - Issue board in `.along/ISSUES.md` still lists issue as active.
4. Start subsequent session on same issue: verify plan is recognized without re-approval.
5. Wrap with status `done`: verify issue moves to `done/`.

---

## 4. Verification Plan
1. Run hermetic tests: `python .along/scripts/test.py tests/test_session_wrap_partial.py`.
2. Verify board sync: `along issue sync`.
3. Typography check: `along sanitize`.
