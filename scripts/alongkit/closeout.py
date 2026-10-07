"""
closeout.py - Readiness of parallel work for one-step closeout.

[feat--parallel-session-closeout] REQ-3, REQ-4. Pure functions over the session bindings, the
per-issue event ledgers (`.along/.session/<slug>/events.jsonl`), the blackboards, the issue
files and one `git status`. `along session list` prints the result; `along session close`
acts on it.

Paths are POSIX, relative to the git top, so ledger attribution and `git status` compare
directly. On Windows the comparison ignores case.
"""

from __future__ import annotations
if __name__ == "__main__":
    import os
    raise SystemExit(
        f"{os.path.basename(__file__)} is a library module, not a command.\n"
        "Run: python .along/scripts/test.py"
    )

import os
import re
import sys
from typing import Any, Dict, List, Optional, Tuple

from . import entities, frontmatter, proc, repo, session, textio

#: Merge-like operations during which nothing may be closed.
_OPERATION_MARKERS: Tuple[Tuple[str, str], ...] = (
    ("MERGE_HEAD", "merge"), ("REBASE_HEAD", "rebase"), ("rebase-merge", "rebase"),
    ("rebase-apply", "rebase"), ("CHERRY_PICK_HEAD", "cherry-pick"), ("REVERT_HEAD", "revert"),
)
_UNMERGED_CODES = frozenset({"DD", "AU", "UD", "UA", "DU", "AA", "UU"})
_MARKER_LINE = re.compile(r"^(<{7}( |$)|={7}$|>{7}( |$))")
_MARKER_SCAN_LIMIT = 2_000_000


def _git_text(cwd: str, *args: str) -> Optional[str]:
    result = proc.run_capture(["git", *args], cwd=cwd, check=False, trip_on_anomaly=False)
    return result.stdout if result.ok else None


def git_top(repo_root: str) -> Optional[str]:
    root = os.path.realpath(os.path.abspath(repo_root))
    out = _git_text(root, "rev-parse", "--show-toplevel")
    return os.path.realpath(out.strip()) if out and out.strip() else None


def path_key(path: str) -> str:
    """Comparison key of a top-relative path (case-insensitive on Windows)."""
    path = repo.normalize_posix(path).lstrip("/")
    return path.lower() if sys.platform == "win32" else path


def git_changes(repo_root: str) -> Dict[str, str]:
    """{top-relative path: two-letter status} of every changed, untracked or deleted path
    (`git status --porcelain -z -uall`); a rename reports both its old and new path."""
    real_root = os.path.realpath(os.path.abspath(repo_root))
    top = git_top(real_root)
    out = _git_text(top or real_root, "status", "--porcelain", "-z", "-uall") if top else None
    changes: Dict[str, str] = {}
    if not out:
        return changes
    entries = out.split("\0")
    i = 0
    while i < len(entries):
        entry = entries[i]
        i += 1
        if len(entry) < 4:
            continue
        code, path = entry[:2], entry[3:]
        changes[repo.normalize_posix(path)] = code
        if code[0] in "RC" and i < len(entries):
            changes[repo.normalize_posix(entries[i])] = "D "
            i += 1
    return changes


def operation_in_progress(repo_root: str) -> Optional[str]:
    """'merge', 'rebase', 'cherry-pick' or 'revert' when one is in progress, else None."""
    real_root = os.path.realpath(os.path.abspath(repo_root))
    top = git_top(real_root) or real_root
    for marker, name in _OPERATION_MARKERS:
        path = _git_text(real_root, "rev-parse", "--git-path", marker)
        if path and path.strip():
            candidate = path.strip()
            if not os.path.isabs(candidate):
                candidate = os.path.join(top, candidate)
            if os.path.exists(candidate):
                return name
    return None


