#!/usr/bin/env python3
"""
alongkit.lifecycle - Repository execution lifecycle hooks and script synthesis.

Manages standard project execution hooks in `.along/scripts/`:
  - build.py (.sh / .ps1 / .bat)
  - test.py  (.sh / .ps1 / .bat)
  - dev.py   (.sh / .ps1 / .bat)

Provides explicit interpreter selection without shell=True, and generates
safe, non-interpolated hook scripts using shared repo-root discovery.
"""

from __future__ import annotations
if __name__ == "__main__":
    import os
    raise SystemExit(
        f"{os.path.basename(__file__)} is a library module, not a command.\n"
        "Run: along --help   (or: python scripts/along_exec.py --help)"
    )

import glob
import json
import os
import re
import shlex
import shutil
import sys
from typing import List, Optional, Sequence, Tuple, Union

from . import entities, frontmatter, gates, proc, repo, session, textio, transaction

LIFECYCLE_ACTIONS: tuple = ("build", "test", "dev", "debug")


def build_interpreter_cmd(script_file: str, extra_args: Sequence[str] = ()) -> List[str]:
    """Build an explicit argv command list for executing a lifecycle hook without shell=True.

    Selects interpreter by extension:
      - .py  -> sys.executable
      - .sh  -> bash
      - .ps1 -> powershell / pwsh (-NoProfile -File)
      - .bat / .cmd -> cmd.exe /c
      - default -> direct invocation
    """
    args = list(extra_args)
    if script_file.endswith(".py"):
        return [sys.executable, script_file, *args]

    if script_file.endswith(".sh"):
        bash_bin = shutil.which("bash") or "bash"
        return [bash_bin, script_file, *args]

    if script_file.endswith(".ps1"):
        ps_bin = shutil.which("pwsh") or shutil.which("powershell") or "powershell"
        return [ps_bin, "-NoProfile", "-File", script_file, *args]

    if script_file.endswith((".bat", ".cmd")):
        cmd_bin = os.environ.get("COMSPEC", "cmd.exe")
        return [cmd_bin, "/c", script_file, *args]

    return [script_file, *args]


def get_lifecycle_script_path(repo_root: str, action: str) -> str:
    """Locate existing lifecycle hook in .along/scripts/ or return default .py target."""
    scripts_dir = os.path.join(repo_root, ".along", "scripts")
    for ext in [".py", ".sh", ".ps1", ".bat"]:
        p = os.path.join(scripts_dir, f"{action}{ext}")
        if os.path.exists(p):
            return p
    return os.path.join(scripts_dir, f"{action}.py")


#: Lifecycle actions whose output is distilled for non-interactive callers. `dev` and
#: `debug` run servers / debuggers and always stream.
DISTILLED_ACTIONS = ("test", "build")
OUTPUT_MODE_ENV = "ALONG_OUTPUT"


def resolve_output_mode(action: str, args: Sequence[str],
                        stdout_isatty: Optional[bool] = None) -> Tuple[str, List[str]]:
    """Return ("raw" | "distill", args without Along's own flags).

    Precedence: `--raw` / `--distill` flag, then `ALONG_OUTPUT=raw|distill`, then the
    default: distill `test`/`build` when stdout is not a terminal (an agent or a pipe is
    reading it), stream otherwise so humans keep live progress. `--raw` is used rather
    than `--verbose` because `--verbose` belongs to the wrapped runners (pytest, cargo).
    """
    rest = [a for a in args if a not in ("--raw", "--distill")]
    if "--raw" in args:
        return "raw", rest
    if "--distill" in args:
        return "distill", rest
    env = os.environ.get(OUTPUT_MODE_ENV, "").strip().lower()
    if env in ("raw", "distill"):
        return env, rest
    if action not in DISTILLED_ACTIONS:
        return "raw", rest
    if stdout_isatty is None:
        try:
            stdout_isatty = sys.stdout.isatty()
        except (AttributeError, ValueError):
            stdout_isatty = False
    return ("raw" if stdout_isatty else "distill"), rest


def raw_log_path(repo_root: str, action: str) -> str:
    return os.path.join(repo_root, ".along", "artifacts", "lifecycle", f"{action}.log")


