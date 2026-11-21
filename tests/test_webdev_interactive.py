#!/usr/bin/env python3
"""tests.test_webdev_interactive - Unit tests for webdev interactive session and checklists (REQ-10)."""

import json
import os
import shutil
import tempfile
import unittest

from alongkit.webdev import checklist, daemon, runner, schema


SAMPLE_CHECKLIST_MD = """# Verification Checklist

Some introductory remarks.

## Browser Verification

- [ ] C1: on 375x812 the composer stays above the fixed footer (AC-1)
- [ ] C2: [AC-2] dark theme switch applies immediately
- [ ] C3: error banner is displayed when network drops
"""


class TestChecklistCompiler(unittest.TestCase):
    """Checklist markdown parser and compiler tests (REQ-10)."""

    def setUp(self):
        self.temp_repo = tempfile.mkdtemp()
        self.issues_dir = os.path.join(self.temp_repo, ".along", "ISSUES")
        os.makedirs(self.issues_dir, exist_ok=True)

    def tearDown(self):
        shutil.rmtree(self.temp_repo, ignore_errors=True)

    def test_parse_checklist_markdown(self):
        items = checklist.parse_checklist_markdown(SAMPLE_CHECKLIST_MD)
        self.assertEqual(len(items), 3)

        self.assertEqual(items[0]["id"], "C1")
        self.assertEqual(items[0]["ac"], "AC-1")
        self.assertEqual(items[0]["viewport_hint"], "mobile-375x812")

        self.assertEqual(items[1]["id"], "C2")
        self.assertEqual(items[1]["ac"], "AC-2")
        self.assertEqual(items[1]["theme_hint"], "dark")

        self.assertEqual(items[2]["id"], "C3")
        self.assertIsNone(items[2]["ac"])

    def test_compile_checklist_from_file_and_uncompiled_status(self):
        chk_file = os.path.join(self.temp_repo, "checklist.md")
        with open(chk_file, "w", encoding="utf-8") as f:
            f.write(SAMPLE_CHECKLIST_MD)

        out_scenario = os.path.join(self.temp_repo, "compiled_scenario.yaml")
        scenario_data = checklist.compile_checklist(self.temp_repo, chk_file, output_path=out_scenario)

        self.assertTrue(os.path.isfile(out_scenario))
        self.assertEqual(len(scenario_data["checks"]), 3)
        self.assertEqual(scenario_data["checks"][0]["steps"], [])

        # Schema validates compiled scenario
        validated = schema.load_scenario(out_scenario)
        self.assertEqual(len(validated["checks"]), 3)

        # Running compiled scenario without filled steps marks checks as NOT RUN not-compiled
        os.environ["ALONG_WEBDEV_HERMETIC"] = "1"
        try:
            exit_code, rep = runner.run_scenario(self.temp_repo, out_scenario)
            self.assertEqual(exit_code, 0)
            for res in rep["results"]:
                self.assertEqual(res["status"], "NOT RUN")
                self.assertEqual(res["reason"], "not-compiled")
        finally:
            os.environ.pop("ALONG_WEBDEV_HERMETIC", None)

    def test_compile_checklist_from_issue_section(self):
        issue_path = os.path.join(self.issues_dir, "feat--chat-ui.md")
        issue_content = (
            "---\nprotocol: along\nslug: chat-ui\ntype: feat\nstatus: in-progress\n---\n\n"
            "# Chat UI Feature\n\n"
            "## Browser Verification\n"
            "- [ ] C1: composer expands smoothly (AC-1)\n"
            "- [ ] C2: attachments list displays chips\n"
        )
        with open(issue_path, "w", encoding="utf-8") as f:
            f.write(issue_content)

        scenario_data = checklist.compile_checklist(self.temp_repo, "chat-ui")
        self.assertEqual(scenario_data["meta"]["issue"], "chat-ui")
        self.assertEqual(len(scenario_data["checks"]), 2)
        self.assertEqual(scenario_data["checks"][0]["id"], "C1")
        self.assertEqual(scenario_data["checks"][0]["ac"], "AC-1")