def conflicted_paths(top: str, changes: Dict[str, str]) -> List[str]:
    """Unmerged paths and changed text files that carry conflict markers."""
    real_top = os.path.realpath(os.path.abspath(top))
    found: List[str] = []
    for path, code in sorted(changes.items()):
        if code in _UNMERGED_CODES:
            found.append(path)
            continue
        full = os.path.join(real_top, *path.split("/"))
        try:
            if not os.path.isfile(full) or os.path.getsize(full) > _MARKER_SCAN_LIMIT:
                continue
            text = textio.read_text(full, strict=False)
        except (OSError, UnicodeDecodeError):
            continue
        in_fence = False
        for line in text.splitlines():
            if line.lstrip().startswith(("```", "~~~")):
                in_fence = not in_fence
            if not in_fence and _MARKER_LINE.match(line):
                found.append(path)
                break
    return found


def _contexts(repo_root: str) -> List[str]:
    """The repository context and every `.along/` context a binding points at."""
    real_root = os.path.realpath(os.path.abspath(repo_root))
    roots = [real_root]
    for binding in session.list_bindings(real_root):
        ctx = session.binding_context(real_root, binding)
        if ctx:
            real_ctx = os.path.realpath(os.path.abspath(ctx))
            if os.path.isdir(real_ctx) and all(not session._same_dir(real_ctx, r) for r in roots):
                roots.append(real_ctx)
    return roots


def _blackboard_slugs(ctx: str) -> List[str]:
    s_root = os.path.join(repo.state_dir(ctx), ".session")
    if not os.path.isdir(s_root):
        return []
    return sorted(e.name for e in os.scandir(s_root)
                  if e.is_dir() and not e.name.startswith(".") and e.name != session.BINDINGS_DIRNAME)


def _issue_body(issue: Dict[str, Any]) -> str:
    try:
        content = textio.read_text(issue["file_path"], strict=False)
    except (OSError, UnicodeDecodeError, KeyError):
        return ""
    block = frontmatter.split(content)
    return block.body if block else content


def _to_top(path: str, prefix: str) -> str:
    return path if prefix in ("", ".") else f"{prefix}/{path}"


def closeout_status(repo_root: str) -> Dict[str, Any]:
    """Readiness of every in-progress issue, every bound issue and every blackboard.

    Returns {"repository": {...}, "items": [...]}. An item: key, slug, context, status,
    sessions (key, last event), files {path: {path_kind, edits, last, shared_with}},
    changed_files (attributed and still changed), last_edit, last_test {ts, ok},
    criteria [ticked, total], plan_recorded, ledger_errors, verdict ('ready' | 'blocked'),
    reasons. The repository part lists changed, unattributed and staged paths, an operation
    in progress and conflicted paths.
    """
    real_root = os.path.realpath(os.path.abspath(repo_root))
    top = git_top(real_root) or real_root
    changes = git_changes(real_root)
    changed_keys = {path_key(p): p for p in changes}
    b_root = os.path.realpath(os.path.abspath(session.binding_root(real_root)))
    prefix = repo.normalize_posix(os.path.relpath(b_root, top))
    prefix = "" if prefix in ("", ".") else prefix
    bindings = session.list_bindings(real_root)

    items: List[Dict[str, Any]] = []
    for ctx in _contexts(real_root):
        slugs = {i["slug"] for i in entities.scan_issues(ctx) if i.get("status") == "in-progress"}
        slugs |= {str(b["slug"]) for b in bindings
                  if b.get("slug") and session._same_dir(session.binding_context(real_root, b) or real_root, ctx)}
        slugs |= set(_blackboard_slugs(ctx))
        for slug in sorted(slugs):
            items.append(_item(ctx, slug, bindings, prefix, changed_keys))

    # Shared files: attributed to more than one issue.
    owners: Dict[str, List[str]] = {}
    for item in items:
        for path in item["files"]:
            owners.setdefault(path_key(path), []).append(item["key"])
    for item in items:
        for path, info in item["files"].items():
            info["shared_with"] = [k for k in owners.get(path_key(path), []) if k != item["key"]]

    attributed = set(owners)
    staged = sorted(p for p, code in changes.items() if code[0] not in " ?")
    repository = {
        "top": repo.normalize_posix(top),
        "changed": sorted(changes),
        "unattributed": sorted(p for p in changes if path_key(p) not in attributed),
        "staged": staged,
        "operation": operation_in_progress(real_root),
        "conflicts": conflicted_paths(top, changes),
    }
    return {"repository": repository, "items": items}


