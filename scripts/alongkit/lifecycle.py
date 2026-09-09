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

LIFECYCLE_ACTIONS: tuple = ("build", "test", "dev")


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
    print(f"[Notice] Please configure {action} command in .along/scripts/{action}.py")
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


def execute_wrap(
    repo_root: str,
    slug: str,
    status: str = "done",
    summary: Optional[str] = None,
    dry_run: bool = False,
    no_verify: bool = False,
    agent: Optional[str] = None,
) -> int:
    """Execute automated session and issue wrap-up.

    1. Pre-flight test gate: executes repository automated tests unless no_verify.
    2. Working tree audit: verifies that modified files are non-zero size (no 0-byte corruptions).
    3. Issue finalization: updates YAML front-matter (status, updated, completed),
       rewrites sibling markdown links, and relocates to .along/ISSUES/done/.
    4. Projection recompilation: recompiles .along/ISSUES.md and Knowledge Base.
    5. Session blackboard purge: deletes .along/.session/<slug>/.
    6. History append: appends formatted entry to .along/HISTORY.md when summary is provided.

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
        corrupt_files = gates.zero_byte_working_tree_audit(repo_root)
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

        # Synchronize Knowledge Base
        kb_script = repo.resolve_tool_script("along_kb_sync.py", repo_root)
        if kb_script:
            kb_res = proc.run_python([kb_script, repo_root], cwd=repo_root)
            if not kb_res.ok:
                raise RuntimeError(f"Knowledge Base sync failed:\n{kb_res.stderr or kb_res.stdout}")
            print("-> Synchronized Knowledge Base.")

        # Purge session blackboard
        if session.purge_session(repo_root, clean_slug):
            print(f"-> Purged session blackboard: .along/.session/{clean_slug}")

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

