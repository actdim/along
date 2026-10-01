#!/usr/bin/env python3
"""
tests/test_telemetry_redactor_offloader.py - Hermetic tests for Redactor and ArtifactOffloader.
"""

from __future__ import annotations

import hashlib
import os
import sys
import tempfile
import unittest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPTS_DIR = os.path.join(REPO_ROOT, "scripts")
if SCRIPTS_DIR not in sys.path:
    sys.path.insert(0, SCRIPTS_DIR)

from alongkit.telemetry import ArtifactOffloader, ArtifactRef, Redactor


class TestRedactorTokensAndKeys(unittest.TestCase):
    def setUp(self) -> None:
        self.redactor = Redactor()

    def test_bearer_token_redaction(self) -> None:
        raw = "Authorization: Bearer secret-token-12345.xyz~abc+foo/bar=="
        sanitized = self.redactor.sanitize_text(raw)
        self.assertEqual(sanitized, "Authorization: Bearer [REDACTED]")

        # Multiple bearer variations and case-insensitivity
        raw2 = "bearer   eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.e30.t-ID"
        self.assertEqual(self.redactor.sanitize_text(raw2), "bearer   [REDACTED]")

        # Idempotence: already redacted token
        self.assertEqual(self.redactor.sanitize_text("Bearer [REDACTED]"), "Bearer [REDACTED]")

    def test_github_token_redaction(self) -> None:
        tokens = [
            ("ghp_123456789012345678901234", "[REDACTED_GITHUB_TOKEN]"),
            ("gho_123456789012345678901234", "[REDACTED_GITHUB_TOKEN]"),
            ("ghu_123456789012345678901234", "[REDACTED_GITHUB_TOKEN]"),
            ("ghs_123456789012345678901234", "[REDACTED_GITHUB_TOKEN]"),
            ("ghr_123456789012345678901234", "[REDACTED_GITHUB_TOKEN]"),
            ("github_pat_11ABCD1234567890123456_abcdefghijklmnopqrstuvwxyz", "[REDACTED_GITHUB_TOKEN]"),
        ]
        for token, expected in tokens:
            with self.subTest(token=token):
                text = f"Token is {token} in environment"
                self.assertEqual(self.redactor.sanitize_text(text), f"Token is {expected} in environment")

    def test_openai_api_key_redaction(self) -> None:
        key1 = "sk-123456789012345678901234"
        self.assertEqual(self.redactor.sanitize_text(f"KEY={key1}"), "KEY=sk-[REDACTED]")

        key2 = "sk-proj-123456789012345678901234567890"
        self.assertEqual(self.redactor.sanitize_text(f"Key: {key2}"), "Key: sk-[REDACTED]")

    def test_anthropic_api_key_redaction(self) -> None:
        key1 = "sk-ant-123456789012345678901234"
        self.assertEqual(self.redactor.sanitize_text(f"KEY={key1}"), "KEY=sk-ant-[REDACTED]")

        key2 = "sk-ant-api03-123456789012345678901234567890"  # along: allow-no-tracked-secrets
        self.assertEqual(self.redactor.sanitize_text(f"Key: {key2}"), "Key: sk-ant-[REDACTED]")

    def test_anthropic_key_not_clobbered_by_openai_pattern(self) -> None:
        text = "Anthropic key is sk-ant-api03-abcdefghijklmnopqrstuvwxyz1234"  # along: allow-no-tracked-secrets
        sanitized = self.redactor.sanitize_text(text)
        self.assertIn("sk-ant-[REDACTED]", sanitized)
        self.assertNotIn("sk-[REDACTED]", sanitized.replace("sk-ant-[REDACTED]", ""))

    def test_aws_access_key_redaction(self) -> None:
        keys = [
            ("AKIAIOSFODNN7EXAMPLE", "[REDACTED_AWS_KEY]"),  # along: allow-no-tracked-secrets
            ("ASIAIOSFODNN7EXAMPLE", "[REDACTED_AWS_KEY]"),  # along: allow-no-tracked-secrets
        ]
        for key, expected in keys:
            with self.subTest(key=key):
                text = f"AWS credentials: aws_access_key_id = {key}"
                self.assertEqual(self.redactor.sanitize_text(text), f"AWS credentials: aws_access_key_id = {expected}")

    def test_private_key_redaction(self) -> None:
        private_keys = [
            "-----BEGIN RSA PRIVATE KEY-----\nMIIEowIBAAKCAQEA0m...\n-----END RSA PRIVATE KEY-----",  # along: allow-no-tracked-secrets
            "-----BEGIN EC PRIVATE KEY-----\nMHcCAQEEI...\n-----END EC PRIVATE KEY-----",  # along: allow-no-tracked-secrets
            "-----BEGIN OPENSSH PRIVATE KEY-----\nb3BlbnNzaC1rZXktdjEAAAAA...\n-----END OPENSSH PRIVATE KEY-----",  # along: allow-no-tracked-secrets
            "-----BEGIN DSA PRIVATE KEY-----\nMIIBvAIBAAKCAQEA...\n-----END DSA PRIVATE KEY-----",  # along: allow-no-tracked-secrets
            "-----BEGIN PRIVATE KEY-----\nMIIEvgIBADANBgkqhkiG9w0BAQEFAASCBKgwggSkAgEAAoIBAQC7...\n-----END PRIVATE KEY-----",  # along: allow-no-tracked-secrets
        ]
        for pk in private_keys:
            with self.subTest(pk=pk[:30]):
                text = f"Certificate config:\n{pk}\nEnd of config."
                sanitized = self.redactor.sanitize_text(text)
                self.assertEqual(sanitized, "Certificate config:\n[REDACTED_PRIVATE_KEY]\nEnd of config.")


