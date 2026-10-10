#!/usr/bin/env python3
"""
tests/test_subcommand_help.py - `-h` / `--help` after a subcommand prints usage and writes
nothing; entity names that look like flags are rejected [bug--subcommand-help-as-argument].
"""

from __future__ import annotations

import hashlib
import os
import shutil
import sys
import unittest

if not os.environ.get("ALONG_TEST_RUNNER"):
    raise SystemExit(
        "[Error] Tests must not be run directly or via standard test commands (unittest/pytest).\n"
        "To run tests with automatically resolved dependencies, use the official project entry point:\n"
        "    python .along/scripts/test.py"
    )

TESTS_DIR = os.path.dirname(os.path.abspath(__file__))
if TESTS_DIR not in sys.path:
    sys.path.insert(0, TESTS_DIR)

import hermetic
from alongkit import proc

ALONG_EXEC = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                          "scripts", "along_exec.py")

#: Every native router and its subcommands (aliases included).
ROUTERS = {
    "issue": ["create", "update", "edit", "done", "close", "cancel", "delete", "reopen", "sync",
              "list", "show", "get", "rename", "supersede"],
    "milestone": ["sync", "list", "show", "create"],
    "start": [],
    "session": ["create", "wrap", "bindings", "gc", "list", "close"],
    "plan": ["approve", "status"],
    "decision": ["create", "add", "sync"],
    "scratch": ["init", "state", "update", "approve", "plan-approve", "phase", "fallback", "purge"],
    "worktree": ["create", "remove", "merge", "list", "status", "gc"],
    "git": ["setup", "status", "sync"],
    "gates": ["check"],
    "rules": ["attach", "status", "diff", "restore"],
    "budget": [],
    "patch": ["replace-func"],
    "circuit": ["status", "trip", "reset", "verify"],
    "telemetry": ["status", "flush"],
    "status": [],
    "doctor": ["entities"],
}


def _snapshot(root: str, with_dirs: bool = True) -> dict:
    """Relative path -> content hash for every file (and every directory when asked)."""
    snap = {}
    for dirpath, dirnames, filenames in os.walk(root):
        rel_dir = os.path.relpath(dirpath, root)
        if with_dirs:
            snap[rel_dir + "/"] = "dir"
        for name in filenames:
            path = os.path.join(dirpath, name)
            with open(path, "rb") as fh:
                snap[os.path.join(rel_dir, name)] = hashlib.sha256(fh.read()).hexdigest()
    return snap


class TestSubcommandHelp(unittest.TestCase):

    def setUp(self):
        self.repo = hermetic.make_repo_fixture(prefix="along-subcommand-help-test-")
        self.env = hermetic.isolated_home_env()
        self.env.pop("ALONG_SESSION_ID", None)

    def tearDown(self):
        shutil.rmtree(self.repo, ignore_errors=True)

    def _run(self, *args: str) -> proc.Result:
        return proc.run_capture([sys.executable, ALONG_EXEC, *args], cwd=self.repo, env=self.env,
                                timeout=60)

    def _invocations(self):
        for router, subs in ROUTERS.items():
            for flag in ("--help", "-h"):
                yield [router, flag]
                yield [router, "fixture-slug", flag]
                for sub in subs:
                    yield [router, sub, flag]
                    yield [router, sub, "fixture-slug", flag]

    def test_help_after_subcommand_prints_usage_and_writes_nothing(self):
        before = _snapshot(self.repo)
        for argv in self._invocations():
            with self.subTest(argv=" ".join(argv)):
                res = self._run(*argv)
                self.assertEqual(res.returncode, 0, f"stdout={res.stdout!r} stderr={res.stderr!r}")
                self.assertIn("Usage", res.stdout)
                self.assertEqual(_snapshot(self.repo), before, "help must not write to the repository")

    def test_help_narrows_to_the_named_subcommand(self):
        res = self._run("scratch", "init", "--help")
        self.assertEqual(res.returncode, 0)
        self.assertIn("init   <slug>", res.stdout)
        self.assertNotIn("purge  <slug>", res.stdout)
        self.assertIn("along scratch --help", res.stdout)

    def test_reported_cases_have_no_side_effects(self):
        before = _snapshot(self.repo)
        for argv in (["decision", "create", "--help"], ["issue", "update", "--help"],
                     ["issue", "create", "--help"], ["scratch", "init", "--help"]):
            with self.subTest(argv=" ".join(argv)):
                res = self._run(*argv)
                self.assertEqual(res.returncode, 0)
                self.assertNotIn("[Error]", res.stderr)
        self.assertEqual(_snapshot(self.repo), before)
        self.assertFalse(os.path.exists(os.path.join(self.repo, ".along", ".session", "--help")))
        self.assertFalse(os.path.isdir(os.path.join(self.repo, ".along", "DECISIONS")))

    def test_flag_like_entity_names_are_rejected(self):
        before = _snapshot(self.repo, with_dirs=False)
        for argv in (["decision", "create", "-x"], ["milestone", "create", "-x"],
                     ["session", "create", "-x"], ["scratch", "init", "--foo"],
                     ["start", "-x"], ["worktree", "create", "-x"],
                     ["issue", "rename", "-x", "task--other-name"],
                     ["issue", "rename", "task--fixture-sample-task", "-x"],
                     # [bug--cli-entity-sync-defects] REQ-4
                     ["issue", "create", "task", "-x"], ["issue", "done", "-x"],
                     ["issue", "cancel", "-x"], ["issue", "delete", "-x"],
                     ["session", "wrap", "-x"]):
            with self.subTest(argv=" ".join(argv)):
                res = self._run(*argv)
                self.assertEqual(res.returncode, 2, f"stderr={res.stderr!r}")
                self.assertIn("cannot start with '-'", res.stderr)
        self.assertEqual(_snapshot(self.repo, with_dirs=False), before)
        # A rejected session name leaves no SESSIONS/<year>/ directory behind.
        sessions = os.path.join(self.repo, ".along", "SESSIONS")
        self.assertFalse(os.path.isdir(sessions) and any(
            name.isdigit() and not os.listdir(os.path.join(sessions, name)) for name in os.listdir(sessions)))

    def test_help_after_double_dash_is_not_intercepted(self):
        res = self._run("decision", "create", "--", "--help")
        self.assertNotEqual(res.returncode, 0)
        self.assertIn("cannot start with '-'", res.stderr)

    def test_commit_and_bump_help_print_usage_and_write_nothing(self):
        before = _snapshot(self.repo)
        for argv in (["commit", "--help"], ["commit", "-h"],
                     ["bump", "--help"], ["bump", "-h"]):
            with self.subTest(argv=" ".join(argv)):
                res = self._run(*argv)
                self.assertEqual(res.returncode, 0, f"stdout={res.stdout!r} stderr={res.stderr!r}")
                self.assertTrue("usage" in res.stdout.lower())
                self.assertEqual(_snapshot(self.repo), before, "help must not write to the repository")


if __name__ == "__main__":
    unittest.main()
