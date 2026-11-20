#!/usr/bin/env python3
"""tests/test_webdev_bootstrap.py - Hermetic tests for CfT resolution, unpack, and process teardown."""

from __future__ import annotations

import io
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
import zipfile
from unittest import mock

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "scripts")))

from alongkit import bootstrap
from alongkit.webdev import browser, cft
import along_webdev


class TestCftResolution(unittest.TestCase):
    """Hermetic unit tests for CfT version, platform, and path resolution."""

    def test_detect_platform_mapping(self):
        with mock.patch("sys.platform", "win32"):
            self.assertEqual(cft.detect_platform(), "win64")
        with mock.patch("sys.platform", "linux"):
            self.assertEqual(cft.detect_platform(), "linux64")
        with mock.patch("sys.platform", "darwin"), mock.patch("platform.machine", return_value="arm64"):
            self.assertEqual(cft.detect_platform(), "mac-arm64")
        with mock.patch("sys.platform", "darwin"), mock.patch("platform.machine", return_value="x86_64"):
            self.assertEqual(cft.detect_platform(), "mac-x64")

    def test_binary_relative_paths(self):
        self.assertIn("chrome.exe", cft.binary_relative_path("win64"))
        self.assertEqual(cft.binary_relative_path("linux64"), os.path.join("chrome-linux64", "chrome"))
        self.assertIn("Google Chrome for Testing", cft.binary_relative_path("mac-arm64"))

    def test_cache_dir_env_override(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            with mock.patch.dict(os.environ, {"ALONG_CFT_CACHE_DIR": tmp_dir}):
                self.assertEqual(cft.cft_cache_dir("131.0"), os.path.abspath(tmp_dir))


class TestCftDownloadAndUnpack(unittest.TestCase):
    """Hermetic download and unpacking via file:// URL."""

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.cache_dir = os.path.join(self.temp_dir, "cache")
        self.archive_dir = os.path.join(self.temp_dir, "archive")
        os.makedirs(self.archive_dir, exist_ok=True)

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_unpack_synthetic_cft_archive(self):
        plat = "win64" if sys.platform == "win32" else "linux64"
        rel_bin = cft.binary_relative_path(plat)
        zip_path = os.path.join(self.archive_dir, "fake_cft.zip")

        with zipfile.ZipFile(zip_path, "w") as zf:
            zf.writestr(rel_bin, b"#!/bin/sh\necho fake chrome\n")

        file_url = f"file:///{os.path.abspath(zip_path).replace(os.sep, '/')}"

        with mock.patch.dict(os.environ, {"ALONG_CFT_CACHE_DIR": self.cache_dir}):
            binary = cft.download_cft(
                version="999.0",
                platform_name=plat,
                destination_dir=self.cache_dir,
                quiet=True,
                url_override=file_url,
            )

            self.assertTrue(os.path.isfile(binary))
            st = cft.status(version="999.0", platform_name=plat)
            self.assertTrue(st["cached"])
            self.assertTrue(st["available"])
            self.assertEqual(os.path.abspath(st["path"]), os.path.abspath(binary))


class TestBrowserProcessTeardown(unittest.TestCase):
    """Hermetic test verifying browser launcher teardown and profile purge."""

    def test_browser_process_close_purges_temp_profile(self):
        temp_profile = tempfile.mkdtemp(prefix="along-test-profile-")
        port_file = os.path.join(temp_profile, "DevToolsActivePort")
        with open(port_file, "w", encoding="utf-8") as handle:
            handle.write("9222\n/devtools/browser/fake-id\n")

        # Launch a dummy python process that sleeps
        proc = subprocess.Popen(
            [sys.executable, "-c", "import time; time.sleep(30)"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )

        bp = browser.BrowserProcess(
            popen=proc,
            port=9222,
            ws_path="/devtools/browser/fake-id",
            user_data_dir=temp_profile,
            is_temp_profile=True,
        )

        self.assertTrue(bp.is_alive())
        self.assertEqual(bp.http_endpoint, "http://127.0.0.1:9222")
        self.assertEqual(bp.ws_endpoint, "ws://127.0.0.1:9222/devtools/browser/fake-id")

        bp.close(grace=0.5)

        self.assertFalse(bp.is_alive())
        self.assertFalse(os.path.isdir(temp_profile))


class TestWebdevCliBootstrap(unittest.TestCase):
    """CLI routing and subcommands in Phase 1."""

    def test_cli_bootstrap_status_json(self):
        stdout = io.StringIO()
        with mock.patch("sys.stdout", stdout):
            code = along_webdev.main(["bootstrap", "--status", "--json"])
        self.assertIn(code, (0, 1))
        payload = json.loads(stdout.getvalue())
        self.assertIn("platform", payload)
        self.assertIn("version", payload)
        self.assertIn("cache_dir", payload)

    def test_cli_limits_json(self):
        stdout = io.StringIO()
        with mock.patch("sys.stdout", stdout):
            code = along_webdev.main(["limits", "--json"])
        self.assertEqual(code, 0)
        limits = json.loads(stdout.getvalue())
        self.assertIsInstance(limits, list)
        ids = [item["id"] for item in limits]
        self.assertIn("platform-limit:mobile-virtual-keyboard", ids)
        self.assertIn("platform-limit:os-media-flyout", ids)
        self.assertIn("platform-limit:native-file-dialog", ids)

    def test_ensure_runtime_helper_signature(self):
        self.assertTrue(callable(bootstrap.ensure_runtime))
        dir_path = bootstrap.named_runtime_venv_dir("webdev")
        self.assertIn("webdev-venv", dir_path)


if __name__ == "__main__":
    unittest.main()