class TestRedactorGenericAssignmentsAndPaths(unittest.TestCase):
    def setUp(self) -> None:
        self.redactor = Redactor()

    def test_generic_secret_assignments(self) -> None:
        cases = [
            ('api_key = "super_secret_123"', 'api_key = "[REDACTED]"'),
            ("api-key: secret-value", "api-key: [REDACTED]"),
            ("access_token = 'token_abc'", "access_token = '[REDACTED]'"),
            ("auth_token: mytoken123;", "auth_token: [REDACTED];"),
            ("secret_key=xyz987", "secret_key=[REDACTED]"),
            ("password: my_password", "password: [REDACTED]"),
            ('client_secret = "client-secret-99"', 'client_secret = "[REDACTED]"'),
            ('{"password": "secret", "user": "admin"}', '{"password": "[REDACTED]", "user": "admin"}'),
            ('{"client_secret": "my-secret"}', '{"client_secret": "[REDACTED]"}'),
            ('ACCESS_TOKEN=tok_12345', 'ACCESS_TOKEN=[REDACTED]'),
        ]
        for raw, expected in cases:
            with self.subTest(raw=raw):
                self.assertEqual(self.redactor.sanitize_text(raw), expected)

    def test_generic_assignment_preserves_specific_redactions(self) -> None:
        cases = [
            ('api_key = "[REDACTED_AWS_KEY]"', 'api_key = "[REDACTED_AWS_KEY]"'),
            ('password: [REDACTED]', 'password: [REDACTED]'),
            ('api_key = "sk-[REDACTED]"', 'api_key = "sk-[REDACTED]"'),
            ('api_key = "sk-ant-[REDACTED]"', 'api_key = "sk-ant-[REDACTED]"'),
        ]
        for raw, expected in cases:
            with self.subTest(raw=raw):
                self.assertEqual(self.redactor.sanitize_text(raw), expected)

    def test_user_home_directory_scrubbing(self) -> None:
        cases = [
            (r"Log file: C:\Users\Admin\Desktop\project\app.log", r"Log file: ~\Desktop\project\app.log"),
            (r"Path is c:\users\Admin\workspace\file.py", r"Path is ~\workspace\file.py"),
            ("Path is C:/Users/Admin/workspace/file.py", "Path is ~/workspace/file.py"),
            (r"Old path: D:\Documents and Settings\JohnDoe\file.txt", r"Old path: ~\file.txt"),
            ("File at /home/alice/project/main.py", "File at ~/project/main.py"),
            ("File at /Users/bob/project/main.py", "File at ~/project/main.py"),
            ("/home/alice", "~"),
            (r"C:\Users\Admin", "~"),
        ]
        for raw, expected in cases:
            with self.subTest(raw=raw):
                self.assertEqual(self.redactor.sanitize_text(raw), expected)

    def test_edge_cases_in_sanitize_text(self) -> None:
        self.assertEqual(self.redactor.sanitize_text(""), "")
        self.assertEqual(self.redactor.sanitize_text(None), "")  # type: ignore[arg-type]
        self.assertEqual(self.redactor.sanitize_text("No secrets here, plain text"), "No secrets here, plain text")


