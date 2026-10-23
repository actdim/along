# Living Plan: orchestrator-review-fail-open

## Revision 1 (2026-10-23T20:32:09Z, ExitPlanMode)

# Fix: orchestrator and handoff pass steps on missing or broken reviews (`bug--orchestrator-review-fail-open`)

Execution Mode: Direct (one subsystem: `handoff.py` + `orchestrator.py` + its CLI command; no core engine refactor)

## Context
The review of 2d84ceb / 6a379f5 found that the cross-runtime orchestrator can report `completed`
for work nobody reviewed. Since `feat--pre-approved-plans` the orchestrator (and the daemon on top
of it) runs whole issues unattended, so these fail-open paths ship unreviewed changes. The issue
file lists REQ-1..REQ-9; this plan implements all of them.

## Changes

### 1. `scripts/alongkit/handoff.py`
- **Identifier validation (REQ-8).** Add `_SAFE_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")`
  and `_require_safe_id(value, kind)` (rejects no-match and `..`). Apply to `slug` in
  `get_runs_dir` / `get_questions_dir` / `get_handoff_path` / review paths / `generate_brief`
  (one private `_session_dir(repo_root, slug)` wrapper over `session.get_session_dir`), to
  `run_id` in `create_run_record` / `save_run_record` / `load_run_record` (after stripping
  `.json`), and to `qid` in `create_question` / `load_question` / `answer_question`. `step` is cast
  with `int()`. Existing ids (`run-a`, `q-1`, uuid hex, `orch-...`) all pass.
- **Verdicts fail closed (REQ-2).** `parse_review_verdict` no longer defaults `verdict` to
  `pass` (missing -> `""`). `load_review_verdict` runs `validate_review_verdict` and returns
  `valid: bool` and `errors: [...]` alongside verdict/defects; a file that does not parse still
  returns `None` (orchestrator treats both as fail).
- **Brief robustness (REQ-9).** `_extract_open_defects` skips non-dict defects.
- **Exclusive claims (REQ-5).** Private context manager `_claim_lock(repo_root, slug)`:
  `os.open(<session>/claim.lock, O_CREAT|O_EXCL|O_WRONLY)`, retry every 50 ms up to 5 s, treat a
  lock older than 30 s as stale (remove and retry), always remove in `finally`; timeout raises
  `TimeoutError`. `acquire_claim` and `release_claim` do their load-check-save inside it, so a
  second acquirer sees the first one's claim. (Kept private here; `bug--runner-daemon-lifecycle-safety`
  can lift it into `textio` for the PID file.)

### 2. `scripts/alongkit/orchestrator.py`
- **Review verdict (REQ-1).** Replace the verdict block in `run_step_loop` with
  `_evaluate_review(step, rev_runner, rev_record) -> (verdict, defects)`:
  valid file -> its verdict; invalid file -> `fail` + blocking defect naming the validation
  errors; no file -> stdout front-matter fallback, written through `write_review_verdict`
  (a `ValueError` there -> `fail` + blocking defect); nothing usable -> `fail` + blocking defect
  "reviewer produced no machine-readable verdict (exit code N)". No path yields `pass` by default.
  The `self.dry_run` special case in this block goes away.
- **Implementer failure (REQ-3).** After the timeout check: `impl_outcome == "fail"` -> skip the
  reviewer and go to the existing failed-review branch with defect "implementer run failed
  (exit code N)" (retry counter, `open_defects`, exhaustion handling reused). Restructure the
  fail branch into a helper `_record_step_failure(step, defects)` used by both paths.
- **Dry run (REQ-4).** `orchestrate()` returns `self.preview(skip_scout, skip_architect)` first
  when `dry_run`: no `init_session`, no claim, no signal handlers, no runner calls. `preview`
  lists each phase that would run (`scout`, `plan` when `session.issue_plan_state` says the issue
  plan is ready else `architect`, then `implementer`/`reviewer` per step from `state.json` or
  "steps from plan") with role, runtime, model, timeout and `len(generate_brief(...))` bytes
  (`generate_brief` is read-only). Result: `{"status": "dry-run", "slug", "phases": [...]}`.
- **Claim lifecycle (REQ-6).** `_renew_claim()` calls `acquire_claim(run_id=self.run_id, ttl=<run timeout> + 300)`
  before every `execute_run`; on `False` the phase returns `{"status": "blocked", ...}`.
  `finally` and the signal handler call `release_claim(..., force=False)`.
- **Timeout default (REQ-7).** `_instantiate_runner`: `r_cfg.get("timeout") or self.timeout or DEFAULT_TIMEOUT`.

### 3. `scripts/alongkit/commands/orchestrator.py`
- Status `dry-run`: print the phase table (or JSON) and exit 0.

### 4. Tests (each verified to fail on the old code)
- `tests/test_orchestrator.py` (MockRunner harness): reviewer exit 0 without review file -> step
  retried with blocking defect, never `completed`; review file without `verdict`, and
  `verdict: fail` with only nits -> fail; implementer `fail` -> reviewer not invoked, retries 1;
  dry run -> `state.json` bytes and run-record dir unchanged, no claim, status `dry-run` with
  phases; claim taken over mid-run by another run id -> `blocked`, other claim survives `finally`;
  runner timeout defaults to `DEFAULT_TIMEOUT`.
- `tests/test_handoff_entities.py`: deterministic race - two threads, `session.load_state`
  wrapped with a `threading.Barrier(2, timeout=0.5)` (broken barrier tolerated): exactly one
  `acquire_claim` returns True (old code: both); stale `claim.lock` older than 30 s is recovered;
  `../x` / `a/b` for run_id, qid and slug raise `ValueError`; `load_review_verdict` on a file
  without verdict returns `valid: False`; brief with a non-dict defect does not raise.
- Update existing tests that relied on the old defaults (the CLI dry-run tests keep exit 0).

### 5. Along bookkeeping
Tick acceptance criteria, `/along-commit`, `along wrap orchestrator-review-fail-open --summary ... --no-decisions`;
update `docs/topic--domain-model.md` (claim lock file, verdict validity) if it documents these.

## Verification
- `python .along/scripts/test.py test_orchestrator.py`, `test_handoff_entities.py`, `test_daemon.py`
  (daemon calls `run_orchestration`), then the full suite (`-q`), green.
- Stash the source changes and rerun the new tests to confirm they fail on the old code.
- `along orchestrate <slug> --dry-run --json` on a fixture repo: tree unchanged (`git status`).
- `git diff --stat`, `along sanitize`.
