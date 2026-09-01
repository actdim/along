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


if __name__ == "__main__":
    unittest.main(verbosity=2)

