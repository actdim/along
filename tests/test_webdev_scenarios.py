#!/usr/bin/env python3
"""tests/test_webdev_scenarios.py - Hermetic tests for scenario schema, results, evidence, and failure filing."""

from __future__ import annotations

import os
import shutil
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "scripts")))

from alongkit import repochecks
from alongkit.webdev import evidence, failures, results, runner, schema


EXTENDED_SCENARIO_EXAMPLE = """
meta: {issue: feat--chat-composer-layout, title: "Composer and player layout pass"}
services: [api, web, cors-static]
auth:
  dev:
    - {goto: "/dev-login"}
    - {click: {role: button, name: "Dev sign-in"}}
    - {wait_for: {url: "/app"}}
defaults:
  origins: ["http://localhost:5173", "http://localhost:8000", "http://localhost:8099"]
  storage: {localStorage: {"app.theme": "system"}}
checks:
  - id: C1
    title: Composer stays above the fixed footer while growing
    ac: AC-3
    matrix: {viewport: [mobile-375x812, mobile-390x844, desktop-1440x900], theme: [light, dark]}
    steps:
      - {use_auth: dev}
      - {goto: "/app/chat"}
      - {fill: {role: textbox, name: "Message"}, value: "one"}
      - {press: "Shift+Enter", repeat: 4}
      - {eval: "above('[data-testid=composer]', 'footer')", expect: {"$": true}}
      - {eval: "covered_by({role: 'button', name: 'Send'})", expect: {"$.self": true}}
      - {eval: "overflow_x()", expect: {"$.overflow": false}}
      - {screenshot: {of: {test_id: composer}}}
  - id: C2
    title: Upload error is shown when the server fails
    steps:
      - {route: {url: "/api/upload", fulfill: {status: 500}}}
      - {upload: {label: "Attach"}, generate: {kind: png, size_kb: 200, name: "a.png"}}
      - {assert_text: {role: alert}, contains: "failed"}
  - id: C3
    title: Media session position reaches the OS flyout
    not_run: "platform-limit:os-media-flyout"
"""


class TestScenarioSchemaValidation(unittest.TestCase):
    """Schema validation tests (REQ-9)."""

    def test_extended_scenario_validates(self):
        data = schema.load_scenario(EXTENDED_SCENARIO_EXAMPLE)
        self.assertEqual(data["meta"]["issue"], "feat--chat-composer-layout")
        self.assertEqual(len(data["checks"]), 3)

    def test_invalid_scenario_missing_meta(self):
        invalid = "checks: [{id: C1, title: test}]"
        with self.assertRaises(ValueError) as ctx:
            schema.load_scenario(invalid)
        self.assertIn("meta", str(ctx.exception))


class TestEvidenceAndArtifactIsolation(unittest.TestCase):
    """Artifact directory and untracked exports checks (REQ-8)."""

    def setUp(self):
        self.temp_repo = tempfile.mkdtemp()
        self.state_dir = os.path.join(self.temp_repo, ".along")
        os.makedirs(self.state_dir, exist_ok=True)

    def tearDown(self):
        shutil.rmtree(self.temp_repo, ignore_errors=True)

    def test_artifacts_dir_creates_self_ignoring_gitignore(self):
        art_dir = evidence.ensure_artifacts_dir(self.temp_repo)
        gi_path = os.path.join(art_dir, ".gitignore")
        self.assertTrue(os.path.isfile(gi_path))
        with open(gi_path, "r", encoding="utf-8") as f:
            content = f.read()
        self.assertIn("*\n!.gitignore", content)

    def test_deterministic_evidence_filename(self):
        name = evidence.evidence_filename("C1", "mobile-375x812", "dark", "composer", "png")
        self.assertEqual(name, "C1--mobile-375x812--dark--composer.png")

    def test_repochecks_flags_staged_artifacts(self):
        paths = [".along/artifacts/webdev/feat--ui/run-1/shot.png", "src/app.py"]
        findings = repochecks.check_untracked_exports(paths, lambda p: "", {})
        flagged = [f[0] for f in findings]
        self.assertIn(".along/artifacts/webdev/feat--ui/run-1/shot.png", flagged)
        self.assertNotIn("src/app.py", flagged)


