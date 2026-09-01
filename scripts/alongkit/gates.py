#!/usr/bin/env python3
"""
alongkit.gates - Pre-commit and pre-release quality gates.

`along_commit.py` and `along_version_bump.py` each carried their own copy of
`run_precommit_tests` and `sanitize_typography`, differing only in the label they print.
The consequence is not hypothetical: the release engine's copy discarded the sanitizer's
output entirely, so a release could not report what it had rewritten, while the commit
engine detected changes by string-matching the tool's own stdout.

Whether the sanitizer may rewrite unattended is settled by
ADR-2026-09-01--typography-rule-scope and `[bug--typography-sanitizer-destroys-non-utf8-files]`:
it may not. `typography_gate` runs in check mode, reports what it found, and returns
False; the caller aborts and the human decides. Rewriting requires an explicit
`allow_fix`, which the engines expose as `--fix-typography`.

Gates run BEFORE the mutations they guard. The release engine used to bump the version,
rewrite the tree, and flip milestone files first, then run the tests, then print
"Release aborted" over a half-released tree with no way back. A gate that reports after
the fact is not a gate. See
`[bug--release-engine-mutates-before-tests-and-reinstalls-globals]` and
`alongkit.transaction`, which supplies the rollback for the mutations themselves.
"""

from __future__ import annotations

import json
import os
import sys
from typing import List, Optional

from . import proc, repo, sanitizer


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


def link_integrity_gate(repo_root: str, label: str = "Quality Gate") -> bool:
    """Verify that every relative Markdown link resolves. True when the caller may proceed.

    Delegates to the Knowledge Base engine in `--check --strict` mode, which walks the
    whole tree, resolves links against disk, and exits non-zero on a broken one. `--check`
    is the engine's read-only mode: nothing is rewritten, no index is recompiled, so this
    is safe to run before a release has mutated anything.

    A repository without the engine (a consumer project with only the skills installed)
    passes: there is nothing to check with, and a missing optional tool must not block a
    release.
    """
    engine = repo.resolve_tool_script("along_kb_sync.py", repo_root)
    if not engine:
        return True

    print(f"-> [{label}] Verifying Markdown link integrity...")
    res = proc.run_python([engine, repo_root, "--check", "--strict"], cwd=repo_root)
    if res.ok:
        print(f"-> [{label}] Link integrity verified.")
        return True

    print(f"[Error] {label}: link integrity check failed.\n", file=sys.stderr)
    for stream in (res.stdout, res.stderr):
        if stream:
            print(stream, file=sys.stderr)
    return False


def run_sanitizer(repo_root: str, verbose: bool = True,
                  mode: str = sanitizer.Mode.CHECK,
                  **options) -> sanitizer.Report:
    """Inspect `repo_root` for banned typography and return the structured report.

    Runs in-process rather than shelling out to `sanitize_typography.py`: the policy
    lives in `alongkit.sanitizer`, so there is nothing a subprocess adds except a
    stdout string to parse. That string is exactly what the commit engine used to
    grep (`"Total files sanitized: 0" not in res.stdout`), and it is what
    `[bug--typography-sanitizer-destroys-non-utf8-files]` REQ-5 removes.

    Defaults to check mode, so calling this never modifies a file by accident.
    """
    report = sanitizer.run(repo_root, mode=mode, **options)
    if verbose and not report.clean:
        print(f"-> [Typography] {sanitizer.format_report(report)}")
    return report


def typography_gate(repo_root: str, label: str = "Quality Gate",
                    allow_fix: bool = False, **options) -> bool:
    """The pre-commit and pre-release typography gate. True when the caller may proceed.

    With `allow_fix` the banned characters are replaced and the gate passes; without
    it nothing is written and a finding fails the gate. An automated path must never
    rewrite a user's files without being told to: the previous behaviour was a
    repository-wide rewrite before every commit, with a lossy read that deleted the
    contents of any file that was not valid UTF-8.

    Files that could not be decoded are always reported, in both outcomes: they are
    the ones the old tool destroyed silently, so their names belong in the log even
    when the run is otherwise clean.
    """
    mode = sanitizer.Mode.WRITE if allow_fix else sanitizer.Mode.CHECK
    report = run_sanitizer(repo_root, verbose=False, mode=mode, **options)

    for skipped in report.skipped:
        print(f"-> [{label}] typography: skipped {skipped.path} ({skipped.reason})")

    if report.clean:
        print(f"-> [{label}] Typography clean ({report.files_scanned} files scanned).")
        return True

    if allow_fix:
        print(f"-> [{label}] Typography repaired:\n{sanitizer.format_report(report)}")
        return True

    print(f"[Error] {label}: banned typography found.\n"
          f"{sanitizer.format_report(report)}\n"
          "Re-run with --fix-typography to apply these replacements, or fix them by hand.",
          file=sys.stderr)
    return False