def _item(ctx: str, slug: str, bindings: List[Dict[str, Any]], prefix: str,
          changed_keys: Dict[str, str]) -> Dict[str, Any]:
    issue = entities.find_issue_by_slug(ctx, slug)
    has_blackboard = session.load_state(ctx, slug) is not None
    events = session.load_events(ctx, slug) if has_blackboard else []
    files = {_to_top(p, prefix): info for p, info in session.attributed_files(ctx, slug).items()} \
        if has_blackboard else {}
    last_seen: Dict[str, str] = {}
    for event in events:
        if event.get("session"):
            last_seen[str(event["session"])] = str(event.get("ts"))
    sessions = [{"key": str(b.get("key")), "last_event": last_seen.get(str(b.get("key")))}
                for b in bindings if b.get("slug") == slug]
    sessions += [{"key": k, "last_event": ts, "unbound": True}
                 for k, ts in last_seen.items() if k not in {s["key"] for s in sessions}]
    # Ledger order (append order) decides "after"; timestamps have one-second resolution.
    edit_at = max((n for n, e in enumerate(events) if e.get("kind") == "edit"), default=-1)
    test_at = max((n for n, e in enumerate(events) if e.get("kind") == "test"), default=-1)
    last_edit = str(events[edit_at]["ts"]) if edit_at >= 0 else None
    last_test = {"ts": str(events[test_at]["ts"]), "ok": bool(events[test_at].get("ok"))} if test_at >= 0 else None
    criteria = entities.acceptance_criteria(_issue_body(issue)) if issue else (0, 0)
    plan = has_blackboard and session.plan_recorded(ctx, slug)
    ledger_error = session.ledger_errors(ctx).get(slug)

    reasons: List[str] = []
    if not issue:
        reasons.append("issue missing (archive the blackboard: along scratch purge)")
    elif issue.get("status") in entities.CLOSED_ISSUE_STATUSES:
        reasons.append(f"issue is {issue.get('status')} (archive the blackboard: along scratch purge)")
    elif issue.get("status") != "in-progress":
        reasons.append(f"issue is {issue.get('status')}, not in progress (along start {slug} to resume, "
                       "or along scratch purge)")
    if not has_blackboard:
        reasons.append("no blackboard: nothing was recorded (along start)")
    elif not plan:
        reasons.append("no plan recorded")
    if edit_at > test_at:
        reasons.append("no test run after the last edit")
    elif last_test and not last_test["ok"]:
        reasons.append("last test run failed")
    if criteria[1] and criteria[0] < criteria[1]:
        reasons.append(f"acceptance criteria {criteria[0]}/{criteria[1]} ticked")
    if ledger_error:
        reasons.append(f"event ledger write failed {ledger_error.get('count')} time(s): attribution incomplete")

    key = entities.canonical_key(issue["type"], issue["slug"]) if issue else slug
    return {
        "key": key, "slug": slug, "context": repo.normalize_posix(ctx), "status": issue.get("status") if issue else None,
        "sessions": sessions, "files": files,
        "changed_files": sorted(changed_keys[path_key(p)] for p in files if path_key(p) in changed_keys),
        "last_edit": last_edit, "last_test": last_test, "criteria": list(criteria),
        "plan_recorded": plan, "ledger_errors": ledger_error,
        "verdict": "blocked" if reasons else "ready", "reasons": reasons,
    }


# ---------------------------------------------------------------------------
# `along session close` [feat--parallel-session-closeout] REQ-5
# ---------------------------------------------------------------------------

RUN_FILENAME: str = ".closeout.json"
RUN_SCHEMA: int = 1
#: Projections a wrap regenerates; they go into the last commit of a closeout.
PROJECTION_FILES: Tuple[str, ...] = (".along/ISSUES.md", ".along/HISTORY.md", "docs/INDEX.md",
                                     "docs/decisions/INDEX.md", "llms.txt", "llms-full.txt")
_COMMIT_TYPES = {"feat": "feat", "bug": "fix", "debt": "refactor", "task": "chore", "docs": "docs"}


