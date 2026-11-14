# Plan: Stop gate false positives and ackable Stop denials

Issue: `bug--stop-gate-false-positives` (REQ-1..REQ-6).

## Execution Mode
Role-Based (along-team). Six work packages across hooks, kb-sync, wrap, CLI and protocol
text. Each work package below is one along-team step: start it with
`along scratch update stop-gate-false-positives --step <N> --step-status in-progress`,
finish it with a review record in `.along/.session/stop-gate-false-positives/reviews/step-<N>.md`
before the turn ends (gate `team-reviews-before-stop`).

Target executor: a fast model. Follow the steps in order. Do not add helpers, flags,
config keys or files that are not listed here. Keep every function name used below
exactly as written. If a fact below does not match the code, stop and report it; do not
improvise a different design.

## Ground rules for the executor
- Before any source edit: `along start stop-gate-false-positives`, then the user approves
  this plan (`along plan approve --plan-file .along/ISSUES/bug--stop-gate-false-positives/plan.md`
  only after the user's explicit yes in chat).
- Edit files with file tools only. Never write file content through a shell
  (no heredocs, no `python -c`). ASCII only in `.md .py` (no em dashes, no smart quotes,
  no non-ASCII arrows): run `along sanitize` before committing.
- Do not touch `.along/rules/**/*.md`, `.along/ISSUES.md`, `.along/DECISIONS.md`,
  `.along/CONSTRAINTS.md`, `docs/INDEX.md` by hand (projections / rule packs).
- Do not edit existing tests to make them pass. New tests go into the files named in
  each step. Tests are hermetic: temp directories only, `git init` inside the temp dir.
- Run targeted tests with the lifecycle runner, never raw pytest:
  `python .along/scripts/test.py -q tests/test_<name>.py`. Full suite at the end:
  `python .along/scripts/test.py -q`.
- Commit per step with `/along-commit` (message names `stop-gate-false-positives`,
  no `Co-Authored-By:` trailers).

## Facts verified in code (2026-11-13)
- `scripts/alongkit/hooks/predicates.py`
  - `MUTATION_WHITELIST_PATTERNS` (line ~183): context-relative patterns incl.
    `docs/INDEX.md`, `docs/decisions/**`, `llms.txt`, `llms-full.txt`.
  - `_matches_in_context(rel, repo_root, patterns)` (~275): matches against the repo root
    and the owning subproject context (a dir with `.along/`). A package dir like
    `packages/dashboard-ui/` (has `AGENTS.md` + `docs/`, no `.along/`) is NOT a context,
    so `packages/dashboard-ui/docs/INDEX.md` does not match.
  - `_is_plan_governed(rel, repo_root)` (~1460): used ONLY by the Stop branch of
    `check_mutation_authorization` (~1366).
  - `check_mutation_authorization` (~1274): PreToolUse branch for file tools; Stop branch
    reads `trace["turn_baseline"]` and calls `turnstate.changed_since(...)` (whole tree).
  - `record_tool_activity` (~526): on `USER_PROMPT_SUBMIT` stores
    `trace["turn_baseline"] = turnstate.snapshot(repo_root)`; file-tool edits are recorded
    on `POST_TOOL_USE`; the shell branch (`run_command`, `execute_command`, `bash`, `shell`)
    returns early unless `PRE_TOOL_USE` and only handles test detection.
  - `record_gate_denial` (~363): writes a ledger `deny` only for `PRE_TOOL_USE` via
    `_record_denial_event` (~386), which needs a bound blackboard
    (`session.bound_blackboard`) and skips the trace entry for procedural gates.
  - `check_unresolved_denials` (~1615): Stop gate over `session_denials(...)`, quiet when
    unbound unless `enforce_unbound`.
  - `check_active_issue` (~1467): no 1-line exemption.
- `scripts/alongkit/hooks/turnstate.py`: `snapshot(repo_root)` ->
  `{abs posix path: "<git code>:<sha1>"}` of dirty paths; `changed_since(repo_root, baseline)`
  -> sorted repo-relative POSIX paths whose state differs.
- `scripts/alongkit/hooks/engine.py` `HookEngine.evaluate` (~60): on an enforcing denial
  calls `record_gate_denial(...)` then returns; `record_tool_activity` runs only when all
  gates allowed.
- `scripts/alongkit/hooks/config.py`: `CLAUDE_POST_TOOL_MATCHER` already includes
  `Bash|PowerShell`, so Claude Code sends PostToolUse for shell commands.
- `.along/rules/gates.yaml`: this repo sets `enforce_unbound: true` for
  `require_plan_approval` (that is why the gate fired after `wrap` unbound the session).
- `scripts/along_kb_sync.py`
  - `_kb_generate_index(...)` (~1216): always writes `docs/INDEX.md` with `"updated": today`
    (date-only rewrite on every run).
  - `sync_decisions_to_docs(...)` (~892): always rewrites `docs/decisions/*.md` and
    `docs/decisions/INDEX.md`, even when identical.
  - `sync_llms_txt` / `sync_llms_full_txt` (~756 / ~820): already skip identical writes.
  - `_kb_sync_subprojects(...)` (~1325): cascades `sync_kb(ctx, ...)` into every context
    from `repo.find_agent_contexts` + `repo.find_package_doc_roots` (package-level docs).
  - `sync_kb(...)` (~1635): `today = datetime.now().strftime("%Y-%m-%d")` (line ~1651).
- `scripts/alongkit/lifecycle.py`
  - `execute_wrap` (~1109): after `tx.commit()` runs `along_kb_sync.py` as a subprocess
    (~1497), then `purge_archived(...)` deletes the blackboard (`.along/.session/<slug>`,
    incl. `events.jsonl`), then `_auto_commit_wrapped_work(...)` (~863).
  - `_auto_commit_wrapped_work` stages `closeout.PROJECTION_FILES` resolved against
    `repo_root` only (~898): package-level indexes are never committed.
- `scripts/alongkit/closeout.py`: `PROJECTION_FILES` (~406), `path_key(path)` (~49),
  `git_top`, `git_changes(repo_root)` (top-relative paths), `content_fingerprint(top, paths)`
  (~530), `_is_wrap_byproduct(path)` (~542). `run_closeout` already commits wrap
  byproducts under `docs/` via `_is_wrap_byproduct` (covers package docs).
- `scripts/alongkit/commands/gates.py`: `_denials_target` (~188), `_handle_denials` (~201)
  print `No gate denials to read: this session is not bound to an issue` when unbound.
- Protocol text with the 1-line exemption: `skills/along-init/protocol.md:16`,
  `skills/along-init/protocol-reference.md:52`; their rendered copies are the managed
  block in `AGENTS.md:15` and `.along/PROTOCOL.md:47` (engine-written, do not hand-edit).
- Test runner: `.along/scripts/test.py` takes test files as positional args, `-q`, `-k`.

## Decision D1 (needs the user's answer at plan review): REQ-6
- **Option A (default, recommended): remove the exemption text.** Smaller, no new bypass
  surface in the gates. The gates stay as they are.
- Option B: implement the exemption in the gates (spec in Step 6B).
The executor does Step 6A unless the user picked B. Record the choice in the issue file
under `## Plan` ("D1: A" or "D1: B").

---

## Step 1 - Compiled projections are not plan-governed (REQ-1)

Files: `scripts/alongkit/closeout.py`, `scripts/alongkit/hooks/predicates.py`.

1. In `closeout.py`, directly below `PROJECTION_FILES`, add:

   ```python
   #: File names `along kb-sync` / `along decision sync` compile at any level (root,
   #: subproject, package doc root). [bug--stop-gate-false-positives] REQ-1
   COMPILED_PROJECTION_NAMES: Tuple[str, ...] = ("llms.txt", "llms-full.txt")


   def is_compiled_projection(rel: str, base: str) -> bool:
       """`rel` (POSIX, relative to `base`) is an index or llms file the KB engines compile.

       - `<any>/docs/INDEX.md` or `<any>/docs/decisions/INDEX.md` whose front matter on disk
         says `protocol: along` and `type: index`;
       - `<any>/llms.txt`, `<any>/llms-full.txt` (also under `.well-known/`) when the owning
         directory has a `docs/` folder.
       A missing file is not a projection (a deletion stays plan-governed).
       """
   ```

   Implementation rules:
   - Normalize with `repo.normalize_posix(rel).lstrip("/")`; split on `/`.
   - INDEX case: `parts[-1] == "INDEX.md"` and (`parts[-2:-1] == ["docs"]` or
     `parts[-3:-1] == ["docs", "decisions"]`). Read the file with
     `textio.read_text(path, strict=False)`, parse with `frontmatter.try_parse(text)`
     (returns `(mapping, body, err)`), require
     `mapping.get("protocol") == "along" and str(mapping.get("type")) == "index"`.
     Catch `OSError, UnicodeDecodeError, ValueError` -> False.
   - llms case: `parts[-1] in COMPILED_PROJECTION_NAMES`; owner dir = parent, or the
     grandparent when the parent is `.well-known`; return
     `os.path.isfile(path) and os.path.isdir(os.path.join(owner_abs, "docs"))`.
   - Import `frontmatter`/`textio` inside `closeout.py` only if not imported yet (check
     the import block at the top of the file first).

2. In `predicates.py`, change `_is_plan_governed` to:

   ```python
   def _is_plan_governed(rel: str, repo_root: str) -> bool:
       """A path whose change needs an approved plan: not Along state, not a planning
       artifact, not a projection the KB engines compile (any level). REQ-1"""
       if _matches_in_context(rel, repo_root, list(MUTATION_WHITELIST_PATTERNS)):
           return False
       if closeout.is_compiled_projection(rel, repo_root):
           return False
       return not _is_along_state(rel)
   ```
   Add `from .. import closeout` at the top only if `closeout` is not already importable
   there (turnstate imports it; check for import cycles by running the step's tests).
   Do NOT change the PreToolUse whitelist branch: hand edits of projections stay governed
   by the existing projection-protection rules.

3. Tests - new class `TestCompiledProjections` in `tests/test_gates_traceability.py`:
   - temp dir; write `packages/pkg/AGENTS.md`, `packages/pkg/docs/topic--a.md`,
     `packages/pkg/docs/INDEX.md` with front matter `protocol: along` / `type: index`:
     `closeout.is_compiled_projection("packages/pkg/docs/INDEX.md", root)` is True;
     `predicates._is_plan_governed(...)` is False.
   - same file without the front matter -> True governed (False projection).
   - `packages/pkg/llms.txt` with `packages/pkg/docs/` present -> projection;
     `tools/llms.txt` without a sibling `docs/` -> not a projection.
   - `packages/pkg/src/a.py` -> governed.
   Run: `python .along/scripts/test.py -q tests/test_gates_traceability.py`.

## Step 2 - kb-sync does not rewrite unchanged indexes (REQ-2)

File: `scripts/along_kb_sync.py`.

1. `_kb_generate_index`: keep building `index_fm` and `index_body_lines` exactly as now.
   Replace the write block at the end (the `if not check_only and os.path.exists(docs_dir):`
   block) with this logic:
   - Read the existing file text once (`existing = None` when missing/unreadable). Reuse
     the read already done at the top of the function: store `cur_content` and `cur_fm`
     in variables that survive the `try` (initialize both to `None` before it).
   - `body = "\n".join(index_body_lines)`.
   - If `cur_fm` has an `updated` value: build
     `candidate = dump_frontmatter(dict(index_fm, updated=str(cur_fm["updated"])), body)`.
     If `candidate == cur_content`: print `"   -> docs/INDEX.md unchanged."` and return
     `index_path` without writing.
   - Otherwise write `dump_frontmatter(index_fm, body)` exactly as today (same `open(...,
     newline="\n")` call, same print).
   Note: the `dict(...)` copy keeps key order, so the dumped front matter only differs in
   the `updated` value.
2. `sync_decisions_to_docs`: for each ADR copy and for `INDEX.md`, read the destination
   if it exists and skip `textio.write_text` when the new content equals it. Print the
   `Synchronized docs/decisions/` line only when at least one file was written.
3. Do not change `sync_llms_txt` / `sync_llms_full_txt` (already idempotent) and do not
   change topic-article handling (it only writes when fields are missing).
4. Tests - in `tests/test_kb_sync.py` add `TestIdempotentSync`:
   - Fixture: temp dir with `AGENTS.md`, `docs/topic--a.md` (valid Along front matter),
     `.along/DECISIONS/ADR-2026-01-01--x.md` (copy the front-matter shape used by other
     tests in that file), and a package `packages/pkg/` with `AGENTS.md`, `docs/topic--b.md`.
   - Run `sync_kb(root)` once (use the same entry point the existing tests in the file
     use). Record `{path: bytes}` of every file under the temp dir.
   - Patch the date to the next day (`mock.patch("along_kb_sync.datetime")` with
     `now.return_value = datetime(2099, 1, 2)` and `strftime` working: simplest is
     `wraps=datetime` plus `now` override - follow how other tests in the file patch time;
     if none do, patch `datetime.now` via a small subclass) and run `sync_kb(root)` again.
   - Assert the byte map is identical (no file changed, root and package `docs/INDEX.md`,
     `docs/decisions/*` and `llms*.txt` included).
   Run: `python .along/scripts/test.py -q tests/test_kb_sync.py`.

## Step 3 - wrap commits what its sync changed (REQ-3)

Files: `scripts/alongkit/lifecycle.py`.

1. In `execute_wrap`, around the kb-sync subprocess (~1497): before `proc.run_python(...)`
   take `top = closeout.git_top(repo_root)`; when `top`:
   `pre = closeout.content_fingerprint(top, sorted(closeout.git_changes(repo_root)))`.
   After the subprocess:
   `post = closeout.content_fingerprint(top, sorted(set(closeout.git_changes(repo_root)) | set(pre)))`
   and
   `kb_written = [p for p, blob in post.items() if pre.get(p, "absent") != blob and closeout.is_compiled_projection(p, top)]`.
   (`git_changes` returns top-relative paths, so `is_compiled_projection(p, top)` is the
   right base.) When there is no git top, `kb_written = []`.
   Note for deleted files: `is_compiled_projection` returns False for a missing file, so a
   deleted index is not auto-committed; that is intended.
2. Add a keyword parameter `extra_projections: Optional[List[str]] = None` to
   `_auto_commit_wrapped_work` and pass `extra_projections=kb_written` from `execute_wrap`.
   Inside, after the `dirty_projections` loop:
   `for p in extra_projections or []: pk = closeout.path_key(p); if pk in changed_keys: dirty_projections.append(changed_keys[pk])`.
   The existing `dict.fromkeys` dedup handles overlaps.
3. In the `no_commit` path (`_warn_uncommitted_work`) do nothing new: `run_closeout`
   already commits docs byproducts through `_is_wrap_byproduct`.
4. Tests - in `tests/test_parallel_closeout.py` (it already builds git repos with
   `_co_git`), add `TestWrapCommitsPackageIndex`:
   - git repo fixture with an in-progress issue (copy the setup of an existing
     `execute_wrap` test in that file or `tests/test_wrap_engine_writes.py`), plus
     `packages/pkg/AGENTS.md`, `packages/pkg/docs/topic--b.md`, committed.
   - Change `packages/pkg/docs/topic--b.md` title so the package index content changes.
     Attribute that edit to the issue the same way the reused test attributes edits.
   - Run `lifecycle.execute_wrap(...)` (same args as the reused test, commit enabled).
   - Assert `closeout.git_changes(root)` is empty afterwards (clean tree), and
     `packages/pkg/docs/INDEX.md` is in the last commit (`git show --name-only HEAD`).
   Run: `python .along/scripts/test.py -q tests/test_parallel_closeout.py tests/test_wrap_engine_writes.py tests/test_lifecycle_wrap.py`.

## Step 4 - Stop plan gate counts only this session's writes (REQ-4)

Files: `scripts/alongkit/hooks/predicates.py`.

Trace fields (all in the per-session activity trace, `load_activity_trace(repo_root, key)`):
- `turn_writes`: list of repo-relative POSIX paths this session wrote during the turn.
- `shell_pending`: `{"snap": <turnstate.snapshot dict>}` or absent.

1. `record_tool_activity`, `USER_PROMPT_SUBMIT` branch: next to `trace["turn_baseline"] = ...`
   set `trace["turn_writes"] = []` and `trace.pop("shell_pending", None)`.
2. File-tool branch (POST_TOOL_USE, after `rel` is computed): when `rel` is truthy,
   append `repo.normalize_posix(rel)` to `trace["turn_writes"]` (create the list if
   missing, skip duplicates, cap at the last 500 entries) and make sure the trace is saved
   on every path through that branch (today it is saved only for source/doc edits: add a
   `save_activity_trace(repo_root, trace, key)` at the end of the branch).
3. Shell branch: restructure the start of the `elif event.tool_name in ("run_command", ...)`
   branch so that, BEFORE the existing `if not cmd or event.event_type != PRE_TOOL_USE: return`:
   - on `PRE_TOOL_USE`: `trace["shell_pending"] = {"snap": turnstate.snapshot(repo_root) or {}}`
     and save the trace (then continue into the existing test-detection code, which loads
     nothing new and saves the same `trace` dict - keep one dict, do not reload).
   - on `POST_TOOL_USE`: `pending = trace.pop("shell_pending", None)`; when it is a dict,
     `for p in turnstate.changed_since(repo_root, pending.get("snap") or {})` add `p` to
     `turn_writes` (same dedup/cap); save the trace; `return None`.
   Import `turnstate` locally (`from . import turnstate`) as the existing code does.
4. `check_mutation_authorization`, Stop branch, after
   `turn_changes = turnstate.changed_since(repo_root, baseline)` and after the existing
   `_unlogged_plan_approvals(turn_changes, ...)` check (leave that check on the FULL
   `turn_changes`, it is a security check):
   ```python
   writes = trace.get("turn_writes")
   if isinstance(writes, list):
       mine = set(writes)
       pending = trace.get("shell_pending")
       if isinstance(pending, dict):  # a shell command without PostToolUse: count it
           mine.update(turnstate.changed_since(repo_root, pending.get("snap") or {}))
       mine_keys = {closeout.path_key(p) for p in mine}
       foreign = [p for p in turn_changes if closeout.path_key(p) not in mine_keys]
       turn_changes = [p for p in turn_changes if closeout.path_key(p) in mine_keys]
       if foreign:
           session.trace_event(repo_root, trace_key,
                               f"stop: {len(foreign)} path(s) changed this turn outside this "
                               "session's tool calls were not counted", collapse=True)
   ```
   Then keep `changed = [p for p in turn_changes if _is_plan_governed(p, repo_root)]`.
   When `turn_writes` is missing (old trace, runtime without the new fields) behavior is
   unchanged (whole-tree diff).
   Path base check: `turnstate.changed_since` returns paths relative to
   `realpath(repo_root)`; `_repo_relative` returns paths relative to `repo_root`. Compare
   with `closeout.path_key` (case-insensitive on Windows). If the test on Windows shows a
   mismatch from a short path (`ADMIN~1`), normalize both sides with
   `repo.safe_relpath(os.path.realpath(os.path.join(repo_root, p)), os.path.realpath(repo_root))`
   before keying.
5. Known limit (document it in Step 7, do not try to fix): another session writing a file
   WHILE one of this session's shell commands runs is still attributed to this session.
6. Tests - in `tests/test_gates_traceability.py` add `TestStopCountsSessionWrites`. Use
   `subprocess.run(["git", "init", "-q"], cwd=root)` plus an initial commit (turnstate
   needs git). Use `check_mutation_authorization(event, root, options={"enforce_unbound": True})`
   and drive `record_tool_activity` directly with `HookEvent` objects (pattern from
   `tests/test_anti_silent_fallback.py`: `HookEvent(event_type=..., tool_name=...,
   tool_args=..., workspace_root=root, runtime="claude", conversation_id="sess-1")`).
   Patch env as `tests/test_gate_friction.py` does (`CLEAN_ENV`, `ALONG_SESSION_ID`).
   - Case "foreign write": USER_PROMPT_SUBMIT for `sess-1`; then write `src/other.py`
     directly with `open()` (simulating session 2); Stop for `sess-1` -> `None`.
   - Case "own file-tool write": USER_PROMPT_SUBMIT; create `src/mine.py` on disk, then
     POST_TOOL_USE `write_to_file` with `TargetFile` = that path; Stop -> reason containing
     `require-plan-approval` and `src/mine.py`.
   - Case "own shell write": USER_PROMPT_SUBMIT; PRE_TOOL_USE `run_command`
     (`CommandLine: "echo x > src/sh.py"`); write `src/sh.py` with `open()`; POST_TOOL_USE
     `run_command`; Stop -> denial mentions `src/sh.py`.
   - Case "legacy trace": delete `turn_writes` from the trace file; a foreign write ->
     denial (old behavior kept).
   Run: `python .along/scripts/test.py -q tests/test_gates_traceability.py tests/test_inquiry_gate.py tests/test_anti_silent_fallback.py tests/test_hook_activation.py`.

## Step 5 - Stop denials are recorded and ackable, bound or not (REQ-5)

Files: `scripts/alongkit/hooks/predicates.py`, `scripts/alongkit/commands/gates.py`.

Design: Stop denials live in the per-session activity trace (it survives `wrap`, which
purges the blackboard). When the session is still bound, a `deny` ledger event is also
written for traceability. The plan gate stops re-denying the same path set once that
denial is acked.

1. `predicates.py` - add near `record_gate_denial`:
   ```python
   #: Stop denials kept per agent session in the activity trace. REQ-5
   STOP_DENIALS_MAX: int = 50

   def stop_denial_id(gate: str, key: Optional[str], paths: List[str], turn_start: Optional[str]) -> str:
       """Deterministic id of a Stop denial: the gate can name it in its message."""
       import hashlib
       seed = "|".join([gate, key or "", turn_start or "", *sorted(paths)])
       return "d-" + hashlib.sha256(seed.encode("utf-8")).hexdigest()[:6]
   ```
2. Plan gate Stop message (`check_mutation_authorization`, the `if event.event_type == STOP:`
   return near the end): compute
   `did = stop_denial_id("require_plan_approval", key, changed, session.last_user_prompt_at(repo_root, key))`
   and, before building the message, if the trace has a `stop_denials` entry with that id and
   `state == "acked"`, return `None` (the user was told; do not loop). Otherwise append to
   the message: `f" Or tell the user what is left and why, then 'along gates ack {did} --note \"...\"'."`.
   Hand `did` and `changed` to the recorder through the trace (do not mutate the event,
   do not parse the reason text): right here save
   `trace["last_stop_denial"] = {"id": did, "gate": "require_plan_approval", "paths": changed}`
   (load with `load_activity_trace(repo_root, key)`, save with `save_activity_trace`).
3. `record_gate_denial`: after the existing PRE_TOOL_USE branch add
   ```python
   elif event.event_type == HookEventType.STOP:
       _record_stop_denial(repo_root, key, gate, first)
   ```
   and implement `_record_stop_denial(repo_root, key, gate, reason)`:
   - `trace = load_activity_trace(repo_root, key)`; `last = trace.get("last_stop_denial")`.
   - If `last` is a dict and `last.get("gate") == gate`: `did = last["id"]`,
     `target = ", ".join(last.get("paths") or [])`. Else (another Stop gate, e.g.
     `test_before_stop`): `did = stop_denial_id(gate, key, [reason], session.last_user_prompt_at(repo_root, key))`,
     `target = None`.
   - If an entry with `id == did` already exists in `trace["stop_denials"]`: return
     (repeats collapse).
   - `ctx, slug = session.bound_blackboard(repo_root, key)`.
   - Entry: `{"id": did, "gate": gate, "tool": "Stop", "target": target, "reason": reason,
     "ts": session._utc_now_iso(), "state": "open", "ctx": ctx, "slug": slug}`; sanitize
     `target` and `reason` with `_get_audit_redactor().sanitize_text` like
     `_record_denial_event` does.
   - Append, cap to `STOP_DENIALS_MAX`, `trace.pop("last_stop_denial", None)`, save.
   - When `slug`: `session.append_event(ctx, slug, key, "deny", extra={"id": did, "gate": gate,
     "tool": "Stop", "target": target, "reason": reason, "procedural": True})`.
     `procedural: True` keeps `check_unresolved_denials` from holding the turn a second
     time for the same thing (the plan gate holds it already).
4. Add two helpers in `predicates.py`:
   - `stop_denials(repo_root, key) -> List[Dict[str, Any]]`: the trace list (both the
     `repo_root` trace and the `session.binding_root(repo_root)` trace, as
     `session_denials` does), each item shaped like `session.denial_status` items:
     `state` mapped to `session.DENIAL_OPEN` / `session.DENIAL_ACKED`, plus `verified`
     (`None`), `note`, `via` (`None`).
   - `ack_stop_denials(repo_root, key, ids, note) -> List[Dict[str, Any]]`: set
     `state = "acked"`, `note`, `ack_ts` on matching open entries, save, and when the entry
     has `ctx`/`slug` and that blackboard still exists (`session.load_state(ctx, slug)`),
     also `session.append_event(ctx, slug, key, "ack", extra={"id": id, "note": note})`.
     Returns the acked entries.
5. `commands/gates.py` `_handle_denials`:
   - `denials` subcommand: when `_denials_target` yields no `(ctx, slug)` and `--slug` was
     not given, list `predicates.stop_denials(repo_root, key)` instead of erroring; error
     only when that list is empty too (keep the current error text). When bound, print the
     ledger items as now and then the stop denials whose id is not already among them.
     JSON mode: one combined list.
   - `ack` subcommand (no `--slug`): build `items` as now, then add
     `predicates.stop_denials(repo_root, key)` entries not already present (by id). The
     "not bound" error fires only when both are empty. In the ack loop, for an item whose
     id is a stop denial, call `predicates.ack_stop_denials(...)` instead of
     `session.append_event(...)` (the helper writes the ledger ack itself when possible).
   - Keep output strings and exit codes otherwise unchanged.
6. Tests - in `tests/test_anti_silent_fallback.py` add `TestStopDenialAck` (reuse the
   `_BoundSession` fixture and its `_stop()` / `_engine()` helpers; the engine must run
   `require_plan_approval` - build a `HookEngine` with the real catalogue like other tests
   there, or call `record_gate_denial` directly with a Stop event after setting
   `trace["last_stop_denial"]`):
   - bound: Stop denial -> `predicates.stop_denials(root, KEY)` has one open entry and the
     ledger has a `deny` with that id; `along gates denials` (call
     `gates._handle_denials(root, "denials", [])` with stdout captured) lists the id;
     `_handle_denials(root, "ack", [id, "--note", "told the user"])` returns 0; the entry
     is acked.
   - unbound: remove the binding (`session.unbind_slug(root, SLUG)` and purge the
     blackboard dir) after the denial; `denials` and `ack` still work and return 0.
   - repeated identical Stop denial in the same turn -> still one entry.
   - after ack, `check_mutation_authorization` Stop for the same paths returns `None`.
   Run: `python .along/scripts/test.py -q tests/test_anti_silent_fallback.py tests/test_subagent_denials.py tests/test_gates_traceability.py`.

## Step 6A - Remove the 1-line exemption text (REQ-6, D1 = A)

1. `skills/along-init/protocol.md:16`: delete the sentence
   `1-line typo/comment edits are exempt.` (keep `Questions get read-only answers;` ->
   make it `Questions get read-only answers.`).
2. `skills/along-init/protocol-reference.md:52`: change the line to
   `- **Exemptions**: Read-only Q&A does not require an issue. Every repository edit,
   including a 1-line typo or comment fix, needs an in-progress issue and an approved plan.`
3. Regenerate the rendered copies with the engine (never hand-edit them): run
   `along init --help` to find the refresh mode and run it in this repo (it rewrites the
   managed block in `AGENTS.md` and `.along/PROTOCOL.md`). Check `git diff --stat`: only
   those two files plus the two skill files may change. If other files change, stop and
   report.
4. Add a test in `tests/test_gates_traceability.py`, `TestNoMicroEditExemption`:
   `skills/along-init/protocol.md` and `skills/along-init/protocol-reference.md` (read
   from `REPO_ROOT`) contain no `exempt` near `1-line` (assert
   `"1-line typo/comment edits are exempt" not in text` and
   `"1-line micro-edits" not in text`), and a one-line comment Edit to `src/a.py` in an
   unbound temp repo with `enforce_unbound` is denied by `check_mutation_authorization`.
5. Run `python .along/scripts/test.py -q tests/test_context_budget.py tests/test_skills_and_scripts.py tests/test_gates_traceability.py`
   (protocol budget tests read these files).

## Step 6B - Implement the 1-line exemption (REQ-6, only if D1 = B)

Only for PreToolUse of an Edit-style tool (`tool_args` has `old_string` and `new_string`,
no `replace_all: true`):
1. `predicates.py`: add `_is_micro_comment_edit(event, rel) -> bool`, true when all hold:
   - `rel` is not under `.along/`, not a test file (`verify.is_test_inert_path` is not the
     right check; use: no path part equals `tests`/`test` and the name does not start with
     `test_`), not a lifecycle script;
   - `old_string.splitlines()` and `new_string.splitlines()` have the same length, and
     exactly one line index differs;
   - both versions of that line, stripped, are empty or start with a comment marker for the
     file type: `#` for `.py .sh .ps1 .yaml .yml .toml`, `//` or `*` or `/*` for
     `.ts .tsx .js .cs .rs .java .go`, `<!--` for `.md .html`; any other extension -> False.
2. In `check_active_issue` and in the PreToolUse branch of `check_mutation_authorization`,
   return `None` when `_is_micro_comment_edit(...)`, and write an audit entry
   (`record_audit_entry(repo_root, event, GateResult(decision=GateDecision.ALLOW,
   reason="micro-edit exemption", gate_name="<gate>"), "audit")`).
3. The Stop branch is unaffected (shell work never qualifies). Note: a file-tool micro-edit
   still shows up at Stop via `turn_writes` -> also skip at Stop any path whose only writes
   this turn were exempt micro-edits: keep a `trace["micro_edits"]` list (added in
   `record_tool_activity` POST_TOOL_USE when `_is_micro_comment_edit` is true) and drop
   those paths from `changed` when they are not also in a non-exempt write.
4. Leave the protocol text as is. Tests in `tests/test_gate_friction.py`
   (`TestMicroEditExemption`): comment-only single-line edit allowed by both gates;
   code-line change denied; two-line change denied; edit in `tests/` denied; edit with
   `replace_all` denied.

## Step 7 - Docs

1. `/along-kb-search require-plan-approval` and update, in
   `docs/topic--runtime-hooks-and-gates.md` (and `docs/topic--declarative-gates-and-traceability.md`
   where it describes Stop denials):
   - Stop branch counts only paths this session wrote (file tools on PostToolUse; shell
     commands by a pre/post snapshot); others are noted in the trace, not denied; known
     limit from Step 4.5.
   - Compiled projections (`docs/INDEX.md`, `docs/decisions/INDEX.md`, `llms*.txt`) at any
     level are not plan-governed.
   - Stop denials: recorded in the session's activity trace (plus the ledger when bound),
     listed by `along gates denials`, settled by `along gates ack <id> --note`, also after
     `wrap`.
2. `docs/topic--cli-reference.md`: `along gates denials` / `ack` work without a binding
   for Stop denials of this session.
3. `docs/topic--troubleshooting.md`: add an entry for the
   `PLAN_REQUIRED ... this turn changed packages/.../docs/INDEX.md` symptom and its fix.
4. Keep the article front matter `updated:` current, relative links only, fenced code with
   a language.

## Step 8 - Verify and close

1. `python .along/scripts/test.py -q` (full suite) - must pass after the last edit.
2. `along sanitize` (no findings), `along lint` if available.
3. Manual repro in a scratch git repo (temp dir, not this repo): `along init`, add
   `packages/pkg/AGENTS.md` + `packages/pkg/docs/topic--x.md`, commit; create an issue,
   `along start`, approve a trivial plan, make one edit, `along wrap <slug> --summary "..."
   --no-decisions`; then `git status --porcelain` must be empty and running
   `along kb-sync` again must leave it empty.
4. Record an ADR at wrap for the attribution change (Stop gate judges session-attributed
   writes; Stop denials live in the session trace): use `/along-decision-sync`, then
   `along wrap stop-gate-false-positives --summary "..." --decisions <ADR-id>`.
5. Tick the acceptance criteria in the issue file.

## Acceptance mapping
| Criterion | Step / test |
| --- | --- |
| wrap with package index ends clean, no Stop denial | Step 1 + Step 3 `TestWrapCommitsPackageIndex` |
| kb-sync twice -> no changes | Step 2 `TestIdempotentSync` |
| second session's file does not trigger Stop gate | Step 4 `TestStopCountsSessionWrites` |
| Stop denial listed and ackable, bound or not | Step 5 `TestStopDenialAck` |
| 1-line exemption: gate and text agree | Step 6A or 6B tests |
| full suite passes | Step 8 |
