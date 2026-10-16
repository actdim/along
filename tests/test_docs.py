#!/usr/bin/env python3
"""tests/test_docs.py - Unit tests for documentation rules and troubleshooting guidance."""

import os
import unittest

from alongkit import textio

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


class TestDocumentationRules(unittest.TestCase):
    def test_agents_md_prohibits_shell_code_probing(self):
        """AGENTS.md and skills/along-init/protocol.md must prohibit ad-hoc python -c probing."""
        agents_path = os.path.join(REPO_ROOT, "AGENTS.md")
        protocol_path = os.path.join(REPO_ROOT, "skills", "along-init", "protocol.md")

        for path in (agents_path, protocol_path):
            content = textio.read_text(path)
            self.assertIn("No Ad-Hoc Shell Code Probing", content)
            self.assertIn("python -c", content)
            self.assertIn("alongkit", content)
            self.assertIn("view_file", content)
            self.assertIn("along graph-", content)

    def test_agents_md_prohibits_cli_reverse_engineering(self):
        """AGENTS.md and skills/along-init/protocol.md must prohibit reading Along engine source code."""
        agents_path = os.path.join(REPO_ROOT, "AGENTS.md")
        protocol_path = os.path.join(REPO_ROOT, "skills", "along-init", "protocol.md")

        for path in (agents_path, protocol_path):
            content = textio.read_text(path)
            self.assertIn("CLI Black-Box Invariance", content)
            self.assertIn("opaque black-box", content)
            self.assertIn("alongkit", content)

    def test_along_team_skill_documents_anti_pattern(self):
        """skills/along-team/SKILL.md must document the anti-pattern shell code probing."""
        skill_path = os.path.join(REPO_ROOT, "skills", "along-team", "SKILL.md")
        content = textio.read_text(skill_path)

        self.assertIn("Ad-Hoc Shell Code Probing", content)
        self.assertIn("python -c", content)
        self.assertIn("alongkit", content)
        self.assertIn("view_file", content)
        self.assertIn("along graph-", content)

    def test_troubleshooting_guide_exists_and_explains_packaging(self):
        """docs/topic--troubleshooting.md must exist and explain packaging structure and anti-patterns."""
        guide_path = os.path.join(REPO_ROOT, "docs", "topic--troubleshooting.md")
        self.assertTrue(os.path.isfile(guide_path), "docs/topic--troubleshooting.md must exist")

        content = textio.read_text(guide_path)
        self.assertIn("alongkit", content)
        self.assertIn("scripts/", content)
        self.assertIn("PEP 723", content)
        self.assertIn("uv", content)
        self.assertIn("python -c", content)
        self.assertIn("view_file", content)
        self.assertIn("along graph-", content)

    def test_troubleshooting_registered_in_index(self):
        """docs/INDEX.md must index topic--troubleshooting.md."""
        index_path = os.path.join(REPO_ROOT, "docs", "INDEX.md")
        content = textio.read_text(index_path)
        self.assertIn("topic--troubleshooting.md", content)


if __name__ == "__main__":
    unittest.main()