def run_file(repo_root: str) -> str:
    real_root = os.path.realpath(os.path.abspath(repo_root))
    return os.path.join(repo.state_dir(real_root), ".session", RUN_FILENAME)


def load_run(repo_root: str) -> Optional[Dict[str, Any]]:
    import json
    path = run_file(repo_root)
    try:
        data = json.loads(textio.read_text(path, strict=False)) if os.path.isfile(path) else None
    except (OSError, UnicodeDecodeError, ValueError):
        return None
    return data if isinstance(data, dict) else None


def _save_run(repo_root: str, run: Dict[str, Any]) -> None:
    import json
    os.makedirs(os.path.dirname(run_file(repo_root)), exist_ok=True)
    textio.write_text(run_file(repo_root), json.dumps(run, indent=2) + "\n", newline="\n")


def plan_closeout(status: Dict[str, Any], selected: List[str]) -> Dict[str, Any]:
    """Commit groups for the selected issue keys, from a `closeout_status` snapshot.

    A changed file attributed only to selected issues goes into the group of exactly those
    issues (one issue: its own commit; several: one combined commit). A file also attributed
    to an issue that is not closed now is held back; unattributed changes are never
    committed. Every selected issue gets its own group (for its entity files), even if empty.
    """
    owners: Dict[str, List[str]] = {}
    for item in status["items"]:
        for path in item["changed_files"]:
            owners.setdefault(path_key(path), []).append(item["key"])
    chosen = set(selected)
    groups: Dict[Tuple[str, ...], List[str]] = {(k,): [] for k in sorted(chosen)}
    held: List[Dict[str, Any]] = []
    for item in status["items"]:
        if item["key"] not in chosen:
            continue
        for path in item["changed_files"]:
            holders = tuple(sorted(set(owners[path_key(path)])))
            if not set(holders) <= chosen:
                held.append({"path": path, "with": [h for h in holders if h not in chosen]})
                continue
            if path not in groups.setdefault(holders, []):
                groups[holders].append(path)
    ordered = sorted(groups.items(), key=lambda kv: (len(kv[0]), kv[0]))
    return {
        "groups": [{"keys": list(keys), "files": sorted(files), "done": False} for keys, files in ordered],
        "held": sorted({h["path"]: h for h in held}.values(), key=lambda h: h["path"]),
        "unattributed": status["repository"]["unattributed"],
    }


def _commit_message(keys: List[str], titles: Dict[str, str], projections: bool = False) -> str:
    refs = " ".join(f"(refs #{entities.parse_key(k)[1]})" for k in keys)
    if projections:
        return f"chore(along): projections after closing out {', '.join(keys)} {refs}"
    if len(keys) == 1:
        itype, _slug = entities.parse_key(keys[0])
        return f"{_COMMIT_TYPES.get(itype or 'task', 'chore')}: {titles.get(keys[0], keys[0])} {refs}"
    return f"chore: changes shared by {', '.join(keys)} {refs}"


def _commit(repo_root: str, top: str, message: str, key: str, files: List[str]) -> int:
    real_root = os.path.realpath(os.path.abspath(repo_root))
    real_top = os.path.realpath(os.path.abspath(top))
    script = repo.resolve_tool_script("along_commit.py", real_root)
    if not script:
        print("[Error] along_commit.py not found.", file=sys.stderr)
        return 1
    paths = [os.path.join(real_top, *p.split("/")) for p in files]
    result = proc.run_capture([sys.executable, script, message, "-i", key, "--paths", *paths],
                              cwd=real_root, check=False, trip_on_anomaly=False)
    print(result.stdout.rstrip())
    if not result.ok:
        print(result.stderr.rstrip(), file=sys.stderr)
    return result.returncode


def content_fingerprint(top: str, paths: List[str]) -> Dict[str, Optional[str]]:
    """{path: blob id} of top-relative paths (None for a missing file), one `git hash-object`."""
    real_top = os.path.realpath(os.path.abspath(top))
    existing = [p for p in paths if os.path.isfile(os.path.join(real_top, *p.split("/")))]
    out: Dict[str, Optional[str]] = {p: None for p in paths}
    if existing:
        ids = (_git_text(real_top, "hash-object", "--", *existing) or "").split()
        if len(ids) == len(existing):
            out.update(dict(zip(existing, ids)))
    return out


