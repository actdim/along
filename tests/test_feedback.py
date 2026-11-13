#!/usr/bin/env python3
"""
tests/test_feedback.py - Unit tests for Along self-diagnostics and feedback engine.
"""

import os
import sys
import json
import unittest
import tempfile
import shutil
from unittest.mock import patch, MagicMock

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(REPO_ROOT, "scripts"))

import along_feedback
from alongkit import proc


class TestAlongFeedbackEngine(unittest.TestCase):

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp(prefix="along_feedback_test_")
        self.old_global_along = along_feedback.GLOBAL_ALONG_DIR
        self.old_diagnostics = along_feedback.DIAGNOSTICS_DIR
        self.old_events = along_feedback.EVENTS_DIR
        self.old_export = along_feedback.EXPORT_DIR
        self.old_report = along_feedback.REPORT_FILE
        self.old_config_file = along_feedback.GLOBAL_CONFIG_FILE

        # Point storage to temp dir
        along_feedback.GLOBAL_ALONG_DIR = self.temp_dir
        along_feedback.DIAGNOSTICS_DIR = os.path.join(self.temp_dir, "diagnostics")
        along_feedback.EVENTS_DIR = os.path.join(along_feedback.DIAGNOSTICS_DIR, "events")
        along_feedback.EXPORT_DIR = os.path.join(along_feedback.DIAGNOSTICS_DIR, "export")
        along_feedback.REPORT_FILE = os.path.join(along_feedback.DIAGNOSTICS_DIR, "REPORT.md")
        along_feedback.GLOBAL_CONFIG_FILE = os.path.join(self.temp_dir, "config.json")

    def tearDown(self):
        along_feedback.GLOBAL_ALONG_DIR = self.old_global_along
        along_feedback.DIAGNOSTICS_DIR = self.old_diagnostics
        along_feedback.EVENTS_DIR = self.old_events
        along_feedback.EXPORT_DIR = self.old_export
        along_feedback.REPORT_FILE = self.old_report
        along_feedback.GLOBAL_CONFIG_FILE = self.old_config_file

        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_01_sanitizer_redacts_secrets_and_paths(self):
        """Verify that user home paths and authentication tokens are redacted."""
        raw_text = (
            f"Error at C:\\Users\\Admin\\AppData\\Local\\Temp with ghp_123456789012345678901234567890 "
            f"and OpenAI key sk-123456789012345678901234567890 and Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.test "
            f"and password=supersecretpass"
        )
        clean = along_feedback.Redactor.sanitize_text(raw_text)

        self.assertNotIn("ghp_123456789012345678901234567890", clean)
        self.assertIn("ghp_[REDACTED]", clean)
        self.assertNotIn("sk-123456789012345678901234567890", clean)
        self.assertIn("sk-[REDACTED]", clean)
        self.assertIn("Bearer [REDACTED]", clean)
        self.assertIn("password=[REDACTED]", clean)

    def test_02_record_and_list_incidents(self):
        """Verify recording an incident creates event file and updates REPORT.md."""
        incident = along_feedback.DiagnosticsStore.record_incident(
            component="scripts/along_commit.py",
            error_message="UnicodeEncodeError: 'charmap' codec can't encode character",
            event_type="script_crash",
            stack_trace="Traceback (most recent call last):\n  File 'along_commit.py', line 45",
            command="python scripts/along_commit.py -m 'test'",
            repo_root=REPO_ROOT
        )
        self.assertIsNotNone(incident)
        self.assertEqual(incident["component"], "scripts/along_commit.py")
        self.assertEqual(incident["status"], "unresolved")

        incidents = along_feedback.DiagnosticsStore.list_incidents(all_status=False)
        self.assertEqual(len(incidents), 1)
        self.assertEqual(incidents[0]["id"], incident["id"])

        self.assertTrue(os.path.exists(along_feedback.REPORT_FILE))
        with open(along_feedback.REPORT_FILE, "r", encoding="utf-8") as f:
            report_md = f.read()
        self.assertIn("Along Diagnostics & Telemetry Report", report_md)
        self.assertIn(incident["id"], report_md)

    def test_03_file_transport_export(self):
        """Verify file transport exports markdown and json bundles."""
        along_feedback.DiagnosticsStore.record_incident(
            component="scripts/test.py",
            error_message="Failed test run",
            event_type="command_error",
            repo_root=REPO_ROOT
        )
        config = along_feedback.ConfigManager.load_config(REPO_ROOT)
        report_text = along_feedback.DiagnosticsStore.generate_markdown_report()
        incidents = along_feedback.DiagnosticsStore.list_incidents()

        ok, msg = along_feedback.FileTransport.send(report_text, incidents, config, custom_path=along_feedback.EXPORT_DIR)
        self.assertTrue(ok)
        self.assertIn("Exported diagnostics bundle", msg)

        exported_files = os.listdir(along_feedback.EXPORT_DIR)
        self.assertGreaterEqual(len(exported_files), 2)

    def test_04_telegram_transport_mock(self):
        """Verify Telegram transport sends formatted summary."""
        incidents = [{
            "id": "2026-08-31T11-00-00Z--12345678",
            "component": "scripts/along_dash.py",
            "error_message": "Port 8000 in use"
        }]
        config = {
            "transports": {
                "telegram": {
                    "enabled": True,
                    "bot_token": "123456:ABC-DEF",
                    "chat_id": "-100123456"
                }
            }
        }

        with patch("urllib.request.urlopen") as mock_urlopen:
            mock_response = MagicMock()
            mock_response.status = 200
            mock_response.read.return_value = b'{"ok": true}'
            mock_urlopen.return_value.__enter__.return_value = mock_response

            ok, msg = along_feedback.TelegramTransport.send("Mock report", incidents, config)
            self.assertTrue(ok)
            self.assertIn("Successfully dispatched", msg)

    def test_05_webhook_transport_mock(self):
        """Verify Webhook transport posts JSON payload."""
        incidents = [{
            "id": "2026-08-31T11-00-00Z--abcdef12",
            "component": "scripts/along_update.py",
            "error_message": "HTTP 404 Not Found"
        }]
        config = {
            "transports": {
                "webhook": {
                    "enabled": True,
                    "url": "https://api.example.com/telemetry",
                    "headers": {"Content-Type": "application/json"}
                }
            }
        }

        with patch("urllib.request.urlopen") as mock_urlopen:
            mock_response = MagicMock()
            mock_response.status = 200
            mock_response.read.return_value = b'{"ok": true}'
            mock_urlopen.return_value.__enter__.return_value = mock_response

            ok, msg = along_feedback.WebhookTransport.send("Mock report", incidents, config)
            self.assertTrue(ok)
            self.assertIn("Successfully posted diagnostics bundle", msg)

    def test_06_cli_execution_flow(self):
        """Verify along_feedback.py CLI executes subcommands cleanly."""
        fb_script = os.path.join(REPO_ROOT, "scripts", "along_feedback.py")
        exec_script = os.path.join(REPO_ROOT, "scripts", "along_exec.py")

        # 1. Record via CLI
        rec_res = proc.run_capture([
            sys.executable, fb_script, "record",
            "--component", "cli_test",
            "--error", "Mock CLI error",
            "--note", "Test note"
        ])
        self.assertEqual(rec_res.returncode, 0)
        self.assertIn("Diagnostic incident recorded", rec_res.stdout)

        # 2. List via CLI
        list_res = proc.run_capture([sys.executable, fb_script, "list"])
        self.assertEqual(list_res.returncode, 0)
        self.assertIn("cli_test", list_res.stdout)

        # 3. Dry-run send via CLI
        send_res = proc.run_capture([sys.executable, fb_script, "send", "--dry-run"])
        self.assertEqual(send_res.returncode, 0)
        self.assertIn("Simulated dispatch", send_res.stdout)

        # 4. Dispatch via along_exec.py router
        exec_res = proc.run_capture([sys.executable, exec_script, "feedback", "list"])
        self.assertEqual(exec_res.returncode, 0)

    def test_07_note_building_and_redaction(self):
        """Verify build_inbox_note sanitizes secrets, normalizes typography, and structures front-matter."""
        raw_title = "Issue with C:\\Users\\Admin\\repo and sk-123456789012345678901234567890"
        raw_body = "Body mentioning ghp_123456789012345678901234567890 and password=secret -- text."
        incidents = [{
            "id": "inc-42",
            "component": "cli_engine",
            "error_message": "Crash with Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.tok"
        }]

        rel_path, text = along_feedback.build_inbox_note(
            title=raw_title,
            body=raw_body,
            incidents=incidents,
            date="2026-11-13"
        )

        self.assertTrue(rel_path.startswith(".along/inbox/feedback--2026-11-13-"))
        self.assertTrue(rel_path.endswith(".md"))

        # Verify redaction
        self.assertNotIn("sk-123456789012345678901234567890", text)
        self.assertIn("sk-[REDACTED]", text)
        self.assertNotIn("ghp_123456789012345678901234567890", text)
        self.assertIn("ghp_[REDACTED]", text)
        self.assertNotIn("password=secret", text)
        self.assertIn("password=[REDACTED]", text)
        self.assertNotIn("Bearer eyJhbGci", text)
        self.assertIn("Bearer [REDACTED]", text)

        # Verify typography is pure ASCII
        text.encode("ascii")

        # Verify front-matter and incidents section
        self.assertIn("source: along-feedback", text)
        self.assertIn("tags: [feedback]", text)
        self.assertIn("along_version:", text)
        self.assertIn("## Incidents", text)
        self.assertIn("inc-42", text)

    def test_08_preview_without_yes_and_dry_run(self):
        """Verify preview mode outputs plan, note content, and NOT SENT without modifications."""
        body_file = os.path.join(self.temp_dir, "preview_body.md")
        with open(body_file, "w", encoding="utf-8") as f:
            f.write("Preview body test content")

        fb_script = os.path.join(REPO_ROOT, "scripts", "along_feedback.py")
        res = proc.run_capture([
            sys.executable, fb_script, "send",
            "--channel", "github",
            "--title", "Preview Feedback Test",
            "--body-file", body_file
        ])

        self.assertEqual(res.returncode, 0)
        self.assertIn("Target Note Path:", res.stdout)
        self.assertIn(".along/inbox/feedback--", res.stdout)
        self.assertIn("Planned Actions:", res.stdout)
        self.assertIn("Preview Feedback Test", res.stdout)
        self.assertIn("NOT SENT", res.stdout)

    def test_09_gh_missing_falls_back_to_browser(self):
        """Verify that missing gh CLI triggers browser fallback with pre-filled new file URL."""
        mock_open = MagicMock(return_value=True)
        mock_run = MagicMock()

        ok, url = along_feedback.GitHubTransport.send(
            title="Missing GH Test",
            body="Feedback body without gh",
            yes=True,
            which=lambda b: None,
            run=mock_run,
            open_url=mock_open,
            date="2026-11-13",
            export_dir=self.temp_dir
        )

        self.assertTrue(ok)
        self.assertEqual(mock_run.call_count, 0)
        mock_open.assert_called_once()
        opened_url = mock_open.call_args[0][0]
        self.assertIn("https://github.com/actdim/along/new/main?filename=", opened_url)
        self.assertIn("filename=.along/inbox/feedback--2026-11-13-missing-gh-test.md", opened_url)
        self.assertIn("Feedback%20body%20without%20gh", opened_url)

    def test_10_gh_unauthenticated_falls_back_to_browser(self):
        """Verify unauthenticated gh CLI falls back to browser URL."""
        mock_open = MagicMock(return_value=True)
        def fake_run(cmd, **kwargs):
            if cmd == ["gh", "auth", "status"]:
                return proc.Result(cmd=cmd, returncode=1, stdout="", stderr="You are not logged into any GitHub hosts.")
            return proc.Result(cmd=cmd, returncode=0, stdout="", stderr="")

        ok, url = along_feedback.GitHubTransport.send(
            title="Unauthenticated Test",
            body="Feedback body with unauthenticated gh",
            yes=True,
            which=lambda b: "/fake/bin/gh",
            run=fake_run,
            open_url=mock_open,
            date="2026-11-13",
            export_dir=self.temp_dir
        )

        self.assertTrue(ok)
        mock_open.assert_called_once()
        opened_url = mock_open.call_args[0][0]
        self.assertIn("https://github.com/actdim/along/new/main?", opened_url)

    def test_11_collaborator_path_call_sequence(self):
        """Verify collaborator workflow executes direct branch creation, commit, and PR without clone or fork."""
        executed_cmds = []

        def fake_run(cmd, **kwargs):
            executed_cmds.append(cmd)
            if cmd == ["gh", "auth", "status"]:
                return proc.Result(cmd=cmd, returncode=0, stdout="Logged in", stderr="")
            if cmd == ["gh", "api", "user", "--jq", ".login"]:
                return proc.Result(cmd=cmd, returncode=0, stdout="collab_user\n", stderr="")
            if cmd == ["gh", "api", "repos/actdim/along", "--jq", ".permissions.push"]:
                return proc.Result(cmd=cmd, returncode=0, stdout="true\n", stderr="")
            if cmd == ["gh", "api", "repos/actdim/along/git/ref/heads/main", "--jq", ".object.sha"]:
                return proc.Result(cmd=cmd, returncode=0, stdout="commit_sha_123\n", stderr="")
            if len(cmd) > 4 and cmd[0:4] == ["gh", "api", "-X", "POST"] and "refs" in cmd[4]:
                return proc.Result(cmd=cmd, returncode=0, stdout="", stderr="")
            if len(cmd) > 4 and cmd[0:4] == ["gh", "api", "-X", "PUT"] and "contents" in cmd[4]:
                return proc.Result(cmd=cmd, returncode=0, stdout="", stderr="")
            if len(cmd) > 3 and cmd[0:3] == ["gh", "pr", "create"]:
                return proc.Result(cmd=cmd, returncode=0, stdout="https://github.com/actdim/along/pull/101\n", stderr="")
            return proc.Result(cmd=cmd, returncode=0, stdout="", stderr="")

        mock_open = MagicMock()
        ok, res = along_feedback.GitHubTransport.send(
            title="Collab Feedback",
            body="Everything works",
            yes=True,
            which=lambda b: "/fake/bin/gh",
            run=fake_run,
            open_url=mock_open,
            date="2026-11-13",
            export_dir=self.temp_dir
        )

        self.assertTrue(ok)
        self.assertEqual(res, "https://github.com/actdim/along/pull/101")
        mock_open.assert_not_called()

        # Verify no clone or fork was called
        for cmd in executed_cmds:
            self.assertNotIn("clone", cmd)
            self.assertNotIn("fork", cmd)

    def test_12_non_collaborator_fork_path(self):
        """Verify non-collaborator workflow executes server-side fork and PR without local clone."""
        executed_cmds = []

        def fake_run(cmd, **kwargs):
            executed_cmds.append(cmd)
            if cmd == ["gh", "auth", "status"]:
                return proc.Result(cmd=cmd, returncode=0, stdout="Logged in", stderr="")
            if cmd == ["gh", "api", "user", "--jq", ".login"]:
                return proc.Result(cmd=cmd, returncode=0, stdout="contributor_user\n", stderr="")
            if cmd == ["gh", "api", "repos/actdim/along", "--jq", ".permissions.push"]:
                return proc.Result(cmd=cmd, returncode=0, stdout="false\n", stderr="")
            if cmd[0:3] == ["gh", "repo", "fork"]:
                return proc.Result(cmd=cmd, returncode=0, stdout="Fork created", stderr="")
            if cmd[0:4] == ["gh", "api", "repos/contributor_user/along", "--jq"]:
                return proc.Result(cmd=cmd, returncode=0, stdout="actdim/along\n", stderr="")
            if "merge-upstream" in cmd[4]:
                return proc.Result(cmd=cmd, returncode=0, stdout="", stderr="")
            if cmd == ["gh", "api", "repos/actdim/along/git/ref/heads/main", "--jq", ".object.sha"]:
                return proc.Result(cmd=cmd, returncode=0, stdout="commit_sha_789\n", stderr="")
            if len(cmd) > 4 and "git/refs" in cmd[4]:
                return proc.Result(cmd=cmd, returncode=0, stdout="", stderr="")
            if len(cmd) > 4 and "contents" in cmd[4]:
                return proc.Result(cmd=cmd, returncode=0, stdout="", stderr="")
            if cmd[0:3] == ["gh", "pr", "create"]:
                return proc.Result(cmd=cmd, returncode=0, stdout="https://github.com/actdim/along/pull/202\n", stderr="")
            return proc.Result(cmd=cmd, returncode=0, stdout="", stderr="")

        mock_open = MagicMock()
        ok, res = along_feedback.GitHubTransport.send(
            title="Contributor Feedback",
            body="Contribution report",
            yes=True,
            which=lambda b: "/fake/bin/gh",
            run=fake_run,
            open_url=mock_open,
            date="2026-11-13",
            export_dir=self.temp_dir
        )

        self.assertTrue(ok)
        self.assertEqual(res, "https://github.com/actdim/along/pull/202")
        mock_open.assert_not_called()

        # Assert fork was executed without clone
        fork_invocations = [c for c in executed_cmds if c[0:3] == ["gh", "repo", "fork"]]
        self.assertEqual(len(fork_invocations), 1)
        self.assertIn("--clone=false", fork_invocations[0])

        for cmd in executed_cmds:
            self.assertNotIn("clone", cmd)

    def test_13_branch_exists_retry(self):
        """Verify branch creation retries with -2 suffix when reference already exists."""
        created_branches = []

        def fake_run(cmd, **kwargs):
            if cmd == ["gh", "auth", "status"]:
                return proc.Result(cmd=cmd, returncode=0, stdout="Logged in", stderr="")
            if cmd == ["gh", "api", "user", "--jq", ".login"]:
                return proc.Result(cmd=cmd, returncode=0, stdout="collab_user\n", stderr="")
            if cmd == ["gh", "api", "repos/actdim/along", "--jq", ".permissions.push"]:
                return proc.Result(cmd=cmd, returncode=0, stdout="true\n", stderr="")
            if cmd == ["gh", "api", "repos/actdim/along/git/ref/heads/main", "--jq", ".object.sha"]:
                return proc.Result(cmd=cmd, returncode=0, stdout="commit_sha_123\n", stderr="")
            if len(cmd) > 4 and "git/refs" in cmd[4]:
                ref_arg = cmd[6] # -f ref=refs/heads/...
                created_branches.append(ref_arg)
                if len(created_branches) == 1:
                    return proc.Result(cmd=cmd, returncode=1, stdout="", stderr="Reference already exists (422)")
                return proc.Result(cmd=cmd, returncode=0, stdout="", stderr="")
            if len(cmd) > 4 and "contents" in cmd[4]:
                return proc.Result(cmd=cmd, returncode=0, stdout="", stderr="")
            if cmd[0:3] == ["gh", "pr", "create"]:
                return proc.Result(cmd=cmd, returncode=0, stdout="https://github.com/actdim/along/pull/303\n", stderr="")
            return proc.Result(cmd=cmd, returncode=0, stdout="", stderr="")

        ok, res = along_feedback.GitHubTransport.send(
            title="Collision Test",
            body="Collision body",
            yes=True,
            which=lambda b: "/fake/bin/gh",
            run=fake_run,
            open_url=MagicMock(),
            date="2026-11-13",
            export_dir=self.temp_dir
        )

        self.assertTrue(ok)
        self.assertEqual(len(created_branches), 2)
        self.assertIn("ref=refs/heads/feedback/2026-11-13-collision-test", created_branches[0])
        self.assertIn("ref=refs/heads/feedback/2026-11-13-collision-test-2", created_branches[1])

    def test_14_gh_failure_midway_falls_back_to_browser(self):
        """Verify that midway gh failure reports stderr and falls back to browser."""
        mock_open = MagicMock(return_value=True)

        def fake_run(cmd, **kwargs):
            if cmd == ["gh", "auth", "status"]:
                return proc.Result(cmd=cmd, returncode=0, stdout="Logged in", stderr="")
            if cmd == ["gh", "api", "user", "--jq", ".login"]:
                return proc.Result(cmd=cmd, returncode=1, stdout="", stderr="HTTP 500: Server Error in GitHub API")
            return proc.Result(cmd=cmd, returncode=0, stdout="", stderr="")

        ok, res = along_feedback.GitHubTransport.send(
            title="Midway Fail Test",
            body="Midway body",
            yes=True,
            which=lambda b: "/fake/bin/gh",
            run=fake_run,
            open_url=mock_open,
            date="2026-11-13",
            export_dir=self.temp_dir
        )

        self.assertTrue(ok)
        mock_open.assert_called_once()
        opened_url = mock_open.call_args[0][0]
        self.assertIn("https://github.com/actdim/along/new/main?", opened_url)

    def test_15_long_body_truncation(self):
        """Verify bodies creating URLs exceeding 7000 chars are truncated and saved to export dir."""
        mock_open = MagicMock(return_value=True)
        long_body = "A" * 10000

        ok, res = along_feedback.GitHubTransport.send(
            title="Long Body Test",
            body=long_body,
            yes=True,
            which=lambda b: None, # trigger web fallback
            open_url=mock_open,
            date="2026-11-13",
            export_dir=self.temp_dir
        )

        self.assertTrue(ok)
        mock_open.assert_called_once()
        opened_url = mock_open.call_args[0][0]
        self.assertLessEqual(len(opened_url), 7000)
        self.assertIn("Body%20truncated%20due%20to%20URL%20length%20limit", opened_url)

        # Verify full note was saved to export_dir
        exported = os.listdir(self.temp_dir)
        matching = [f for f in exported if f.startswith("feedback-full--2026-11-13-long-body-test")]
        self.assertEqual(len(matching), 1)

    def test_16_channel_all_does_not_include_github(self):
        """Verify dispatching with --channel all does not invoke github transport."""
        along_feedback.DiagnosticsStore.record_incident(
            component="scripts/test.py",
            error_message="Sample test anomaly",
            event_type="command_error",
            repo_root=REPO_ROOT
        )

        with patch.object(along_feedback.GitHubTransport, "send") as mock_gh_send:
            results = along_feedback.dispatch_feedback(channel="all")
            mock_gh_send.assert_not_called()

        channel_names = [ch for ch, _, _ in results]
        self.assertNotIn("github", channel_names)
        self.assertIn("file", channel_names)


if __name__ == "__main__":
    unittest.main(verbosity=2)

