#!/usr/bin/env python3
"""tests/test_cli_chdir.py - Hermetic tests for Along CLI global -C / --chdir option."""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
import unittest


class TestCliChdir(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="along-test-chdir-")
        self.scripts_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "scripts"))
        self.along_exec = os.path.join(self.scripts_dir, "along_exec.py")

        # Create root context with .along
        self.root_along = os.path.join(self.tmp, ".along")
        os.makedirs(os.path.join(self.root_along, "ISSUES"), exist_ok=True)
        with open(os.path.join(self.root_along, "ISSUES.md"), "w", encoding="utf-8") as f:
            f.write("# Root Issues Board\n")

        # Create nested subproject with its own .along
        self.sub_dir = os.path.join(self.tmp, "packages", "subproject")
        self.sub_along = os.path.join(self.sub_dir, ".along")
        os.makedirs(os.path.join(self.sub_along, "ISSUES"), exist_ok=True)
        with open(os.path.join(self.sub_along, "ISSUES.md"), "w", encoding="utf-8") as f:
            f.write("# Subproject Issues Board\n")

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _run(self, *args, cwd=None):
        cmd = [sys.executable, self.along_exec, *args]
        return subprocess.run(cmd, cwd=cwd or self.tmp, capture_output=True, text=True)

    def test_chdir_to_valid_subproject(self):
        res = self._run("-C", "packages/subproject", "status")
        self.assertEqual(res.returncode, 0, f"stderr: {res.stderr}")
        self.assertIn("packages/subproject", res.stdout.replace("\\", "/"))

    def test_chdir_nonexistent_directory_exits_2(self):
        res = self._run("-C", "packages/nonexistent", "status")
        self.assertEqual(res.returncode, 2)
        self.assertIn("Target directory does not exist", res.stderr)

    def test_chdir_missing_dir_argument_exits_2(self):
        res = self._run("-C")
        self.assertEqual(res.returncode, 2)
        self.assertIn("requires a directory argument", res.stderr)

    def test_chdir_chained(self):
        res = self._run("-C", "packages", "-C", "subproject", "status")
        self.assertEqual(res.returncode, 0, f"stderr: {res.stderr}")
        self.assertIn("packages/subproject", res.stdout.replace("\\", "/"))

    def test_chdir_attached_flag(self):
        res = self._run("-Cpackages/subproject", "status")
        self.assertEqual(res.returncode, 0, f"stderr: {res.stderr}")
        self.assertIn("packages/subproject", res.stdout.replace("\\", "/"))

    def test_chdir_long_flag_with_equal(self):
        res = self._run("--chdir=packages/subproject", "status")
        self.assertEqual(res.returncode, 0, f"stderr: {res.stderr}")
        self.assertIn("packages/subproject", res.stdout.replace("\\", "/"))

    def test_alongkit_cli_entry_point_chdir(self):
        from alongkit import cli
        code = cli.main(["-C", "packages/nonexistent-xyz", "status"])
        self.assertEqual(code, 2)

    def test_alongkit_cli_does_not_load_commands(self):
        cmd = [
            sys.executable,
            "-c",
            "import sys; import alongkit.cli; "
            "assert 'alongkit.commands' not in sys.modules, 'alongkit.commands loaded prematurely'"
        ]
        res = subprocess.run(cmd, cwd=self.tmp, capture_output=True, text=True)
        self.assertEqual(res.returncode, 0, f"stdout: {res.stdout}\nstderr: {res.stderr}")

    def test_handle_chdir_options_cliargs_and_backward_compat(self):
        from alongkit.cliargs import _handle_chdir_options as handle_from_cliargs
        from alongkit.cli import _handle_chdir_options as handle_from_cli

        self.assertIs(handle_from_cliargs, handle_from_cli)
        target, rem = handle_from_cliargs(["-C", "sub/dir", "status"])
        self.assertEqual(target, os.path.normpath("sub/dir"))
        self.assertEqual(rem, ["status"])


if __name__ == "__main__":
    unittest.main()