class TestRedactorDictAndValue(unittest.TestCase):
    def setUp(self) -> None:
        self.redactor = Redactor()

    def test_sanitize_dict_sensitive_keys(self) -> None:
        data = {
            "password": "plain_password_123",
            "api_key": "raw_api_key_456",
            "client_secret": "raw_client_secret_789",
            "username": "admin",
            "active": True,
            "port": 8080,
        }
        sanitized = self.redactor.sanitize_dict(data)
        self.assertEqual(sanitized["password"], "[REDACTED]")
        self.assertEqual(sanitized["api_key"], "[REDACTED]")
        self.assertEqual(sanitized["client_secret"], "[REDACTED]")
        self.assertEqual(sanitized["username"], "admin")
        self.assertEqual(sanitized["active"], True)
        self.assertEqual(sanitized["port"], 8080)

    def test_sanitize_dict_nested_and_lists(self) -> None:
        data = {
            "config": {
                "auth": {
                    "password": "nested_secret",
                    "token": "ghp_123456789012345678901234",
                },
                "server": {
                    "home_dir": "/home/developer/app",
                },
            },
            "tokens": [
                "sk-proj-123456789012345678901234",
                "AKIAIOSFODNN7EXAMPLE",  # along: allow-no-tracked-secrets
                "normal_string",
            ],
        }
        sanitized = self.redactor.sanitize_dict(data)
        self.assertEqual(sanitized["config"]["auth"]["password"], "[REDACTED]")
        self.assertEqual(sanitized["config"]["auth"]["token"], "[REDACTED_GITHUB_TOKEN]")
        self.assertEqual(sanitized["config"]["server"]["home_dir"], "~/app")
        self.assertEqual(sanitized["tokens"][0], "sk-[REDACTED]")
        self.assertEqual(sanitized["tokens"][1], "[REDACTED_AWS_KEY]")
        self.assertEqual(sanitized["tokens"][2], "normal_string")

    def test_sanitize_value_types(self) -> None:
        # String
        self.assertEqual(self.redactor.sanitize_value("Bearer 12345"), "Bearer [REDACTED]")
        # Tuple
        tup = ("sk-123456789012345678901234", 10)
        self.assertEqual(self.redactor.sanitize_value(tup), ("sk-[REDACTED]", 10))
        # Set
        s = {"/home/alice/data"}
        self.assertEqual(self.redactor.sanitize_value(s), {"~/data"})
        # Primitives
        self.assertIsNone(self.redactor.sanitize_value(None))
        self.assertEqual(self.redactor.sanitize_value(123), 123)
        self.assertEqual(self.redactor.sanitize_value(3.14), 3.14)
        self.assertEqual(self.redactor.sanitize_value(True), True)