class TestInteractiveSessionDaemon(unittest.TestCase):
    """Hermetic tests for interactive session daemon and transcript recorder (REQ-10)."""

    def setUp(self):
        self.temp_repo = tempfile.mkdtemp()
        self.sdir = os.path.join(self.temp_repo, ".along")
        os.makedirs(self.sdir, exist_ok=True)
        os.environ["ALONG_WEBDEV_HERMETIC"] = "1"

    def tearDown(self):
        daemon.session_stop(self.temp_repo)
        shutil.rmtree(self.temp_repo, ignore_errors=True)
        os.environ.pop("ALONG_WEBDEV_HERMETIC", None)

    def test_daemon_lifecycle_token_auth_and_recording(self):
        # 1. Start daemon
        start_res = daemon.session_start(self.temp_repo, issue_key="test-feature")
        self.assertTrue(start_res["ok"])
        sess_info = daemon.read_session_info(self.temp_repo)
        self.assertIsNotNone(sess_info)
        port = sess_info["port"]
        token = sess_info["token"]
        self.assertTrue(port > 0)
        self.assertEqual(len(token), 32)

        # 2. Check status via helper
        status_res = daemon.session_status(self.temp_repo)
        self.assertTrue(status_res["ok"])
        self.assertTrue(status_res["alive"])
        self.assertEqual(status_res["steps_count"], 0)

        # 3. Unauthorized access rejection
        import urllib.request
        req_unauth = urllib.request.Request(f"http://127.0.0.1:{port}/status")
        with self.assertRaises(urllib.error.HTTPError) as ctx:
            urllib.request.urlopen(req_unauth)
        self.assertEqual(ctx.exception.code, 401)

        # 4. Execute single step
        step1 = {"goto": "/login"}
        step_res = daemon.session_step(self.temp_repo, step1)
        self.assertTrue(step_res["ok"])
        self.assertEqual(step_res["transcript_index"], 0)

        # 5. Execute batch of steps
        batch = [
            {"fill": {"role": "textbox", "name": "Username"}, "value": "alice"},
            {"click": {"role": "button", "name": "Submit"}},
            {"wait_for": {"url": "/home"}},
            {"screenshot": {"out": "home.png"}},
        ]
        batch_res = daemon.session_batch(self.temp_repo, batch)
        self.assertTrue(batch_res["ok"])
        self.assertEqual(batch_res["executed_count"], 4)
        self.assertEqual(batch_res["transcript_count"], 5)

        # 6. Save transcript to scenario YAML
        out_yaml = os.path.join(self.temp_repo, "recorded_scenario.yaml")
        save_res = daemon.session_save(self.temp_repo, out_yaml, title="Alice Login Flow")
        self.assertTrue(save_res["ok"])
        self.assertEqual(save_res["steps_count"], 5)
        self.assertTrue(os.path.isfile(out_yaml))

        # Validate scenario format
        loaded = schema.load_scenario(out_yaml)
        self.assertEqual(loaded["meta"]["issue"], "test-feature")
        self.assertEqual(loaded["meta"]["title"], "Alice Login Flow")
        self.assertEqual(len(loaded["checks"][0]["steps"]), 5)

        # 7. Stop daemon
        stop_res = daemon.session_stop(self.temp_repo)
        self.assertTrue(stop_res["ok"])
        self.assertIsNone(daemon.read_session_info(self.temp_repo))

    def test_create_browser_session_reuses_existing_page(self):
        from unittest.mock import MagicMock, patch
        from alongkit.webdev import session

        mock_bp = MagicMock()
        mock_pw = MagicMock()
        mock_b_inst = MagicMock()
        mock_ctx = MagicMock()
        mock_existing_page = MagicMock()
        mock_ctx.pages = [mock_existing_page]
        mock_b_inst.contexts = [mock_ctx]

        with patch("alongkit.webdev.browser.launch_cft", return_value=mock_bp) as p_launch, \
             patch("alongkit.webdev.browser.connect_playwright", return_value=(mock_pw, mock_b_inst)) as p_conn:
            bp, (pw, page) = session.create_browser_session(self.temp_repo, headed=True, allowed_origins=["http://localhost:3000"])
            self.assertEqual(bp, mock_bp)
            self.assertEqual(pw, mock_pw)
            self.assertEqual(page, mock_existing_page)
            mock_b_inst.new_page.assert_not_called()
            p_launch.assert_called_once_with(headless=False, repo_root=self.temp_repo)
            p_conn.assert_called_once_with(mock_bp)

    def test_create_browser_session_fallback_new_page(self):
        from unittest.mock import MagicMock, patch
        from alongkit.webdev import session

        mock_bp = MagicMock()
        mock_pw = MagicMock()
        mock_b_inst = MagicMock()
        mock_b_inst.contexts = []
        mock_fallback_page = MagicMock()
        mock_b_inst.new_page.return_value = mock_fallback_page

        with patch("alongkit.webdev.browser.launch_cft", return_value=mock_bp), \
             patch("alongkit.webdev.browser.connect_playwright", return_value=(mock_pw, mock_b_inst)):
            bp, (pw, page) = session.create_browser_session(self.temp_repo, headed=False)
            self.assertEqual(page, mock_fallback_page)
            mock_b_inst.new_page.assert_called_once()

    def test_normalize_step_payload(self):
        # 1. Standard dict
        self.assertEqual(daemon.normalize_step_payload({"goto": "/home"}), {"goto": "/home"})

        # 2. cmd.exe split args with single quotes
        cmd_tokens = ["'{\"goto\":", "https://www.google.com}'"]
        parsed = daemon.normalize_step_payload(cmd_tokens)
        self.assertEqual(parsed, {"goto": "https://www.google.com"})

        # 3. Outer quotes wrapped string
        self.assertEqual(daemon.normalize_step_payload("'{\"click\": \"button\"}'"), {"click": "button"})

        # 4. Key=value shorthand
        self.assertEqual(daemon.normalize_step_payload("goto=https://example.com"), {"goto": "https://example.com"})

        # 5. File reference
        step_file = os.path.join(self.temp_repo, "step.json")
        with open(step_file, "w", encoding="utf-8") as f:
            f.write('{"fill": {"locator": "input", "text": "hello"}}')
        self.assertEqual(
            daemon.normalize_step_payload(f"@{step_file}"),
            {"fill": {"locator": "input", "text": "hello"}}
        )

    def test_normalize_batch_payload(self):
        # 1. Pre-parsed dict list
        self.assertEqual(daemon.normalize_batch_payload([{"goto": "/a"}, {"click": "#b"}]), [{"goto": "/a"}, {"click": "#b"}])

        # 2. JSON array string
        self.assertEqual(daemon.normalize_batch_payload('[{"goto": "/a"}, {"click": "#b"}]'), [{"goto": "/a"}, {"click": "#b"}])

        # 3. File reference
        batch_file = os.path.join(self.temp_repo, "batch.json")
        with open(batch_file, "w", encoding="utf-8") as f:
            f.write('[{"goto": "/test"}]')
        self.assertEqual(daemon.normalize_batch_payload(f"@{batch_file}"), [{"goto": "/test"}])



if __name__ == "__main__":
    unittest.main()
