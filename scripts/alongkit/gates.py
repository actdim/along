#!/usr/bin/env python3
"""
alongkit.gates - Pre-commit and pre-release quality gates.

`along_commit.py` and `along_version_bump.py` each carried their own copy of
`run_precommit_tests` and `sanitize_typography`, differing only in the label they print.
The consequence is not hypothetical: the release engine's copy discarded the sanitizer's
output entirely, so a release could not report what it had rewritten, while the commit
engine detected changes by string-matching the tool's own stdout.

Policy questions about these gates (whether the sanitizer may rewrite unattended, whether
tests run before or after mutations) belong to their own issues:
`[bug--typography-sanitizer-destroys-non-utf8-files]` and
`[bug--release-engine-mutates-before-tests-and-reinstalls-globals]`. This module only gives
them a single implementation to change.
"""

from __future__ import annotations

import json
import os
import sys
from typing import List, Optional

from . import proc, repo


def detect_test_command(repo_root: str) -> Optional[List[str]]:
    """The command that runs this repository's tests, or None when there are none.

    Order of preference: the repository's own `.along/scripts/test.py` lifecycle hook, a
    `tests/` directory, then an npm `test` script.
    """
    hook = os.path.join(repo.state_dir(repo_root), "scripts", "test.py")
    if os.path.exists(hook):
        return [sys.executable, hook]

    if os.path.isdir(os.path.join(repo_root, "tests")):
        return [sys.executable, "-m", "unittest", "discover", "-s", "tests", "-p", "test_*.py"]

    manifest = os.path.join(repo_root, "package.json")
    if os.path.exists(manifest):
        try:
            with open(manifest, "r", encoding="utf-8") as handle:
                package = json.load(handle)
        except (OSError, ValueError) as exc:
            # Previously `json` was not even imported here and the NameError was swallowed
            # by a bare `except Exception: pass`, so a repository with a package.json
            # silently ran no tests at all.
            print(f"[Warning] cannot read package.json: {exc}", file=sys.stderr)
            return None
        if isinstance(package.get("scripts"), dict) and "test" in package["scripts"]:
            return ["npm", "test", "--", "--silent"]
    return None


def run_repository_tests(repo_root: str, label: str = "Quality Gate") -> bool:
    """Run the repository's tests, printing the outcome. True when they passed or none exist."""
    cmd = detect_test_command(repo_root)
    if not cmd:
        return True

    print(f"-> [{label}] Running automated tests: {' '.join(cmd)}")
    res = proc.run_capture(cmd, cwd=repo_root)
    if res.ok:
        print(f"-> [{label}] All tests passed successfully.")
        return True

    print(f"[Error] {label}: automated tests failed.\n", file=sys.stderr)
    if res.stdout:
        print(res.stdout, file=sys.stderr)
    if res.stderr:
        print(res.stderr, file=sys.stderr)
    return False


def run_sanitizer(repo_root: str, verbose: bool = True) -> Optional[proc.Result]:
    """Run the typography sanitizer, if it is installed alongside this engine.

    Returns its Result, or None when the sanitizer is not present. Callers should not
    parse the returned stdout for a count: emitting a machine-readable summary is
    `[bug--typography-sanitizer-destroys-non-utf8-files]` REQ-5.
    """
    sanitizer = repo.resolve_tool_script("sanitize_typography.py", repo_root)
    if not sanitizer:
        return None
    res = proc.run_python([sanitizer], cwd=repo_root)
    if verbose and res.stdout.strip() and "Total files sanitized: 0" not in res.stdout:
        print(f"-> [Typography Sanitizer] {res.out}")
    return res