class TestResultsMarkdownAndIssueReplace(unittest.TestCase):
    """Result formatting and issue body replacement (REQ-11)."""

    def setUp(self):
        self.temp_repo = tempfile.mkdtemp()
        self.issues_dir = os.path.join(self.temp_repo, ".along", "ISSUES")
        os.makedirs(self.issues_dir, exist_ok=True)

    def tearDown(self):
        shutil.rmtree(self.temp_repo, ignore_errors=True)

    def test_format_results_markdown_table(self):
        raw_res = [
            {
                "check_id": "C1",
                "title": "Composer Layout",
                "ac": "AC-1",
                "viewport": "mobile-375x812",
                "theme": "dark",
                "status": "PASS",
                "reason": "",
                "evidence": ["shot.png"],
            }
        ]
        md = results.format_results_markdown("run-100", raw_res)
        self.assertIn("## Browser Verification Results", md)
        self.assertIn("| **C1**: Composer Layout | AC-1 | mobile-375x812 | dark | **PASS** | - | [shot.png](shot.png) |", md)

    def test_update_issue_results_replaces_section(self):
        issue_path = os.path.join(self.issues_dir, "feat--my-feature.md")
        initial_content = (
            "---\nprotocol: along\nslug: my-feature\ntype: feat\nstatus: in-progress\n---\n\n"
            "# Feature Title\n\n"
            "## Browser Verification Results\nOld results table from run-1\n\n"
            "## Acceptance Criteria\n- [ ] AC1\n"
        )
        with open(issue_path, "w", encoding="utf-8") as f:
            f.write(initial_content)

        new_results = "## Browser Verification Results\nNew run results for run-2\n\n"
        ok = results.update_issue_results(self.temp_repo, "my-feature", new_results)
        self.assertTrue(ok)

        with open(issue_path, "r", encoding="utf-8") as f:
            updated = f.read()

        self.assertIn("New run results for run-2", updated)
        self.assertNotIn("Old results table from run-1", updated)
        self.assertIn("## Acceptance Criteria", updated)


class TestFailureFiling(unittest.TestCase):
    """Automated failure filing into bug issues (REQ-11)."""

    def setUp(self):
        self.temp_repo = tempfile.mkdtemp()
        self.issues_dir = os.path.join(self.temp_repo, ".along", "ISSUES")
        os.makedirs(self.issues_dir, exist_ok=True)

    def tearDown(self):
        shutil.rmtree(self.temp_repo, ignore_errors=True)

    def test_file_failures_creates_bug_issue(self):
        failed_res = [
            {
                "check_id": "C2",
                "title": "Upload Failure Handling",
                "reason": "Expected alert text 'failed', got '500 Internal Server Error'",
                "steps": [{"action": "click", "selector": "#upload"}],
                "evidence": ["evidence/fail.png"],
            }
        ]
        created = failures.file_failures(self.temp_repo, "feat--chat-upload", failed_res)
        self.assertEqual(len(created), 1)
        created_path = created[0]
        self.assertTrue(os.path.isfile(created_path))
        with open(created_path, "r", encoding="utf-8") as f:
            content = f.read()

        self.assertIn("type: bug", content)
        self.assertIn("related: [feat--chat-upload]", content)
        self.assertIn("Expected alert text 'failed'", content)


class TestScenarioExecutionExitCodes(unittest.TestCase):
    """Hermetic execution runner exit codes (REQ-9)."""

    def setUp(self):
        self.temp_repo = tempfile.mkdtemp()
        self.state_dir = os.path.join(self.temp_repo, ".along")
        os.makedirs(self.state_dir, exist_ok=True)
        os.environ["ALONG_WEBDEV_HERMETIC"] = "1"

    def tearDown(self):
        os.environ.pop("ALONG_WEBDEV_HERMETIC", None)
        shutil.rmtree(self.temp_repo, ignore_errors=True)

    def test_all_pass_returns_zero(self):
        scenario = {
            "meta": {"issue": "feat--test", "title": "Test Pass"},
            "checks": [
                {
                    "id": "C1",
                    "title": "Check 1",
                    "steps": [{"action": "eval", "expr": "1 + 1"}],
                }
            ],
        }
        code, rep = runner.run_scenario(self.temp_repo, scenario)
        self.assertEqual(code, 0)
        self.assertEqual(rep["summary"]["passed"], 1)

    def test_schema_error_returns_two(self):
        code, _ = runner.run_scenario(self.temp_repo, "not a valid scenario text")
        self.assertEqual(code, 2)


if __name__ == "__main__":
    unittest.main()
