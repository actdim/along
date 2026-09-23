#!/usr/bin/env python3
"""
test_graph_skills.py - Contract Tests for code-review-graph User-Facing Skills.

Verifies:
1. Skill manifest frontmatter validity (along-graph-impact, along-graph-arch).
2. Command mappings and routing in along_exec.py.
3. Argument parsing, output formatting, and stream contracts.
4. Graceful offline degradation when uvx / code-review-graph is unavailable.
5. Integration with bootstrap.ensure_deps().
"""

import os
import sys
import unittest
import tempfile
import json
from unittest.mock import patch

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(REPO_ROOT, "scripts"))

from alongkit import bootstrap
bootstrap.ensure_deps()

from alongkit import frontmatter, repo


class TestGraphSkillsContracts(unittest.TestCase):
    """Test suite for along-graph-impact and along-graph-arch skills and engines."""

    def test_01_skill_manifests_validity(self):
        """Verify YAML frontmatter for along-graph-impact and along-graph-arch."""
        for skill_name in ("along-graph-impact", "along-graph-arch"):
            manifest_path = os.path.join(REPO_ROOT, "skills", skill_name, "SKILL.md")
            self.assertTrue(os.path.isfile(manifest_path), f"Missing manifest for {skill_name}")
            with open(manifest_path, "r", encoding="utf-8") as f:
                content = f.read()

            self.assertTrue(content.startswith("---"), f"{skill_name} manifest must start with '---'")
            fm, body = frontmatter.parse(content)
            self.assertEqual(fm.get("name"), skill_name)
            self.assertTrue(fm.get("description"), f"{skill_name} must have non-empty description")
            self.assertIn("along", fm["description"].lower())
            self.assertTrue(len(body.strip()) > 50, f"{skill_name} body must not be empty")

    def test_02_along_exec_tool_mappings(self):
        """Verify CLI routing and aliases in along_exec.TOOL_MAPPINGS."""
        import along_exec

        expected_mappings = {
            "graph-impact": "along_graph_impact.py",
            "graphimpact": "along_graph_impact.py",
            "graph-arch": "along_graph_arch.py",
            "grapharch": "along_graph_arch.py",
        }
        for cmd, script in expected_mappings.items():
            self.assertIn(cmd, along_exec.TOOL_MAPPINGS)
            self.assertEqual(along_exec.TOOL_MAPPINGS[cmd], script)

    def test_03_scripts_ensure_deps_contract(self):
        """Verify that both scripts invoke bootstrap.ensure_deps()."""
        for script_name in ("along_graph_impact.py", "along_graph_arch.py"):
            script_path = os.path.join(REPO_ROOT, "scripts", script_name)
            self.assertTrue(os.path.isfile(script_path), f"Missing script {script_name}")
            with open(script_path, "r", encoding="utf-8") as f:
                content = f.read()
            self.assertIn("bootstrap.ensure_deps()", content, f"{script_name} must call ensure_deps()")

    def test_04_impact_engine_offline_degradation(self):
        """Verify along_graph_impact degrades gracefully to static search when uvx is absent."""
        import along_graph_impact

        with patch("shutil.which", return_value=None):
            report = along_graph_impact.analyze_impact(
                repo_root=REPO_ROOT,
                target="along_graph_check",
                optional=True,
            )
            self.assertEqual(report["status"], "degraded")
            self.assertEqual(report["mode"], "degraded_static")
            self.assertIn("degraded", report["summary"].lower())
            self.assertIsInstance(report["callers"], list)
            self.assertIn("scripts/along_exec.py", report["callers"])
            self.assertIsInstance(report["candidate_tests"], list)
            self.assertTrue(len(report["candidate_tests"]) > 0)

    def test_05_architecture_engine_offline_degradation(self):
        """Verify along_graph_arch degrades gracefully to static analysis when uvx is absent."""
        import along_graph_arch

        with patch("shutil.which", return_value=None):
            report = along_graph_arch.analyze_architecture(
                repo_root=REPO_ROOT,
                detail_level="standard",
                optional=True,
            )
            self.assertEqual(report["status"], "degraded")
            self.assertEqual(report["mode"], "degraded_static")
            self.assertIn("degraded", report["summary"].lower())
            self.assertIsInstance(report["communities"], list)
            self.assertTrue(len(report["communities"]) >= 3)
            self.assertIsInstance(report["hub_nodes"], list)

    def test_06_impact_engine_candidate_tests_and_docs_discovery(self):
        """Verify candidate tests and doc discovery heuristics."""
        import along_graph_impact

        tests = along_graph_impact.find_candidate_tests_static(REPO_ROOT, "along_graph_check")
        self.assertIn("tests/test_skills_and_scripts.py", tests)

        docs = along_graph_impact.find_affected_docs_static(REPO_ROOT, "along-team")
        self.assertTrue(any("skills-reference" in d for d in docs))


if __name__ == "__main__":
    unittest.main()