def _is_wrap_byproduct(path: str) -> bool:
    """Along state, docs and KB projections: what `along wrap` writes besides the issue."""
    name = path.rsplit("/", 1)[-1]
    return session.path_kind(path) in ("state", "docs") or name in ("llms.txt", "llms-full.txt")


def _entity_files(repo_root: str, top: str, key: str, today: str) -> List[str]:
    """Top-relative paths of an issue's entity files a wrap touched: the issue file at both
    places (the move) and today's session log."""
    from . import lifecycle
    real_root = os.path.realpath(os.path.abspath(repo_root))
    real_top = os.path.realpath(os.path.abspath(top))
    issue = entities.find_issue_by_slug(real_root, key)
    if not issue:
        return []
    name = os.path.basename(issue["file_path"])
    issues_dir = os.path.join(repo.state_dir(real_root), "ISSUES")
    paths = [os.path.join(issues_dir, name), os.path.join(issues_dir, "done", name),
             lifecycle.session_log_path(real_root, issue["slug"], today)]
    return [repo.normalize_posix(os.path.relpath(os.path.realpath(p), real_top)) for p in paths]


def run_closeout(repo_root: str, keys: Optional[List[str]] = None, ready: bool = False,
                 dry_run: bool = False, push: bool = False, session_key: Optional[str] = None) -> int:
    """Close out finished parallel work: tests once, wrap each issue, commit by attribution,
    push once. Idempotent: an interrupted run continues from `.along/.session/.closeout.json`.
    Returns the exit code.
    """
    from . import gates, lifecycle

    real_root = os.path.realpath(os.path.abspath(repo_root))
    top = git_top(real_root)
    if not top:
        print("[Error] along session close needs a git repository.", file=sys.stderr)
        return 2
    key = session_key if session_key is not None else session.current_session_key()
    run = load_run(real_root)
    if run and not dry_run:
        print(f"-> Resuming the closeout started {run.get('created')} for {', '.join(run['keys'])}.")
    else:
        status = closeout_status(real_root)
        rep = status["repository"]
        if rep["operation"]:
            print(f"[Error] A {rep['operation']} is in progress: finish or abort it first.", file=sys.stderr)
            return 2
        if rep["conflicts"]:
            print("[Error] Conflicts in: " + ", ".join(rep["conflicts"]) + ". Resolve them first.", file=sys.stderr)
            return 2
        by_slug = {i["slug"]: i for i in status["items"]}
        by_key = {i["key"]: i for i in status["items"]}
        if ready:
            wanted = [i for i in status["items"] if i["verdict"] == "ready"]
        else:
            wanted = []
            for name in keys or []:
                item = by_key.get(name) or by_slug.get(entities.parse_key(name)[1])
                if not item:
                    print(f"[Error] '{name}' is not in progress, bound or on a blackboard here.", file=sys.stderr)
                    return 2
                wanted.append(item)
        not_ready = [i for i in wanted if i["verdict"] != "ready"]
        for item in not_ready:
            print(f"-> Not closing {item['key']} (left untouched): {'; '.join(item['reasons'])}")
        chosen = [i for i in wanted if i["verdict"] == "ready"]
        for item in status["items"]:
            if ready and item["verdict"] != "ready":
                print(f"-> Not ready, left untouched: {item['key']}: {'; '.join(item['reasons'])}")
        if not chosen:
            print("[Error] No ready issue to close out. See 'along session list'.", file=sys.stderr)
            return 1
        if rep["staged"]:
            print("[Error] Files are already staged (" + ", ".join(rep["staged"][:5])
                  + "): a closeout commits by attribution only. Unstage them first (git restore --staged).",
                  file=sys.stderr)
            return 2
        plan = plan_closeout(status, [i["key"] for i in chosen])
        print("-> Closeout plan:")
        for group in plan["groups"]:
            print(f"   commit [{', '.join(group['keys'])}]: {len(group['files'])} attributed file(s)"
                  + (" + issue file and session log" if len(group["keys"]) == 1 else ""))
        print("   commit [projections]: " + ", ".join(PROJECTION_FILES))
        for held in plan["held"]:
            print(f"   held back: {held['path']} (also attributed to {', '.join(held['with'])})")
        for path in plan["unattributed"]:
            print(f"   not committed (unattributed): {path}")
        if dry_run:
            return 0
        approved = set(session.closeout_approved(real_root, key))
        missing = [i["slug"] for i in chosen if i["slug"] not in approved]
        if missing:
            print(f"[Error] Closeout not approved for: {', '.join(missing)}. After the user's explicit yes, run "
                  f"'along plan approve --closeout {' '.join(missing)}' in this session.", file=sys.stderr)
            return 2
        titles = {}
        for item in chosen:
            issue = entities.find_issue_by_slug(real_root, item["slug"]) or {}
            titles[item["key"]] = str((issue.get("frontmatter") or {}).get("title") or item["slug"])
        run = {"schema": RUN_SCHEMA, "created": session._utc_now_iso(), "session": key,
               "keys": [i["key"] for i in chosen], "titles": titles, "groups": plan["groups"],
               "tested": False, "wrapped": [], "entity_files": {}, "projections_done": False,
               "pushed": False, "today": entities.today_iso()}
        _save_run(real_root, run)

    # Tests once for the whole closeout, before anything is wrapped.
    if not run["tested"]:
        if not gates.run_repository_tests(real_root, "Closeout Quality Gate"):
            print("[Error] Tests failed: nothing was wrapped or committed. Fix them and re-run "
                  "'along session close' (it resumes).", file=sys.stderr)
            return 1
        run["tested"] = True
        _save_run(real_root, run)

    # Fingerprint before the first wrap: what the wraps change is told apart from the work.
    if "pre_wrap" not in run:
        run["pre_wrap"] = content_fingerprint(top, sorted(git_changes(real_root)))
        _save_run(real_root, run)

    # Wrap each issue: archive with attribution, issue done, session log, HISTORY.
    for ikey in run["keys"]:
        if ikey in run["wrapped"]:
            continue
        issue = entities.find_issue_by_slug(real_root, ikey)
        if issue and issue.get("status") not in entities.CLOSED_ISSUE_STATUSES:
            code = lifecycle.execute_wrap(real_root, ikey, no_verify=True, decisions=[],
                                          summary=f"Closed out ({run['titles'].get(ikey, ikey)})")
            if code != 0:
                _save_run(real_root, run)
                print(f"[Error] Wrap of {ikey} failed; re-run 'along session close' to continue.", file=sys.stderr)
                return code
        run["wrapped"].append(ikey)
        run["entity_files"][ikey] = _entity_files(real_root, top, ikey, run["today"])
        _save_run(real_root, run)

    # What the wraps changed (KB provenance, indexes, logs). When that is all Along state,
    # docs and projections, the green run carries over to the wrapped tree; anything else
    # (a parallel edit during the closeout) makes the commits run the tests again.
    if "byproducts" not in run:
        pre = run["pre_wrap"]
        post = content_fingerprint(top, sorted(set(git_changes(real_root)) | set(pre)))
        changed = sorted(p for p, blob in post.items() if pre.get(p, "absent") != blob)
        entity = {path_key(p) for files in run["entity_files"].values() for p in files}
        run["byproducts"] = [p for p in changed if path_key(p) not in entity]
        if all(_is_wrap_byproduct(p) for p in run["byproducts"]):
            from . import testruns
            testruns.record_run(real_root, True, testruns.tree_hash(real_root),
                                "Closeout Quality Gate (carried over its wraps)")
        _save_run(real_root, run)

    # Commits: one per issue, then the shared ones, then the projections.
    for group in run["groups"]:
        if group["done"]:
            continue
        files = list(group["files"])
        if len(group["keys"]) == 1:
            files += run["entity_files"].get(group["keys"][0], [])
        changed = {path_key(p) for p in git_changes(real_root)}
        files = [f for f in dict.fromkeys(files) if path_key(f) in changed]
        if files:
            code = _commit(real_root, top, _commit_message(group["keys"], run["titles"]),
                           entities.parse_key(group["keys"][0])[1], files)
            if code != 0:
                _save_run(real_root, run)
                print("[Error] Commit failed; re-run 'along session close' to continue.", file=sys.stderr)
                return code
        group["done"] = True
        _save_run(real_root, run)
    if not run["projections_done"]:
        state_real = os.path.realpath(repo.state_dir(real_root))
        state_rel = repo.normalize_posix(os.path.relpath(state_real, top))
        state_prefix = "" if state_rel in ("", ".") else state_rel
        root_rel = repo.normalize_posix(os.path.relpath(real_root, top))
        root_prefix = "" if root_rel in ("", ".") else root_rel
        projections = [((f"{state_prefix}/{p[len('.along/'):]}".lstrip("/")) if p.startswith(".along/")
                        else (f"{root_prefix}/{p}".lstrip("/") if root_prefix else p)) for p in PROJECTION_FILES]
        # Docs and state the wraps rewrote (KB provenance) go with the projections.
        projections += [p for p in run.get("byproducts", []) if _is_wrap_byproduct(p)]
        changed = {path_key(p) for p in git_changes(real_root)}
        projections = [p for p in dict.fromkeys(projections) if path_key(p) in changed]
        if projections:
            code = _commit(real_root, top, _commit_message(run["keys"], run["titles"], projections=True),
                           entities.parse_key(run["keys"][0])[1], projections)
            if code != 0:
                _save_run(real_root, run)
                return code
        run["projections_done"] = True
        _save_run(real_root, run)

    if push and not run["pushed"]:
        result = proc.run_capture(["git", "push"], cwd=top, check=False, trip_on_anomaly=False)
        if not result.ok:
            _save_run(real_root, run)
            print(f"[Error] git push failed:\n{result.stderr}", file=sys.stderr)
            return 1
        run["pushed"] = True
        print("-> Pushed.")

    session.consume_closeout_approval(real_root, run.get("session"), [entities.parse_key(k)[1] for k in run["keys"]])
    try:
        os.remove(run_file(real_root))
    except OSError:
        pass
    print(f"-> [OK] Closed out {', '.join(run['keys'])}.")
    return 0