def run_lifecycle_command(action: str, cmd: Sequence[str], repo_root: str, mode: str) -> int:
    """Run a lifecycle command; in distill mode print the observation and keep the raw
    output in `.along/artifacts/lifecycle/<action>.log` (overwritten per run).

    A test run and its result go into the execution trace of the session's bound issue
    [bug--session-records-not-captured].
    """
    code = _run_lifecycle_command(action, cmd, repo_root, mode)
    if action == "test":
        session.trace_test_run(repo_root, code == 0, "along test")
    return code


def _run_lifecycle_command(action: str, cmd: Sequence[str], repo_root: str, mode: str) -> int:
    if mode != "distill":
        return proc.run_passthrough(list(cmd), cwd=repo_root)

    log_path = raw_log_path(repo_root, action)
    rel_log = repo.safe_relpath(log_path, repo_root).replace("\\", "/")
    # No anomaly classification: test output legitimately contains strings such as
    # "bad signature" from fixtures, and passthrough mode never classified it either.
    result = proc.run_capture(list(cmd), cwd=repo_root, distill=True, trip_on_anomaly=False)
    raw = result.stdout + ("\n" if result.stdout and result.stderr else "") + result.stderr
    try:
        os.makedirs(os.path.dirname(log_path), exist_ok=True)
        textio.write_text(log_path, raw, newline="\n")
        saved = True
    except OSError:
        saved = False
    print(result.observation or "")
    if saved:
        print(f"(raw output: {rel_log}; rerun with --raw to stream it)")
    return result.returncode


def synthesize_lifecycle_script(script_path: str, content: str) -> None:
    """Write synthesized lifecycle hook to disk with executable permissions."""
    os.makedirs(os.path.dirname(script_path), exist_ok=True)
    with open(script_path, "w", encoding="utf-8", newline=textio.newline_for_path(script_path)) as f:
        f.write(content)
    try:
        os.chmod(script_path, 0o755)
    except OSError:
        pass
    print(f"-> Created lifecycle hook: {script_path}")


def detect_lifecycle_action(repo_root: str, action: str) -> Tuple[Optional[str], bool]:
    """Auto-detect build/test/dev command for common project ecosystems."""
    # 1. Node.js
    pkg_json = os.path.join(repo_root, "package.json")
    if os.path.exists(pkg_json):
        try:
            with open(pkg_json, "r", encoding="utf-8") as f:
                data = json.load(f)
            scripts = data.get("scripts", {})
            if action == "build" and "build" in scripts:
                return "npm run build", True
            elif action == "test":
                return "npm test -- --silent" if "test" in scripts else "npm test", True
            elif action == "dev":
                cmd = "npm run dev" if "dev" in scripts else ("npm start" if "start" in scripts else None)
                if cmd:
                    return cmd, True
        except (OSError, json.JSONDecodeError, UnicodeDecodeError):
            pass

    # 2. Rust
    if os.path.exists(os.path.join(repo_root, "Cargo.toml")):
        if action == "build":
            return "cargo build", True
        elif action == "test":
            return "cargo test -q", True
        elif action == "dev":
            return "cargo run", True

    # 3. .NET
    if bool(glob.glob(os.path.join(repo_root, "*.csproj"))) or os.path.exists(os.path.join(repo_root, "Directory.Build.props")):
        if action == "build":
            return "dotnet build -v q", True
        elif action == "test":
            return "dotnet test -v q", True
        elif action == "dev":
            return "dotnet run", True

    # 4. Python
    if os.path.exists(os.path.join(repo_root, "pyproject.toml")) or os.path.exists(os.path.join(repo_root, "setup.py")):
        if action == "build":
            return "python -m build", True
        elif action == "test":
            return "pytest -q" if shutil.which("pytest") else "python -m unittest discover tests -q", True
        elif action == "dev":
            for main_file in ["main.py", "app.py", "server.py"]:
                if os.path.exists(os.path.join(repo_root, main_file)):
                    return f"python {main_file}", True

    return None, False


