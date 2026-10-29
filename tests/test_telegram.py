#!/usr/bin/env python3
"""
tests/test_telegram.py - Unit tests for alongkit.telegram unified Telegram helper.
"""

import json
import os
import tempfile
import unittest
import urllib.error
from unittest.mock import MagicMock, patch

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

from alongkit import diagnostics, telegram


class TestTelegramResolution(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="along-test-telegram-")
        self.repo_dir = os.path.join(self.tmp, "repo")
        os.makedirs(os.path.join(self.repo_dir, ".along"), exist_ok=True)
        self.global_cfg = os.path.join(self.tmp, "global_config.json")

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_precedence_global_local_and_env(self):
        # 1. Global config
        with open(self.global_cfg, "w", encoding="utf-8") as f:
            json.dump({
                "transports": {
                    "telegram": {
                        "bot_token": "token-A",
                        "chat_id": "1",
                        "enabled": False,
                    }
                }
            }, f)

        # 2. Local repo config
        local_cfg = os.path.join(self.repo_dir, ".along", "config.json")
        with open(local_cfg, "w", encoding="utf-8") as f:
            json.dump({
                "transports": {
                    "telegram": {
                        "bot_token": "token-B",
                        "chat_id": "2",
                        "enabled": False,
                    }
                }
            }, f)

        # 3. Environment overrides
        environ = {
            "TELEGRAM_BOT_TOKEN": "token-C",
            "ALONG_TELEGRAM_CHAT_ID": "3,4",
        }

        settings = telegram.resolve_settings(
            repo_root=self.repo_dir,
            environ=environ,
            global_config=self.global_cfg,
        )

        self.assertEqual(settings.bot_token, "token-C")
        self.assertEqual(settings.chat_ids, ["1", "2", "3", "4"])
        self.assertEqual(settings.primary_chat_id, "3")
        self.assertTrue(settings.enabled)

    def test_diagnostics_load_config_with_unprefixed_env_tokens(self):
        # Container environment with TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID
        environ = {
            "TELEGRAM_BOT_TOKEN": "container-bot-token",
            "TELEGRAM_CHAT_ID": "999888",
        }
        with patch.dict(os.environ, environ, clear=True):
            cfg = diagnostics.ConfigManager.load_config(repo_root=self.repo_dir)
            t_cfg = cfg["transports"]["telegram"]
            self.assertEqual(t_cfg["bot_token"], "container-bot-token")
            self.assertEqual(t_cfg["chat_id"], "999888")
            self.assertTrue(t_cfg["enabled"])

    def test_diagnostics_load_config_does_not_mutate_default_config(self):
        # First call with env vars
        with patch.dict(os.environ, {"ALONG_TELEGRAM_BOT_TOKEN": "ephemeral-token"}, clear=True):
            cfg1 = diagnostics.ConfigManager.load_config(repo_root=self.repo_dir)
            self.assertEqual(cfg1["transports"]["telegram"]["bot_token"], "ephemeral-token")

        # Second call with empty env and no config files
        empty_tmp = tempfile.mkdtemp(prefix="along-test-empty-")
        try:
            with patch.dict(os.environ, {}, clear=True):
                cfg2 = diagnostics.ConfigManager.load_config(repo_root=empty_tmp)
                self.assertEqual(cfg2["transports"]["telegram"]["bot_token"], "")
                self.assertFalse(cfg2["transports"]["telegram"]["enabled"])
        finally:
            import shutil
            shutil.rmtree(empty_tmp, ignore_errors=True)


class TestTelegramDispatch(unittest.TestCase):
    @patch("urllib.request.urlopen")
    def test_send_message_http_error_redacts_token(self, mock_urlopen):
        err = urllib.error.HTTPError(
            url="https://api.telegram.org/botSUPER_SECRET_TOKEN/sendMessage",
            code=401,
            msg="Unauthorized",
            hdrs={},
            fp=None,
        )
        mock_urlopen.side_effect = err

        ok, detail = telegram.send_message("SUPER_SECRET_TOKEN", "12345", "test message")
        self.assertFalse(ok)
        self.assertNotIn("SUPER_SECRET_TOKEN", detail)
        self.assertIn("401", detail)

    def test_single_home_for_telegram_api_endpoint(self):
        # api.telegram.org and sendMessage appear under scripts/ only in alongkit/telegram.py
        scripts_dir = os.path.join(REPO_ROOT, "scripts")
        telegram_py = os.path.normpath(os.path.join(scripts_dir, "alongkit", "telegram.py"))

        violations = []
        for root, _, files in os.walk(scripts_dir):
            for fname in files:
                if not fname.endswith(".py"):
                    continue
                path = os.path.normpath(os.path.join(root, fname))
                if path == telegram_py:
                    continue
                with open(path, "r", encoding="utf-8") as f:
                    content = f.read()
                if "api.telegram.org" in content:
                    violations.append(f"{path}: contains 'api.telegram.org'")
                if "sendMessage" in content:
                    violations.append(f"{path}: contains 'sendMessage'")

        self.assertEqual(violations, [], f"Found unauthorized Telegram API references: {violations}")