def format_closeout_status(status: Dict[str, Any]) -> str:
    """Human-readable `along session list`."""
    rep = status["repository"]
    lines = [f"Repository {rep['top']}: {len(rep['changed'])} changed path(s), "
             f"{len(rep['unattributed'])} unattributed, {len(rep['staged'])} staged"
             + (f", {rep['operation']} in progress" if rep["operation"] else "")
             + (f", {len(rep['conflicts'])} with conflict markers" if rep["conflicts"] else "")]
    if not status["items"]:
        lines.append("No issue in progress, no session bound, no blackboard.")
    for item in status["items"]:
        shared = sorted({k for f in item["files"].values() for k in f.get("shared_with", [])})
        exclusive = [p for p, f in item["files"].items() if not f.get("shared_with")]
        test = item["last_test"]
        lines.append(f"- {item['key']} [{item['verdict']}]")
        lines.append("    sessions: " + (", ".join(f"{s['key']} (last {s['last_event'] or '-'})"
                                                   for s in item["sessions"]) or "none bound"))
        lines.append(f"    files: {len(exclusive)} exclusive, {len(item['files']) - len(exclusive)} shared"
                     + (f" (with {', '.join(shared)})" if shared else "")
                     + f"; {len(item['changed_files'])} still uncommitted")
        lines.append(f"    tests: " + (f"{'pass' if test['ok'] else 'FAIL'} at {test['ts']}" if test else "none")
                     + f"; last edit {item['last_edit'] or '-'}; criteria {item['criteria'][0]}/{item['criteria'][1]}"
                     + f"; plan {'recorded' if item['plan_recorded'] else 'missing'}")
        for reason in item["reasons"]:
            lines.append(f"    blocked: {reason}")
    if rep["unattributed"]:
        lines.append("Unattributed changes (never committed by a closeout):")
        lines.extend(f"  {p}" for p in rep["unattributed"])
    for path in rep["conflicts"]:
        lines.append(f"Conflict: {path}")
    return "\n".join(lines)
