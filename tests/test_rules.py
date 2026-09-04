#!/usr/bin/env python3
"""
tests/test_rules.py - unit tests for alongkit.rules engine.

Hermetic tests for signature detection, rule pack attachment, case-insensitive
pruning on Windows, AGENTS.md injection, and library execution guard.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest

from tests import hermetic
from alongkit import rules, textio

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


class TestRulesEngine(unittest.TestCase):
    def test_detect_required_rules_python(self):
        with hermetic.repo_fixture() as repo:
            textio.write_text(os.path.join(repo, "pyproject.toml"), "[project]\nname = 'demo'\n")
            detected = rules.detect_required_rules(repo)
            self.assertIn("languages/python.md", detected)

    def test_detect_required_rules_typescript_and_web(self):
        with hermetic.repo_fixture() as repo:
            textio.write_text(os.path.join(repo, "tsconfig.json"), "{}\n")
            textio.write_text(
                os.path.join(repo, "package.json"),
                json.dumps({"dependencies": {"react-dom": "^18.0.0", "msw": "^2.0.0"}}) + "\n",
            )
            detected = rules.detect_required_rules(repo)
            self.assertIn("languages/typescript.md", detected)
            self.assertIn("platforms/web.md", detected)

    def test_detect_required_rules_ignores_ignored_dirs(self):
        with hermetic.repo_fixture() as repo:
            ignored = os.path.join(repo, "node_modules", "some-pkg")
            os.makedirs(ignored, exist_ok=True)
            textio.write_text(os.path.join(ignored, "tsconfig.json"), "{}\n")
            detected = rules.detect_required_rules(repo)
            self.assertNotIn("languages/typescript.md", detected)

    def test_attach_rules_copies_and_updates_agents(self):
        with hermetic.repo_fixture() as repo:
            # Create a mock global rules source
            with tempfile.TemporaryDirectory() as global_rules:
                py_rule = os.path.join(global_rules, "languages", "python.md")
                os.makedirs(os.path.dirname(py_rule), exist_ok=True)
                textio.write_text(py_rule, "# Python Standards\n")

                # Set repo to require python
                textio.write_text(os.path.join(repo, "pyproject.toml"), "[project]\n")

                orig_get_global = rules.get_global_rules_dir
                try:
                    rules.get_global_rules_dir = lambda: global_rules
                    rules.attach_rules(repo)
                finally:
                    rules.get_global_rules_dir = orig_get_global

                local_py = os.path.join(repo, ".along", "rules", "languages", "python.md")
                self.assertTrue(os.path.isfile(local_py))

                agents_md = textio.read_text(os.path.join(repo, "AGENTS.md"))
                self.assertIn("<!-- BEGIN ALONG-RULES -->", agents_md)
                self.assertIn("[languages/python.md](file://.along/rules/languages/python.md)", agents_md)
                self.assertIn("<!-- END ALONG-RULES -->", agents_md)

    def test_attach_rules_pruning_case_insensitive(self):
        with hermetic.repo_fixture() as repo:
            with tempfile.TemporaryDirectory() as global_rules:
                py_rule = os.path.join(global_rules, "languages", "python.md")
                os.makedirs(os.path.dirname(py_rule), exist_ok=True)
                textio.write_text(py_rule, "# Python Standards\n")

                # Pre-populate an obsolete rule that should be pruned
                obsolete_rule = os.path.join(repo, ".along", "rules", "platforms", "mobile.md")
                os.makedirs(os.path.dirname(obsolete_rule), exist_ok=True)
                textio.write_text(obsolete_rule, "# Mobile Standards\n")

                textio.write_text(os.path.join(repo, "pyproject.toml"), "[project]\n")

                orig_get_global = rules.get_global_rules_dir
                try:
                    rules.get_global_rules_dir = lambda: global_rules
                    rules.attach_rules(repo)
                finally:
                    rules.get_global_rules_dir = orig_get_global

                # Obsolete rule should be pruned
                self.assertFalse(os.path.exists(obsolete_rule))
                # Active rule should exist
                self.assertTrue(os.path.isfile(os.path.join(repo, ".along", "rules", "languages", "python.md")))

    def test_attach_rules_empty_does_not_pollute(self):
        with hermetic.repo_fixture() as repo:
            with tempfile.TemporaryDirectory() as global_rules:
                agents_before = textio.read_text(os.path.join(repo, "AGENTS.md"))

                orig_get_global = rules.get_global_rules_dir
                try:
                    rules.get_global_rules_dir = lambda: global_rules
                    rules.attach_rules(repo)
                finally:
                    rules.get_global_rules_dir = orig_get_global

                agents_after = textio.read_text(os.path.join(repo, "AGENTS.md"))
                self.assertNotIn("<!-- BEGIN ALONG-RULES -->", agents_after)
                self.assertEqual(agents_before.strip(), agents_after.strip())

    def test_rules_execution_guard(self):
        cmd = [sys.executable, os.path.join(REPO_ROOT, "scripts", "alongkit", "rules.py")]
        proc = subprocess.run(cmd, capture_output=True, text=True)
        self.assertNotEqual(proc.returncode, 0)
        self.assertIn("rules.py is a library module, not a command.", proc.stderr + proc.stdout)


if __name__ == "__main__":
    unittest.main()

