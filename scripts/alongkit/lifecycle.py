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
import shlex
import shutil
import sys
from typing import List, Optional, Sequence, Tuple, Union

from . import textio

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
