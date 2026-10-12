#!/usr/bin/env python3
"""
tests/test_bootstrap.py - Unit tests for alongkit.bootstrap.
Covers inline invocation (-c) support, venv reuse, fallback to uv run, and graceful degradation.
[feat--bootstrap-resilience-and-subcommand-proxying]
"""

from __future__ import annotations

import os
import shutil
import sys
import tempfile
import unittest
from unittest import mock

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPTS_DIR = os.path.join(REPO_ROOT, "scripts")
if SCRIPTS_DIR not in sys.path:
    sys.path.insert(0, SCRIPTS_DIR)

from alongkit import bootstrap, textio


class TestBootstrapInline(unittest.TestCase):
    """Verifies bootstrap.ensure_deps with sys.argv[0] == '-c'."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.venv_dir = os.path.join(self.tmp.name, "venv")

    def tearDown(self):
        self.tmp.cleanup()

    def _plant_venv(self, venv_dir, specs):
        python = bootstrap.venv_python(venv_dir)
        os.makedirs(os.path.dirname(python), exist_ok=True)
        textio.write_text(python, "")
        textio.write_text(os.path.join(venv_dir, ".along-deps"), "\n".join(specs) + "\n")
        return python

    def test_inline_reexec_uv_run_fallback(self):
        """When sys.argv[0] == '-c' and venv cannot be built, falls back to uv run --with spec python *sys.argv[1:]."""
        captured = {}

        def fake_reexec(command, missing_exit_code, **_kwargs):
            captured["command"] = command
            raise SystemExit(0)

        with mock.patch.object(bootstrap, "have_deps", return_value=False), \
                mock.patch.object(bootstrap, "_reexec", side_effect=fake_reexec), \
                mock.patch.object(bootstrap, "_build_venv", return_value=False), \
                mock.patch("shutil.which", return_value="uv"), \
                mock.patch.dict(os.environ, {bootstrap.VENV_ENV: self.venv_dir}), \
                mock.patch.object(sys, "argv", ["-c", "-c", "import alongkit"]):
            os.environ.pop(bootstrap.GUARD_ENV, None)
            with self.assertRaises(SystemExit):
                bootstrap.ensure_deps(dependencies=["ruamel.yaml>=0.18"])

        cmd = captured.get("command")
        self.assertIsNotNone(cmd)
        self.assertEqual(cmd[0], "uv")
        self.assertEqual(cmd[1], "run")
        self.assertIn("--with", cmd)
        self.assertIn("ruamel.yaml>=0.18", cmd)
        python_idx = cmd.index("python")
        self.assertEqual(cmd[python_idx:], ["python", "-c", "import alongkit"])

    def test_inline_reexec_cached_venv(self):
        """When sys.argv[0] == '-c' and cached venv is current, reexecs into venv python."""
        captured = {}
        python = self._plant_venv(self.venv_dir, bootstrap.RUNTIME_DEPENDENCIES)

        def fake_reexec(command, missing_exit_code, **_kwargs):
            captured["command"] = command
            raise SystemExit(0)

        with mock.patch.object(bootstrap, "have_deps", return_value=False), \
                mock.patch.object(bootstrap, "_reexec", side_effect=fake_reexec), \
                mock.patch("shutil.which", return_value="uv"), \
                mock.patch.dict(os.environ, {bootstrap.VENV_ENV: self.venv_dir}), \
                mock.patch.object(sys, "argv", ["-c", "-c", "print(42)"]):
            os.environ.pop(bootstrap.GUARD_ENV, None)
            with self.assertRaises(SystemExit):
                bootstrap.ensure_deps()

        cmd = captured.get("command")
        self.assertIsNotNone(cmd)
        self.assertEqual(cmd[0], python)
        self.assertEqual(cmd[1:], ["-c", "print(42)"])

    def test_inline_missing_uv_aborts_cleanly(self):
        """When sys.argv[0] == '-c' and uv is missing, exits with missing_exit_code."""
        with mock.patch.object(bootstrap, "have_deps", return_value=False), \
                mock.patch("shutil.which", return_value=None), \
                mock.patch.dict(os.environ, {bootstrap.VENV_ENV: self.venv_dir}), \
                mock.patch.object(sys, "argv", ["-c", "-c", "import alongkit"]):
            os.environ.pop(bootstrap.GUARD_ENV, None)
            with self.assertRaises(SystemExit) as ctx:
                bootstrap.ensure_deps(missing_exit_code=2)
            self.assertEqual(ctx.exception.code, 2)

    def test_inline_reexec_with_sys_orig_argv(self):
        """When invoked via CPython -c, sys.argv is ['-c', 'arg'] and code lives in sys.orig_argv."""
        captured = {}
        python = self._plant_venv(self.venv_dir, bootstrap.RUNTIME_DEPENDENCIES)

        def fake_reexec(command, missing_exit_code, **_kwargs):
            captured["command"] = command
            raise SystemExit(0)

        with mock.patch.object(bootstrap, "have_deps", return_value=False), \
                mock.patch.object(bootstrap, "_reexec", side_effect=fake_reexec), \
                mock.patch("shutil.which", return_value="uv"), \
                mock.patch.dict(os.environ, {bootstrap.VENV_ENV: self.venv_dir}), \
                mock.patch.object(sys, "argv", ["-c", "foo_arg"]), \
                mock.patch.object(sys, "orig_argv", ["python", "-c", "import sys; print(sys.argv)", "foo_arg"]):
            os.environ.pop(bootstrap.GUARD_ENV, None)
            with self.assertRaises(SystemExit):
                bootstrap.ensure_deps()

        cmd = captured.get("command")
        self.assertIsNotNone(cmd)
        self.assertEqual(cmd[0], python)
        self.assertEqual(cmd[1:], ["-c", "import sys; print(sys.argv)", "foo_arg"])


if __name__ == "__main__":
    unittest.main()
