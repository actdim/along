#!/usr/bin/env python3
"""
tests/test_destructive_command.py - Narrow destructive-command gate. [debt--gate-simplification]

Explicit recursive deletes and history rewrites are held only on facts: the target lies
outside the repository, is empty or unexpandable, or holds work git cannot restore. Every
other command passes. All fixtures are throwaway git repositories.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPTS_DIR = os.path.join(REPO_ROOT, "scripts")
if SCRIPTS_DIR not in sys.path:
    sys.path.insert(0, SCRIPTS_DIR)

from alongkit import bootstrap
bootstrap.ensure_deps()

from alongkit.hooks import GateDecision, HookEvent, HookEventType
from alongkit.hooks.deletion import find_problem
from alongkit.hooks.predicates import check_destructive_command


def _git_in(root, *args):
    subprocess.run(["git", "-c", "user.email=t@example.com", "-c", "user.name=t", *args],
                   cwd=root, check=True, capture_output=True)


class _Repo(unittest.TestCase):
    def setUp(self):
        self.root = os.path.realpath(tempfile.mkdtemp(prefix="along-destructive-"))
        # Outside both the repository and the temp dir; never created (the check is by path).
        self.outside = os.path.join(os.path.dirname(os.path.realpath(tempfile.gettempdir())),
                                    "along-destructive-outside-never-created")
        self._put("build/out.txt", "x\n")
        self._put("src/app.py", "x = 1\n")
        self._put(".gitignore", "node_modules/\n")
        self._put("node_modules/pkg/index.js", "x\n")
        _git_in(self.root, "init", "-q")
        _git_in(self.root, "add", "-A")
        _git_in(self.root, "commit", "-q", "-m", "init")

    def tearDown(self):
        shutil.rmtree(self.root, ignore_errors=True)

    def _put(self, rel, text):
        path = os.path.join(self.root, rel)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8", newline="\n") as f:
            f.write(text)

    def held(self, cmd):
        return find_problem(cmd, self.root, self.root)


class TestRecursiveDeletes(_Repo):
    def test_committed_and_ignored_paths_inside_pass(self):
        for cmd in ("rm -rf build", "rm -r build/", "Remove-Item -Recurse -Force build",
                    "del /s /q build", "rd /s /q build", "rmdir /s build", "rm -rf node_modules",
                    "rm -rf missing-dir", "rm -rf build/*", "ri build -Recurse"):
            with self.subTest(cmd=cmd):
                self.assertIsNone(self.held(cmd))

    def test_outside_the_repository_is_held(self):
        for cmd in (f"rm -rf {self.outside}", f"Remove-Item -Recurse {self.outside}",
                    f'rd /s /q "{self.outside}"', "rm -rf ..", "rm -rf ~"):
            with self.subTest(cmd=cmd):
                self.assertIn("outside the repository", self.held(cmd) or "")

    def test_repository_root_is_held(self):
        self.assertIn("repository itself", self.held("rm -rf .") or "")

    def test_untracked_and_modified_work_is_held(self):
        self._put("build/new.txt", "fresh\n")
        self.assertIn("uncommitted work", self.held("rm -rf build") or "")
        self._put("src/app.py", "x = 2\n")
        self.assertIn("uncommitted work", self.held("Remove-Item -Recurse src") or "")

    def test_empty_and_unexpandable_targets_are_held(self):
        env = {k: v for k, v in os.environ.items() if k not in ("ALONG_UNSET_X",)}
        with mock.patch.dict(os.environ, env, clear=True):
            for cmd in ("rm -rf $ALONG_UNSET_X/", "rm -rf ${ALONG_UNSET_X}",
                        "Remove-Item -Recurse $env:ALONG_UNSET_X", "rd /s /q %ALONG_UNSET_X%"):
                with self.subTest(cmd=cmd):
                    self.assertIn("cannot be expanded", self.held(cmd) or "")
        self.assertIn("command substitution", self.held("rm -rf $(pwd)/build") or "")
        self.assertIn("names no path", self.held("rm -rf") or "")
        self.assertIn("empty", self.held('rm -rf ""') or "")

    def test_expandable_variable_is_resolved(self):
        with mock.patch.dict(os.environ, {"ALONG_BUILD_DIR": "build"}):
            self.assertIsNone(self.held("rm -rf $ALONG_BUILD_DIR"))

    def test_temp_directory_children_pass(self):
        scratch = tempfile.mkdtemp(prefix="along-destructive-tmp-")
        try:
            self.assertIsNone(self.held(f"rm -rf {scratch}"))
        finally:
            shutil.rmtree(scratch, ignore_errors=True)

    def test_held_segment_found_in_a_chain(self):
        self.assertIsNotNone(self.held(f"git status && rm -rf {self.outside}"))

    def test_non_recursive_and_unlisted_commands_pass(self):
        for cmd in ("rm src/app.py", "rmdir empty", "python scripts/clean.py", "git status",
                    "Remove-Item src/app.py", "del src\\app.py"):
            with self.subTest(cmd=cmd):
                self.assertIsNone(self.held(cmd))


class TestGitHistory(_Repo):
    def test_reset_hard_on_a_clean_tree_passes(self):
        self.assertIsNone(self.held("git reset --hard HEAD"))

    def test_reset_hard_with_modified_files_is_held(self):
        self._put("src/app.py", "x = 2\n")
        self.assertIn("discards modified", self.held("git reset --hard") or "")
        self.assertIn("discards modified", self.held(f"git -C {self.root} reset --hard") or "")

    def test_clean_with_untracked_files_is_held(self):
        self.assertIsNone(self.held("git clean -fd"))
        self._put("scratch.txt", "x\n")
        self.assertIn("untracked", self.held("git clean -fd") or "")
        self.assertIn("untracked", self.held("git clean --force") or "")

    def test_force_push_is_always_held(self):
        for cmd in ("git push --force", "git push -f origin main", "git push --force-with-lease"):
            with self.subTest(cmd=cmd):
                self.assertIn("force-push", self.held(cmd) or "")
        self.assertIsNone(self.held("git push origin main"))


class TestPredicateDecision(_Repo):
    def _event(self, cmd, payload=None):
        return HookEvent(event_type=HookEventType.PRE_TOOL_USE, tool_name="run_command",
                         tool_args={"CommandLine": cmd}, workspace_root=self.root, runtime="claude",
                         raw_payload=payload or {})

    def test_interactive_asks_autonomous_denies(self):
        cmd = f"rm -rf {self.outside}"
        res = check_destructive_command(self._event(cmd), self.root)
        self.assertEqual(res.decision, GateDecision.ASK)
        res = check_destructive_command(self._event(cmd, {"permission_mode": "bypassPermissions"}), self.root)
        self.assertEqual(res.decision, GateDecision.DENY)

    def test_safe_command_passes(self):
        self.assertIsNone(check_destructive_command(self._event("rm -rf build"), self.root))


if __name__ == "__main__":
    unittest.main(verbosity=2)