class TestArtifactOffloader(unittest.TestCase):
    def test_small_payload_no_offload(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            offloader = ArtifactOffloader(repo_root=tmp_dir, run_id="run-001", max_bytes=100, max_lines=10)
            content = "line 1\nline 2\nline 3"
            preview, ref = offloader.maybe_offload(content)
            self.assertEqual(preview, content)
            self.assertIsNone(ref)
            # Verify no artifacts directory was created
            artifacts_dir = os.path.join(tmp_dir, ".along", "artifacts", "run-001")
            self.assertFalse(os.path.exists(artifacts_dir))

    def test_large_bytes_payload_offload(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            offloader = ArtifactOffloader(repo_root=tmp_dir, run_id="run-002", max_bytes=50, max_lines=100)
            content = "A" * 120  # 120 bytes, 1 line
            preview, ref = offloader.maybe_offload(content, ext="txt")
            self.assertIsNotNone(ref)
            assert ref is not None

            expected_sha = hashlib.sha256(content.encode("utf-8")).hexdigest()
            self.assertEqual(ref.sha256, expected_sha)
            self.assertEqual(ref.artifact_id, expected_sha)
            self.assertEqual(ref.size_bytes, 120)
            self.assertEqual(ref.line_count, 1)
            self.assertEqual(ref.mime_type, "text/plain")
            self.assertEqual(ref.path, f".along/artifacts/run-002/{expected_sha}.txt")

            # Verify file exists on disk and content matches
            target_file = os.path.join(tmp_dir, ".along", "artifacts", "run-002", f"{expected_sha}.txt")
            self.assertTrue(os.path.isfile(target_file))
            with open(target_file, "r", encoding="utf-8") as f:
                saved_content = f.read()
            self.assertEqual(saved_content, content)

            # Check preview formatting
            self.assertIn(f"... [Output offloaded to .along/artifacts/run-002/{expected_sha}.txt (120 bytes, 1 lines)]", preview)

    def test_large_lines_payload_offload(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            offloader = ArtifactOffloader(repo_root=tmp_dir, run_id="run-003", max_bytes=10000, max_lines=5)
            lines = [f"line {i}" for i in range(10)]
            content = "\n".join(lines)
            preview, ref = offloader.maybe_offload(content, ext="log", preview_lines=3)
            self.assertIsNotNone(ref)
            assert ref is not None

            self.assertEqual(ref.line_count, 10)
            self.assertEqual(ref.mime_type, "text/plain")

            # Check preview lines truncated to 3 lines
            expected_preview_body = "line 0\nline 1\nline 2"
            self.assertTrue(preview.startswith(expected_preview_body))
            self.assertIn(f"... [Output offloaded to {ref.path} ({ref.size_bytes} bytes, 10 lines)]", preview)

    def test_preview_capped_at_preview_chars(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            offloader = ArtifactOffloader(repo_root=tmp_dir, run_id="run-004", max_bytes=50, max_lines=50)
            content = "X" * 200
            preview, ref = offloader.maybe_offload(content, preview_chars=20)
            self.assertIsNotNone(ref)
            assert ref is not None
            self.assertTrue(preview.startswith("X" * 20 + "\n... [Output offloaded to"))

    def test_custom_extensions_and_mime_types(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            offloader = ArtifactOffloader(repo_root=tmp_dir, run_id="run-005", max_bytes=10)
            content = '{"key": "value", "items": [1, 2, 3]}'
            _, ref = offloader.maybe_offload(content, ext=".json")
            self.assertIsNotNone(ref)
            assert ref is not None
            self.assertEqual(ref.mime_type, "application/json")
            self.assertTrue(ref.path.endswith(".json"))

            diff_content = "diff --git a/test.py b/test.py\nindex 123..456\n+added line\n"
            _, ref2 = offloader.maybe_offload(diff_content, ext="diff")
            self.assertIsNotNone(ref2)
            assert ref2 is not None
            self.assertEqual(ref2.mime_type, "text/x-diff")
            self.assertTrue(ref2.path.endswith(".diff"))

    def test_idempotent_write(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            offloader = ArtifactOffloader(repo_root=tmp_dir, run_id="run-006", max_bytes=10)
            content = "Duplicate offload content payload"
            _, ref1 = offloader.maybe_offload(content)
            _, ref2 = offloader.maybe_offload(content)
            self.assertIsNotNone(ref1)
            self.assertIsNotNone(ref2)
            assert ref1 is not None and ref2 is not None
            self.assertEqual(ref1.sha256, ref2.sha256)
            self.assertEqual(ref1.path, ref2.path)


if __name__ == "__main__":
    unittest.main()