VERIFIED_HOOK_TEMPLATE = """#!/usr/bin/env python3
# Status: {status_tag}
# Auto-generated by Along for {action}
import os
import shutil
import subprocess
import sys

def find_repo_root(start_dir=None):
    try:
        from alongkit.repo import find_repo_root as resolver
        return resolver(start_dir)
    except ImportError:
        cur = os.path.abspath(start_dir or os.path.dirname(__file__))
        while True:
            for marker in (".along", ".git", "AGENTS.md"):
                if os.path.exists(os.path.join(cur, marker)):
                    return cur
            parent = os.path.dirname(cur)
            if parent == cur:
                return os.path.abspath(start_dir or os.path.dirname(__file__))
            cur = parent

def main():
    repo_root = find_repo_root(os.path.dirname(__file__))
    base_cmd = {base_cmd_repr}
    full_cmd = list(base_cmd) + sys.argv[1:]
    print(f"-> Running: {{' '.join(full_cmd)}}")
    target = shutil.which(full_cmd[0]) if (os.name == "nt" and full_cmd) else full_cmd[0]
    exec_cmd = [target or full_cmd[0]] + full_cmd[1:]
    res = subprocess.run(exec_cmd, cwd=repo_root)
    sys.exit(res.returncode)

if __name__ == "__main__":
    main()
"""

UNCONFIGURED_HOOK_TEMPLATE = """#!/usr/bin/env python3
# Status: {status_tag}
# Template for {action} in this repository
import os
import sys

def find_repo_root(start_dir=None):
    try:
        from alongkit.repo import find_repo_root as resolver
        return resolver(start_dir)
    except ImportError:
        cur = os.path.abspath(start_dir or os.path.dirname(__file__))
        while True:
            for marker in (".along", ".git", "AGENTS.md"):
                if os.path.exists(os.path.join(cur, marker)):
                    return cur
            parent = os.path.dirname(cur)
            if parent == cur:
                return os.path.abspath(start_dir or os.path.dirname(__file__))
            cur = parent

def main():
    repo_root = find_repo_root(os.path.dirname(__file__))
    print("[Warning] {action} is not configured for this repository: nothing was verified. "
          "Configure the command in .along/scripts/{action}.py", file=sys.stderr)
    sys.exit(0)

if __name__ == "__main__":
    main()
"""


def render_lifecycle_script(action: str,
                            base_cmd: Optional[Union[str, Sequence[str]]] = None,
                            status_tag: str = "verified") -> str:
    """Render a standalone Python lifecycle hook script.

    If `status_tag` is "unconfigured" or `base_cmd` is empty, renders the unconfigured notice template.
    Otherwise, splits command string into list at generation time and renders verified runner.
    """
    if status_tag == "unconfigured" or not base_cmd:
        return UNCONFIGURED_HOOK_TEMPLATE.format(status_tag="unconfigured", action=action)

    if isinstance(base_cmd, str):
        cmd_list = shlex.split(base_cmd)
    else:
        cmd_list = list(base_cmd)

    return VERIFIED_HOOK_TEMPLATE.format(
        status_tag=status_tag,
        action=action,
        base_cmd_repr=repr(cmd_list),
    )


def session_log_path(repo_root: str, slug: str, today: str) -> str:
    """`.along/SESSIONS/<YYYY>/<today>--<slug>.md`: one session log per issue and day."""
    return os.path.join(repo.state_dir(repo_root), "SESSIONS", today.split("-")[0], f"{today}--{slug}.md")


_RECORD_HEADING = re.compile(r"^## Blackboard Record\b", re.MULTILINE)


