"""
testruns.py - One test run per completion [feat--parallel-session-closeout] REQ-8.

A test run is recorded with a hash of the working tree it ran on. `along wrap`, `along commit`
and `along bump` reuse the last green run when the tree has not changed since, instead of
running the full suite again.

The hash is the git tree id of the working tree (tracked and untracked, not ignored files),
built in a throwaway index. Along state (`.along/`, except the lifecycle hooks in
`.along/scripts/`) and the Knowledge Base projections that `along wrap` regenerates are left
out: a wrap between the test run and the commit does not change anything the tests check.
"""

from __future__ import annotations
if __name__ == "__main__":
    import os
    raise SystemExit(
        f"{os.path.basename(__file__)} is a library module, not a command.\n"
        "Run: python .along/scripts/test.py"
    )

import json
import os
import shutil
import tempfile
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from . import proc, repo, textio

TEST_RUNS_FILENAME: str = "test_runs.json"
#: Runs kept in the record.
MAX_RUNS: int = 20
#: Paths left out of the tree hash (git pathspecs).
EXCLUDED_PATHSPECS: tuple = (
    ":(glob)**/.along/**",
    ":(glob)**/docs/INDEX.md",
    ":(glob)**/docs/decisions/INDEX.md",
    "llms.txt",
    "llms-full.txt",
    # Bytecode the syntax gate writes is not source.
    ":(glob)**/__pycache__/**",
)


def _tree_git(top: str, args: List[str], env: Dict[str, str]) -> Optional[str]:
    result = proc.run_capture(["git", *args], cwd=top, env=env, check=False, trip_on_anomaly=False)
    return result.stdout.strip() if result.ok else None


def tree_hash(repo_root: str) -> Optional[str]:
    """Git tree id of the working tree without Along state and KB projections, or None
    outside a git repository."""
    top = _tree_git(repo_root, ["rev-parse", "--show-toplevel"], dict(os.environ))
    if not top:
        return None
    tmp = tempfile.mkdtemp(prefix="along-tree-")
    try:
        env = dict(os.environ)
        env["GIT_INDEX_FILE"] = os.path.join(tmp, "index")
        if _tree_git(top, ["rev-parse", "--verify", "-q", "HEAD"], env):
            if _tree_git(top, ["read-tree", "HEAD"], env) is None:
                return None
        if _tree_git(top, ["add", "-A", "--", "."], env) is None:
            return None
        _tree_git(top, ["rm", "-r", "--cached", "-q", "--ignore-unmatch", "--", *EXCLUDED_PATHSPECS], env)
        # The lifecycle hooks (.along/scripts/test.py, ...) decide what a test run is: they count.
        _tree_git(top, ["add", "-A", "--", ":(glob)**/.along/scripts/**", ":(exclude,glob)**/__pycache__/**"], env)
        return _tree_git(top, ["write-tree"], env) or None
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def _runs_file(repo_root: str) -> str:
    return os.path.join(repo.diagnostics_dir(repo_root), TEST_RUNS_FILENAME)


def load_runs(repo_root: str) -> List[Dict[str, Any]]:
    """Recorded runs, oldest first."""
    path = _runs_file(repo_root)
    try:
        data = json.loads(textio.read_text(path, strict=False)) if os.path.isfile(path) else []
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return []
    return [r for r in data if isinstance(r, dict)] if isinstance(data, list) else []


def record_run(repo_root: str, ok: bool, tree: Optional[str], source: str) -> None:
    """Remember a test run and the tree it ran on (machine-local diagnostics)."""
    runs = load_runs(repo_root)
    runs.append({"tree_hash": tree, "ok": bool(ok), "source": source,
                 "ts": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")})
    try:
        repo.ensure_diagnostics_dir(repo_root)
        textio.write_text(_runs_file(repo_root), json.dumps(runs[-MAX_RUNS:], indent=2) + "\n", newline="\n")
    except OSError:
        pass


def green_run_for(repo_root: str, tree: Optional[str]) -> Optional[Dict[str, Any]]:
    """The last run, when it was green on exactly this tree; else None."""
    if not tree:
        return None
    runs = load_runs(repo_root)
    last = next((r for r in reversed(runs) if r.get("tree_hash") == tree), None)
    return last if last and last.get("ok") else None
