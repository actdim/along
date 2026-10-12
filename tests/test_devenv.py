#!/usr/bin/env python3
"""
tests/test_devenv.py - Unit tests for alongkit.devenv dev environment setup.
[feat--dev-environment-setup-and-editable-install]
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

from alongkit import devenv, textio
import hermetic


class TestDevEnvironmentSetup(unittest.TestCase):
    """Verifies alongkit.devenv automated setup and editable links."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = self.tmp.name
        self.scripts_dir = os.path.join(self.root, "scripts")
        self.alongkit_dir = os.path.join(self.scripts_dir, "alongkit")
        os.makedirs(self.alongkit_dir, exist_ok=True)
        textio.write_text(os.path.join(self.alongkit_dir, "__init__.py"), "__version__ = '1.0'\n")

    def tearDown(self):
        self.tmp.cleanup()

    def test_find_site_packages(self):
        """Locates site-packages directory on Windows or POSIX."""
        venv = os.path.join(self.root, ".venv")
        if sys.platform == "win32":
            sp = os.path.join(venv, "Lib", "site-packages")
        else:
            sp = os.path.join(venv, "lib", "python3.11", "site-packages")
        os.makedirs(sp, exist_ok=True)
        found = devenv.find_site_packages(venv)
        self.assertEqual(os.path.normpath(found), os.path.normpath(sp))

    def test_setup_dev_environment_creates_venv_and_pth(self):
        """Creates .venv and installs actdim_along.pth link pointing to scripts/."""
        # Mock subprocess.run for uv / venv creation to keep test lightweight
        venv_dir = os.path.join(self.root, ".venv")
        if sys.platform == "win32":
            sp = os.path.join(venv_dir, "Lib", "site-packages")
            py = os.path.join(venv_dir, "Scripts", "python.exe")
        else:
            sp = os.path.join(venv_dir, "lib", "python3.11", "site-packages")
            py = os.path.join(venv_dir, "bin", "python")
        os.makedirs(sp, exist_ok=True)
        os.makedirs(os.path.dirname(py), exist_ok=True)
        textio.write_text(py, "")

        def fake_run(cmd, *args, **kwargs):
            class Res:
                returncode = 0
                stdout = ""
                stderr = ""
            return Res()

        with mock.patch("subprocess.run", side_effect=fake_run), \
                mock.patch("shutil.which", return_value="uv"):
            ok, msg = devenv.setup_dev_environment(self.root, quiet=True)
            self.assertTrue(ok)
            self.assertIn("Development environment initialized", msg)

        pth = os.path.join(sp, "actdim_along.pth")
        self.assertTrue(os.path.isfile(pth))
        content = textio.read_text(pth)
        self.assertIn(self.scripts_dir, content)

    def test_setup_dev_environment_reinstall(self):
        """Reinstall flag removes existing .venv directory."""
        venv_dir = os.path.join(self.root, ".venv")
        os.makedirs(venv_dir, exist_ok=True)
        marker = os.path.join(venv_dir, "old_marker.txt")
        textio.write_text(marker, "old")

        with mock.patch("subprocess.run") as mock_run:
            class Res:
                returncode = 1
                stdout = ""
                stderr = "Simulated failure"
            mock_run.return_value = Res()
            # Fails at creation step, but proves old .venv was cleaned up
            ok, msg = devenv.setup_dev_environment(self.root, reinstall=True, quiet=True)
            self.assertFalse(ok)
            self.assertFalse(os.path.isfile(marker))


if __name__ == "__main__":
    unittest.main()