def write_session_record(repo_root: str, tx: "transaction.FileTransaction", slug: str, *, today: str,
                         issue: Optional[dict] = None, completed: bool = False,
                         summary: Optional[str] = None, agent: Optional[str] = None,
                         decisions: Optional[List[str]] = None, reason: Optional[str] = None) -> str:
    """Create or extend today's session log of `slug` with the blackboard record.

    The one writer behind `along wrap`, `along scratch purge` and `along issue done`
    [bug--session-records-not-captured]. `completed` adds the issue key to `issues_completed`
    [feat--wrap-session-log-from-blackboard]. `decisions` (wrap's answer) adds the Decisions
    section; None leaves it out. A later record of the same day is appended as
    `## Blackboard Record (<n>, <ts>)` instead of being dropped; `reason` (a forced purge) is
    written into the record.
    """
    from .version import CURRENT_PROTOCOL_VERSION

    issue = issue or entities.find_issue_by_slug(repo_root, slug) or {}
    log_path = session_log_path(repo_root, slug, today)
    key = f"{issue.get('type', 'task')}--{slug}"
    blackboard = session.render_blackboard_markdown(repo_root, slug, reason=reason)
    decisions_md = None
    if decisions is not None:
        decisions_md = "\n".join(f"- [{d}]" for d in decisions) if decisions else \
            "- None (confirmed at wrap: no architectural decisions)."
    tx.protect(log_path)

    if os.path.isfile(log_path):
        content = textio.read_text(log_path)
        fm, body, _err = frontmatter.try_parse(content)
        if fm is not None:
            updates = {}
            if completed:
                done = [str(x) for x in (fm.get("issues_completed") or [])]
                if key not in done:
                    updates["issues_completed"] = done + [key]
            known = [str(x) for x in (fm.get("decisions") or [])]
            extra = [d for d in (decisions or []) if d not in known]
            if extra:
                updates["decisions"] = known + extra
            if updates:
                content = frontmatter.update(content, updates)
        addition = ""
        if decisions_md and "## Decisions" not in content:
            addition += f"\n## Decisions\n{decisions_md}\n"
        if blackboard:
            records = len(_RECORD_HEADING.findall(content))
            if records:
                blackboard = blackboard.replace(
                    "## Blackboard Record", f"## Blackboard Record ({records + 1}, {session._utc_now_iso()})", 1)
            addition += "\n" + blackboard
        textio.write_text(log_path, content.rstrip("\n") + "\n" + addition, newline="\n")
        return log_path

    branch = proc.git(["rev-parse", "--abbrev-ref", "HEAD"], cwd=repo_root)
    head = proc.git(["rev-parse", "--short", "HEAD"], cwd=repo_root)
    fm_out = {
        "protocol": "along",
        "protocol_version": frontmatter.quoted(CURRENT_PROTOCOL_VERSION),
        "date": today,
        "slug": slug,
        "agent": agent or entities.detect_agent(),
    }
    if branch.ok and branch.stdout.strip():
        fm_out["branch"] = branch.stdout.strip()
    if head.ok and head.stdout.strip():
        fm_out["commit"] = head.stdout.strip()
    fm_out["summary"] = (summary or (f"Completed {key}" if completed else f"Record of {key}")).strip()
    milestone = (issue.get("frontmatter") or {}).get("milestone")
    if milestone:
        fm_out["milestone"] = milestone
    fm_out.update({
        "issues_advanced": [],
        "issues_completed": [key] if completed else [],
        "decisions": list(decisions or []),
        "risks_logged": [],
        "spikes_conducted": [],
    })
    title = (issue.get("frontmatter") or {}).get("title") or slug.replace("-", " ").capitalize()
    body = f"# Session: {title}\n\n## Summary\n{fm_out['summary']}\n\n"
    if decisions_md:
        body += f"## Decisions\n{decisions_md}\n\n"
    body += blackboard or ""
    os.makedirs(os.path.dirname(log_path), exist_ok=True)
    textio.write_text(log_path, frontmatter.render(fm_out, body), newline="\n")
    return log_path


def archive_and_purge(repo_root: str, slug: str, *, reason: Optional[str] = None, completed: bool = False,
                      source: str = "purge", today: Optional[str] = None,
                      tx: Optional["transaction.FileTransaction"] = None) -> Optional[str]:
    """Write the blackboard of `slug` into its session log, then delete it.

    The only way a blackboard leaves the repository [bug--session-records-not-captured]
    REQ-3. With `tx`, the log is written in the caller's transaction and the caller purges
    (`purge_archived`) after committing; without, this commits its own. Returns the log path,
    or None when there is no blackboard.
    """
    if not session.load_state(repo_root, slug):
        return None
    today = today or entities.today_iso()
    session.append_trace(repo_root, slug, f"archived by {source}" + (f": {reason}" if reason else ""))
    own = tx is None
    tx = tx or transaction.FileTransaction(repo_root, label=f"archive-{slug}")
    try:
        log_path = write_session_record(repo_root, tx, slug, today=today, completed=completed, reason=reason)
        if own:
            tx.commit()
    except Exception:
        if own:
            tx.rollback()
        raise
    if own:
        purge_archived(repo_root, slug)
    return log_path


