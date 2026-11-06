#!/usr/bin/env python3
"""
tests/test_lint_unstaged.py - Unstaged file linting and recursive subproject doctor audit.
[feat--lint-worktree-and-doctor-subprojects]
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
import unittest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPTS_DIR = os.path.join(REPO_ROOT, "scripts")
if SCRIPTS_DIR not in sys.path:
    sys.path.insert(0, SCRIPTS_DIR)

from alongkit import bootstrap
bootstrap.ensure_deps()

from alongkit import gitgates, migration, version
from alongkit.commands.doctor import audit_subproject_protocol_versions

EXEC = os.path.join(SCRIPTS_DIR, "along_exec.py")
UPDATE = os.path.join(SCRIPTS_DIR, "along_update.py")


def _tlu_write(root: str, rel: str, text: str) -> str:
    path = os.path.join(root, *rel.split("/"))
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as h:
        h.write(text)
    return path


def _tlu_git(cwd: str, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git", *args],
        cwd=cwd,
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=True,
    )


class TestLintUnstagedAndDoctorSubprojects(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="along-tlu-")
        _tlu_git(self.tmp, "init", "-q")
        _tlu_git(self.tmp, "config", "user.name", "Along Tester")
        _tlu_git(self.tmp, "config", "user.email", "tester@along.local")

        # Root protocol files
        _tlu_write(self.tmp, "AGENTS.md", "# Root Agents\n<!-- BEGIN ALONG-PROTOCOL root -->\n# ALONG-PROTOCOL\n<!-- END ALONG-PROTOCOL -->\n")
        _tlu_write(self.tmp, ".along/.protocol-version", f"{version.CURRENT_PROTOCOL_VERSION}\n")
        _tlu_write(self.tmp, ".along/ISSUES.md", "# Active Issues\n")
        _tlu_git(self.tmp, "add", "-A")
        _tlu_git(self.tmp, "commit", "-m", "init root", "-q")

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_check_files_detects_typography_without_staging(self):
        # Create an unstaged file with a forbidden em-dash (\u2014)
        draft_path = _tlu_write(self.tmp, "docs/draft.md", "# Title \u2014 with em dash\n")
        # Verify git status shows it as untracked
        violations = gitgates.check_files(self.tmp, ["docs/draft.md"])
        typography_viols = [v for v in violations if v.gate == "typography"]
        self.assertTrue(len(typography_viols) > 0)
        self.assertIn("em dash", typography_viols[0].message)

    def test_check_files_passes_on_clean_unstaged_file(self):
        clean_path = _tlu_write(self.tmp, "docs/clean.md", "# Clean ASCII Title\nClean content.\n")
        violations = gitgates.check_files(self.tmp, ["docs/clean.md"])
        self.assertEqual(violations, [])

    def test_cli_lint_specific_path_fails_on_typography(self):
        _tlu_write(self.tmp, "plans/draft.md", "# Plan \u2014 with em dash\n")
        res = subprocess.run(
            [sys.executable, EXEC, "lint", "plans/draft.md"],
            cwd=self.tmp,
            capture_output=True,
            text=True,
            encoding="utf-8",
        )
        self.assertNotEqual(res.returncode, 0)
        self.assertIn("typography", res.stderr + res.stdout)

    def test_cli_lint_worktree_catches_untracked_modifications(self):
        _tlu_write(self.tmp, "src/untracked.py", "# Comment \u2013 with en dash\n")
        res = subprocess.run(
            [sys.executable, EXEC, "lint", "--worktree"],
            cwd=self.tmp,
            capture_output=True,
            text=True,
            encoding="utf-8",
        )
        self.assertNotEqual(res.returncode, 0)
        self.assertIn("typography", res.stderr + res.stdout)

    def test_audit_subproject_protocol_versions_detects_skew(self):
        sub_dir = os.path.join(self.tmp, "packages", "ui-core")
        _tlu_write(sub_dir, "AGENTS.md", "# Sub Agents\n")
        _tlu_write(sub_dir, ".along/.protocol-version", "4.5.4\n")
        _tlu_write(sub_dir, ".along/ISSUES.md", "# Active Issues\n")

        results = audit_subproject_protocol_versions(self.tmp)
        sub_entry = next((r for r in results if "packages/ui-core" in r["path"] or "packages\\ui-core" in r["path"]), None)
        self.assertIsNotNone(sub_entry)
        self.assertEqual(sub_entry["version"], "4.5.4")
        self.assertEqual(sub_entry["mismatch"], "True")

    def test_along_doctor_warns_on_protocol_version_skew(self):
        sub_dir = os.path.join(self.tmp, "packages", "service-a")
        _tlu_write(sub_dir, "AGENTS.md", "# Sub Agents\n")
        _tlu_write(sub_dir, ".along/.protocol-version", "4.0.0\n")
        _tlu_write(sub_dir, ".along/ISSUES.md", "# Active Issues\n")

        res = subprocess.run(
            [sys.executable, EXEC, "doctor"],
            cwd=self.tmp,
            capture_output=True,
            text=True,
            encoding="utf-8",
        )
        output = res.stdout + res.stderr
        self.assertIn("mismatch with root", output)
        self.assertIn("along update --recursive", output)

    def test_along_update_recursive_aligns_subprojects(self):
        sub_dir = os.path.join(self.tmp, "packages", "service-b")
        _tlu_write(sub_dir, "AGENTS.md", "<!-- BEGIN ALONG-PROTOCOL root -->\n# ALONG-PROTOCOL\n<!-- END ALONG-PROTOCOL -->\n")
        _tlu_write(sub_dir, ".along/.protocol-version", "4.0.0\n")
        _tlu_write(sub_dir, ".along/ISSUES.md", "# Active Issues\n")

        # Run along update --recursive
        res = subprocess.run(
            [sys.executable, UPDATE, self.tmp, "--recursive", "--local-only", "--no-hooks"],
            cwd=self.tmp,
            capture_output=True,
            text=True,
            encoding="utf-8",
        )
        self.assertEqual(res.returncode, 0, res.stdout + res.stderr)
        aligned_ver = migration.read_state(os.path.join(sub_dir, ".along"))
        self.assertEqual(aligned_ver, version.CURRENT_PROTOCOL_VERSION)


if __name__ == "__main__":
    unittest.main()
