#!/usr/bin/env python3
"""tests/test_webdev_engine.py - Hermetic tests for locators, redaction, origin guard, and capture (REQ-2..REQ-7)."""

from __future__ import annotations

import os
import sys
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "scripts")))

from alongkit.webdev import capture, locators, probes, redact, session, steps


class TestLocatorsAndCoordinates(unittest.TestCase):
    """Unit tests for locator parsing and coordinate safety gating (REQ-2)."""

    def test_describe_locator(self):
        self.assertEqual(locators.describe_locator("button.submit"), "button.submit")
        self.assertEqual(
            locators.describe_locator({"role": "button", "name": "Send"}),
            "{name='Send', role='button'}",
        )

    def test_coordinates_validation_fails_without_allow_coordinates(self):
        step = {"action": "click", "at": {"x": 100, "y": 200}}
        with self.assertRaises(ValueError) as ctx:
            locators.validate_coordinates_allowed(step)
        self.assertIn("allow_coordinates: true", str(ctx.exception))

    def test_coordinates_validation_passes_with_allow_coordinates(self):
        step = {"action": "click", "at": {"x": 100, "y": 200}, "allow_coordinates": True}
        # Must not raise
        locators.validate_coordinates_allowed(step)


class TestRedaction(unittest.TestCase):
    """Unit tests for centralized secret and header redaction (REQ-3, REQ-7)."""

    def setUp(self):
        self.redactor = redact.Redactor(secrets={"API_SECRET": "topsecret_12345"})

    def test_sensitive_headers_redacted(self):
        headers = {
            "Authorization": "Bearer topsecret_12345",
            "Cookie": "session=xyz",
            "User-Agent": "AlongBrowser/1.0",
        }
        cleaned = self.redactor.redact_headers(headers)
        self.assertEqual(cleaned["Authorization"], "[REDACTED]")
        self.assertEqual(cleaned["Cookie"], "[REDACTED]")
        self.assertEqual(cleaned["User-Agent"], "AlongBrowser/1.0")

    def test_secret_text_redacted(self):
        text = "Server responded with token topsecret_12345 for user"
        cleaned = self.redactor.redact_text(text)
        self.assertEqual(cleaned, "Server responded with token ***API_SECRET*** for user")

    def test_recursive_data_redaction(self):
        data = {
            "user": "alice",
            "password": "plain_password_here",
            "nested": {"api_key": "some_key", "count": 5},
        }
        cleaned = self.redactor.redact_data(data)
        self.assertEqual(cleaned["password"], "[REDACTED]")
        self.assertEqual(cleaned["nested"]["api_key"], "[REDACTED]")
        self.assertEqual(cleaned["user"], "alice")


class TestCaptureAndNoiseFiltering(unittest.TestCase):
    """Unit tests for console and network capture with noise filtering (REQ-7)."""

    def test_console_noise_filtering(self):
        harvester = capture.DiagnosticsHarvester(
            console_noise=[r".*\[HMR\].*", r".*DevTools.*"]
        )
        harvester.console_messages.append(
            capture.ConsoleMessage(level="error", text="[HMR] Connection failed to dev server")
        )
        harvester.console_messages.append(
            capture.ConsoleMessage(level="error", text="Real application runtime error: Uncaught TypeError")
        )

        filtered = harvester.filtered_console_errors()
        self.assertEqual(len(filtered), 1)
        self.assertEqual(filtered[0].text, "Real application runtime error: Uncaught TypeError")

    def test_network_noise_filtering(self):
        harvester = capture.DiagnosticsHarvester(
            network_noise=[r".*favicon\.ico.*"]
        )
        harvester.network_records.append(
            capture.NetworkRecord(method="GET", url="http://localhost:5173/favicon.ico", status=404)
        )
        harvester.network_records.append(
            capture.NetworkRecord(method="POST", url="http://localhost:5173/api/data", status=500)
        )

        filtered = harvester.filtered_failed_requests()
        self.assertEqual(len(filtered), 1)
        self.assertEqual(filtered[0].url, "http://localhost:5173/api/data")
        self.assertEqual(filtered[0].status, 500)


class TestOriginGuard(unittest.TestCase):
    """Unit tests for navigation origin allowlist checking (REQ-2)."""

    def test_is_origin_allowed(self):
        allowed = ["http://localhost:5173", "http://127.0.0.1:8000"]
        self.assertTrue(session.is_origin_allowed("http://localhost:5173/dashboard", allowed))
        self.assertTrue(session.is_origin_allowed("http://127.0.0.1:8000/api/users", allowed))
        self.assertTrue(session.is_origin_allowed("about:blank", allowed))

        # Disallowed origins
        self.assertFalse(session.is_origin_allowed("https://accounts.google.com/signin", allowed))
        self.assertFalse(session.is_origin_allowed("http://evil-origin.com/login", allowed))


class TestProbesJsBundle(unittest.TestCase):
    """Unit tests for in-page geometry and spy probe definitions (REQ-6)."""

    def test_probes_script_present_and_has_required_probes(self):
        code = probes.get_probes_script()
        self.assertTrue(len(code) > 100)
        self.assertIn("window.__along_probes__.box", code)
        self.assertIn("window.__along_probes__.above", code)
        self.assertIn("window.__along_probes__.covered_by", code)
        self.assertIn("window.__along_probes__.overflow_x", code)
        self.assertIn("window.__along_probes__.install_spy", code)


class TestSyntheticFixtures(unittest.TestCase):
    """Unit tests for synthetic upload fixture generator (REQ-5)."""

    def test_generate_synthetic_png_fixture(self):
        path = steps.generate_synthetic_fixture(kind="png", size_kb=2)
        try:
            self.assertTrue(os.path.isfile(path))
            size = os.path.getsize(path)
            self.assertGreaterEqual(size, 2048)
            with open(path, "rb") as f:
                header = f.read(8)
            self.assertEqual(header, b"\x89PNG\r\n\x1a\n")
        finally:
            if os.path.isfile(path):
                os.remove(path)


if __name__ == "__main__":
    unittest.main()