def orphan_blackboards(repo_root: str) -> List[Tuple[str, str]]:
    """(slug, why) of blackboards no session is bound to whose issue is closed or missing.

    `along doctor` reports them; `along scratch purge <slug>` archives and removes one.
    See [bug--session-records-not-captured] REQ-8.
    """
    s_root = os.path.join(repo.state_dir(repo_root), ".session")
    if not os.path.isdir(s_root):
        return []
    bound = {str(b.get("slug")) for b in session.list_bindings(repo_root) if b.get("slug")}
    found: List[Tuple[str, str]] = []
    for entry in sorted(os.scandir(s_root), key=lambda e: e.name):
        if not entry.is_dir() or entry.name.startswith(".") or entry.name == session.BINDINGS_DIRNAME:
            continue
        if entry.name in bound:
            continue
        issue = entities.find_issue_by_slug(repo_root, entry.name)
        if not issue:
            found.append((entry.name, "issue missing"))
        elif issue.get("status") in entities.CLOSED_ISSUE_STATUSES:
            found.append((entry.name, f"issue {issue.get('status')}"))
    return found


def purge_archived(repo_root: str, slug: str, complete: bool = False) -> bool:
    """Purge a blackboard whose record is committed; a failed delete only warns (nothing is lost)."""
    try:
        return session.purge_session(repo_root, slug, complete=complete)
    except OSError as exc:
        print(f"[Warning] Blackboard '.along/.session/{slug}' archived but not deleted: {exc}", file=sys.stderr)
        return False


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
) -> int:
    """Execute automated session and issue wrap-up.

    `decisions` is the answer to "were architectural decisions made?": a list of ADR keys,
    or [] for an explicit no. When given, the session log for today is written (or
    extended) with the blackboard record before the purge. A role-based blackboard with
    open steps or missing reviews blocks the wrap unless `force_reason` says why.
    See [feat--wrap-session-log-from-blackboard] and [feat--along-team-step-enforcement].

    1. Pre-flight test gate: executes repository automated tests unless no_verify.
    2. Working tree audit: a truncated tracked file or an empty session-edited file aborts;
       other empty files only warn.
    3. Issue finalization: updates YAML front-matter (status, updated, completed),
       rewrites sibling markdown links, and relocates to .along/ISSUES/done/.
    4. Projection recompilation: recompiles .along/ISSUES.md and Knowledge Base.
    5. Session log: the blackboard record (refused while plan.md is the scaffold, unless
       `force_reason`).
    6. History append: appends formatted entry to .along/HISTORY.md when summary is provided.
    7. Session blackboard purge, after the transaction committed: deletes .along/.session/<slug>/.

    All disk mutations are protected by FileTransaction for byte-exact rollback on failure.
    """
    clean_type, clean_slug = entities.parse_key(slug)
    issue = entities.find_issue_by_slug(repo_root, slug)
    if not issue:
        print(f"[Error] Issue '{slug}' not found in .along/ISSUES/.", file=sys.stderr)
        return 1

    if status not in entities.CLOSED_ISSUE_STATUSES:
        print(
            f"[Error] Invalid closing status '{status}'. "
            f"Allowed statuses: {', '.join(entities.CLOSED_ISSUE_STATUSES)}",
            file=sys.stderr,
        )
        return 1

    src_file = issue["file_path"]
    is_already_done = issue.get("done", False) or "done" in os.path.normpath(src_file).split(os.sep)

    # 0. along-team step discipline
    problems = session.completion_problems(repo_root, clean_slug)
    if problems and not force_reason:
        print(f"[Error] Wrap aborted: role-based blackboard '{clean_slug}' is not complete:\n"
              + "\n".join(f"  - {p}" for p in problems)
              + "\n  Finish the steps with reviews/step-N.md, or pass --force-reason \"...\".", file=sys.stderr)
        return 2
    if problems:
        session.append_trace(repo_root, clean_slug, f"Wrapped with open steps ({'; '.join(problems)}): {force_reason}")
    # [bug--session-records-not-captured] REQ-5: a blackboard is never archived without its plan.
    has_blackboard = session.load_state(repo_root, clean_slug) is not None
    if has_blackboard and not session.plan_recorded(repo_root, clean_slug):
        if not force_reason:
            print(f"[Error] Wrap aborted: no plan recorded for '{clean_slug}' (.along/.session/{clean_slug}/plan.md "
                  "is the scaffold).\n  Record the approved plan ('along plan approve <slug> --plan-file <path>', "
                  "or write it into plan.md), or pass --force-reason \"...\".", file=sys.stderr)
            return 2
        if not dry_run:
            session.append_trace(repo_root, clean_slug, f"Wrapped without a recorded plan: {force_reason}")

    # 1. Pre-Flight Test Gate
    if not no_verify and not dry_run:
        if not gates.run_repository_tests(repo_root, label="Wrap Quality Gate"):
            print(
                "[Error] Wrap aborted: automated tests failed. Fix failing tests before wrapping up.",
                file=sys.stderr,
            )
            return 1

    # 2. Working tree zero-byte audit
    if not dry_run:
        corrupt_files, empty_files = gates.zero_byte_working_tree_audit(repo_root)
        if empty_files:
            print("[Warning] Empty file(s) in the working tree, not edited in an agent session "
                  "(not blocking):\n" + "\n".join(f"  - {f}" for f in empty_files), file=sys.stderr)
        if corrupt_files:
            print(
                "[Error] Wrap aborted: 0-byte file(s) detected in working tree:\n"
                + "\n".join(f"  - {f}" for f in corrupt_files),
                file=sys.stderr,
            )
            return 1

    done_dir = os.path.join(repo.state_dir(repo_root), "ISSUES", "done")
    dest_file = os.path.join(done_dir, os.path.basename(src_file))

    # 3. Dry-run mode
    if dry_run:
        print(f"-> [Dry-Run] Wrap plan for issue '{slug}':")
        if not is_already_done:
            print(f"   - Relocate {repo.safe_relpath(src_file, repo_root)} -> {repo.safe_relpath(dest_file, repo_root)}")
            print(f"   - Update front-matter: status={status}, completed={entities.today_iso()}, updated={entities.today_iso()}")
        else:
            print(f"   - Issue already in done/: {repo.safe_relpath(src_file, repo_root)}")
        print("   - Recompile .along/ISSUES.md projection board")
        print("   - Synchronize Knowledge Base (docs/INDEX.md)")
        print(f"   - Purge session blackboard: .along/.session/{clean_slug}/")
        if summary:
            print(f"   - Append entry to .along/HISTORY.md: {summary.strip()}")
        return 0

    # 4. Transactional execution
    tx = transaction.FileTransaction(repo_root, label=f"wrap-{clean_slug}")
    try:
        today = entities.today_iso()
        content = textio.read_text(src_file)

        if not frontmatter.has_frontmatter(content):
            print(f"[Error] {os.path.basename(src_file)} has no parseable YAML front-matter.", file=sys.stderr)
            return 1

        updates = {"status": status, "updated": today, "completed": today}
        new_content = frontmatter.update(
            content,
            updates,
            place_after={"completed": "status"},
        )

        if not is_already_done:
            block = frontmatter.split(new_content)
            if block:
                sibling_link_re = re.compile(
                    r'(\[[^\]]+\]\()(?:\./)?(?<!\.\./)((?:feat|bug|debt|task|docs)--[a-z0-9-]+\.md\b)'
                )
                body_lines = block.body.splitlines(keepends=True)
                adjusted_body_lines = []
                in_fence = False
                for line in body_lines:
                    stripped = line.strip()
                    if stripped.startswith("```") or stripped.startswith("~~~"):
                        in_fence = not in_fence
                        adjusted_body_lines.append(line)
                        continue
                    if in_fence:
                        adjusted_body_lines.append(line)
                        continue
                    adjusted_body_lines.append(sibling_link_re.sub(r'\1../\2', line))
                new_content = block.bom + block.open_delim + block.raw + block.close_delim + "".join(adjusted_body_lines)

            os.makedirs(done_dir, exist_ok=True)
            tx.protect(src_file)
            tx.protect(dest_file)
            textio.write_text(dest_file, new_content, newline="\n")
            if os.path.abspath(src_file) != os.path.abspath(dest_file):
                os.remove(src_file)
            print(f"-> Moved issue to done: {repo.safe_relpath(dest_file, repo_root)}")
        else:
            tx.protect(src_file)
            textio.write_text(src_file, new_content, newline="\n")
            print(f"-> Updated issue in done: {repo.safe_relpath(src_file, repo_root)}")

        # Recompile .along/ISSUES.md
        board_file = os.path.join(repo.state_dir(repo_root), "ISSUES.md")
        tx.protect(board_file)
        board_content = entities.compile_issues_board(repo_root)
        textio.write_text(board_file, board_content, newline="\n")
        print(f"-> Updated {repo.safe_relpath(board_file, repo_root)}")

        # [gate: entity-reference-integrity]: enforce mode rolls the wrap back.
        if not gates.entity_integrity_gate(repo_root, "Wrap Quality Gate"):
            raise RuntimeError("entity graph has dangling references or schema violations")

        # Synchronize Knowledge Base
        kb_script = repo.resolve_tool_script("along_kb_sync.py", repo_root)
        if kb_script:
            kb_res = proc.run_python([kb_script, repo_root], cwd=repo_root)
            if not kb_res.ok:
                raise RuntimeError(f"Knowledge Base sync failed:\n{kb_res.stderr or kb_res.stdout}")
            print("-> Synchronized Knowledge Base.")

        # Session log with the blackboard record; the blackboard is purged only after the
        # transaction committed [bug--session-records-not-captured].
        if decisions is not None or has_blackboard:
            log_path = write_session_record(
                repo_root, tx, clean_slug, today=today, issue=issue, completed=(status == "done"),
                summary=summary, agent=agent, decisions=decisions,
            )
            print(f"-> Wrote session log: {repo.safe_relpath(log_path, repo_root)}")

        # Append to HISTORY.md if summary provided
        if summary:
            history_file = os.path.join(repo.state_dir(repo_root), "HISTORY.md")
            if os.path.isfile(history_file):
                tx.protect(history_file)
                effective_agent = agent or entities.detect_agent()
                year = today.split("-")[0]
                session_file = os.path.join(repo.state_dir(repo_root), "SESSIONS", year, f"{today}--{clean_slug}.md")
                if os.path.isfile(session_file):
                    link = f"[Session Log](./SESSIONS/{year}/{today}--{clean_slug}.md)"
                else:
                    rel_done = repo.safe_relpath(dest_file, repo.state_dir(repo_root)).replace("\\", "/")
                    link = f"[{issue.get('type', 'issue')}](./{rel_done})"
                history_line = f"{today} - {clean_slug} - {effective_agent} - {summary.strip()} - {link}\n"
                hist_raw = textio.read_text(history_file)
                if not hist_raw.endswith("\n"):
                    hist_raw += "\n"
                hist_raw += history_line
                textio.write_text(history_file, hist_raw, newline="\n")
                print(f"-> Appended history entry to {repo.safe_relpath(history_file, repo_root)}")

        tx.commit()
        # This session keeps a completion token for the commit that follows
        # [bug--commit-blocked-after-wrap].
        if purge_archived(repo_root, clean_slug, complete=True):
            print(f"-> Purged session blackboard: .along/.session/{clean_slug}")
        print(f"-> [OK] Successfully wrapped up '{clean_slug}'.")
        return 0

    except (OSError, RuntimeError, ValueError, KeyError, frontmatter.FrontmatterError) as exc:
        print(f"[Error] Wrap failed: {exc}", file=sys.stderr)
        restored = tx.rollback()
        if restored:
            print(f"-> Rolled back {len(restored)} modified file(s):", file=sys.stderr)
            for r in restored:
                print(f"   - {r}", file=sys.stderr)
        return 1
    except Exception:
        tx.rollback()
        raise

