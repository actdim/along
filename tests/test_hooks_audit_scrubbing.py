#!/usr/bin/env python3
"""
tests/test_hooks_audit_scrubbing.py - Unit tests for secret scrubbing in hook audit logs and circuit diagnostics.

Verifies:
- REQ-1: Redactor sanitizes all audit entry strings before appending to hooks_audit.jsonl.
- REQ-2: Redactor sanitizes command arguments and error details in circuit_breaker.json and reports.
- REQ-3: Fast-path zero-allocation detection in Redactor returns clean strings intact.
- REQ-5: Strict backward compatibility of hooks_audit.jsonl JSON schema.
"""

from __future__ import annotations

import json
import os
import shutil
import sys
import tempfile
import unittest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPTS_DIR = os.path.join(REPO_ROOT, "scripts")
if SCRIPTS_DIR not in sys.path:
    sys.path.insert(0, SCRIPTS_DIR)

from alongkit.circuit import (
    AnomalyClass,
    AnomalyMatch,
    load_circuit_state,
    save_circuit_state,
    trip_breaker,
)
from alongkit.hooks import (
    GateDecision,
    GateResult,
    HookEvent,
    HookEventType,
)
from alongkit.hooks.config import HookMode, record_audit_entry
from alongkit.telemetry.redactor import Redactor


class TestRedactorFastPath(unittest.TestCase):
    def setUp(self) -> None:
        self.redactor = Redactor()

    def test_has_candidates_negative(self) -> None:
        clean_samples = [
            "",
            "cli_safety",
            "write_to_file",
            "run_shell",
            "allow",
            "deny",
            "antigravity",
            "Typography Gate Violation: Detected non-ASCII character",
            "src/utils.py",
            "Normal status report without any sensitive items",
        ]
        for sample in clean_samples:
            with self.subTest(sample=sample):
                self.assertFalse(self.redactor.has_candidates(sample))
                self.assertFalse(Redactor.has_candidates(sample))
                self.assertFalse(self.redactor.has_sensitive_candidates(sample))

    def test_has_candidates_positive(self) -> None:
        sensitive_samples = [
            "sk-ant-api03-abcdef12345678901234567890",  # along: allow-no-tracked-secrets
            "sk-proj-abcdef12345678901234567890",  # along: allow-no-tracked-secrets
            "ghp_123456789012345678901234",  # along: allow-no-tracked-secrets
            "github_pat_11ABCD1234567890123456_abcdef",  # along: allow-no-tracked-secrets
            "AKIAIOSFODNN7EXAMPLE",  # along: allow-no-tracked-secrets
            "ASIAIOSFODNN7EXAMPLE",  # along: allow-no-tracked-secrets
            "Authorization: Bearer secret_token",
            "bearer eyJhbGciOiJIUzI1NiI...",
            "-----BEGIN RSA PRIVATE KEY-----",  # along: allow-no-tracked-secrets
            "password: my_secret_value",
            "api_key = 'abcdef'",
            "access_token: tok_123",
            "client_secret = 'super_secret'",
            r"C:\Users\Admin\Desktop\app.log",
            r"D:\Documents and Settings\John\file.txt",
            "/home/developer/workspace/app.py",
            "/Users/bob/project/test.py",
        ]
        for sample in sensitive_samples:
            with self.subTest(sample=sample):
                self.assertTrue(self.redactor.has_candidates(sample))
                self.assertTrue(Redactor.has_candidates(sample))

    def test_sanitize_text_fast_path_identity(self) -> None:
        clean = "cli_safety_clean_tool_invocation"
        sanitized = self.redactor.sanitize_text(clean)
        self.assertIs(clean, sanitized)

    def test_sanitize_text_redacts_tokens(self) -> None:
        raw_key = "sk-ant-api03-123456789012345678901234567890"  # along: allow-no-tracked-secrets
        raw = f"Header: Bearer {raw_key} with AWS AKIAIOSFODNN7EXAMPLE and ghp_123456789012345678901234"  # along: allow-no-tracked-secrets
        sanitized = self.redactor.sanitize_text(raw)
        self.assertNotIn("123456789012345678901234567890", sanitized)
        self.assertNotIn("AKIAIOSFODNN7EXAMPLE", sanitized)  # along: allow-no-tracked-secrets
        self.assertNotIn("ghp_123456789012345678901234", sanitized)
        self.assertIn("Bearer [REDACTED]", sanitized)
        self.assertIn("[REDACTED_AWS_KEY]", sanitized)
        self.assertIn("[REDACTED_GITHUB_TOKEN]", sanitized)


class TestHooksAuditScrubbing(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.mkdtemp(prefix="along-audit-scrub-")
        os.makedirs(os.path.join(self.tmp, ".along", "ISSUES"), exist_ok=True)

    def tearDown(self) -> None:
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_record_audit_entry_scrubs_secrets_in_reason(self) -> None:
        anthropic_key = "sk-ant-api03-123456789012345678901234567890"  # along: allow-no-tracked-secrets
        gh_token = "ghp_123456789012345678901234"  # along: allow-no-tracked-secrets
        aws_key = "AKIAIOSFODNN7EXAMPLE"  # along: allow-no-tracked-secrets

        sensitive_reason = (
            f"Blocked command containing Authorization: Bearer {anthropic_key}, "
            f"github token {gh_token}, aws {aws_key}, and home /home/developer/secrets.txt"
        )
        event = HookEvent(
            event_type=HookEventType.PRE_TOOL_USE,
            tool_name="run_shell",
            tool_args={"command": "curl -H 'Authorization: Bearer ...'"},
            workspace_root=self.tmp,
            runtime="antigravity",
            conversation_id="conv-123",
            step_idx=4,
        )
        result = GateResult(
            decision=GateDecision.DENY,
            reason=sensitive_reason,
            gate_name="cli_safety",
        )

        record_audit_entry(self.tmp, event, result, HookMode.ENFORCE)

        audit_file = os.path.join(self.tmp, ".along", "diagnostics", "hooks_audit.jsonl")
        self.assertTrue(os.path.isfile(audit_file))
        with open(audit_file, "r", encoding="utf-8") as handle:
            lines = handle.readlines()
        self.assertEqual(len(lines), 1)

        record = json.loads(lines[0])
        # Verify strict JSON schema keys (REQ-5)
        expected_keys = [
            "timestamp",
            "gate",
            "decision",
            "mode",
            "runtime",
            "tool",
            "reason",
            "conversation_id",
            "step_idx",
        ]
        self.assertEqual(list(record.keys()), expected_keys)

        # Verify values
        self.assertEqual(record["gate"], "cli_safety")
        self.assertEqual(record["decision"], "deny")
        self.assertEqual(record["mode"], "enforce")
        self.assertEqual(record["runtime"], "antigravity")
        self.assertEqual(record["tool"], "run_shell")
        self.assertEqual(record["conversation_id"], "conv-123")
        self.assertEqual(record["step_idx"], 4)

        # Verify secrets are scrubbed
        logged_reason = record["reason"]
        self.assertNotIn(anthropic_key, logged_reason)
        self.assertNotIn(gh_token, logged_reason)
        self.assertNotIn(aws_key, logged_reason)
        self.assertNotIn("/home/developer", logged_reason)
        self.assertIn("Bearer [REDACTED]", logged_reason)
        self.assertIn("[REDACTED_GITHUB_TOKEN]", logged_reason)
        self.assertIn("[REDACTED_AWS_KEY]", logged_reason)
        self.assertIn("~/secrets.txt", logged_reason)

    def test_record_audit_entry_scrubs_tool_name(self) -> None:
        tool_with_secret = "curl -H 'Authorization: Bearer secret_access_token_12345'"
        event = HookEvent(
            event_type=HookEventType.PRE_TOOL_USE,
            tool_name=tool_with_secret,
            workspace_root=self.tmp,
            runtime="antigravity",
        )
        result = GateResult(
            decision=GateDecision.DENY,
            reason="Command denied",
            gate_name="cli_safety",
        )

        record_audit_entry(self.tmp, event, result, HookMode.ENFORCE)

        audit_file = os.path.join(self.tmp, ".along", "diagnostics", "hooks_audit.jsonl")
        with open(audit_file, "r", encoding="utf-8") as handle:
            record = json.loads(handle.readline())

        self.assertEqual(record["tool"], "curl -H 'Authorization: Bearer [REDACTED]'")
        self.assertEqual(record["reason"], "Command denied")

    def test_record_audit_entry_backward_compatibility(self) -> None:
        event = HookEvent(
            event_type=HookEventType.PRE_TOOL_USE,
            tool_name="write_to_file",
            workspace_root=self.tmp,
            runtime="antigravity",
            conversation_id="conv-456",
            step_idx=2,
        )
        result = GateResult(
            decision=GateDecision.ALLOW,
            reason=None,
            gate_name="typography",
        )

        record_audit_entry(self.tmp, event, result, HookMode.SHADOW)

        audit_file = os.path.join(self.tmp, ".along", "diagnostics", "hooks_audit.jsonl")
        with open(audit_file, "r", encoding="utf-8") as handle:
            record = json.loads(handle.readline())

        self.assertIsNone(record["reason"])
        self.assertEqual(record["gate"], "typography")
        self.assertEqual(record["decision"], "allow")
        self.assertEqual(record["mode"], "shadow")
        self.assertEqual(record["runtime"], "antigravity")
        self.assertEqual(record["tool"], "write_to_file")
        self.assertEqual(record["conversation_id"], "conv-456")
        self.assertEqual(record["step_idx"], 2)


class TestCircuitBreakerDiagnosticsScrubbing(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.mkdtemp(prefix="along-circuit-scrub-")
        os.makedirs(os.path.join(self.tmp, ".along", "ISSUES"), exist_ok=True)

    def tearDown(self) -> None:
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_trip_breaker_scrubs_command_args_and_anomaly(self) -> None:
        anthropic_key = "sk-ant-api03-123456789012345678901234567890"  # along: allow-no-tracked-secrets
        sensitive_cmd = f"curl -H 'Authorization: Bearer {anthropic_key}' https://api.anthropic.com"
        aws_token = "AKIAIOSFODNN7EXAMPLE"  # along: allow-no-tracked-secrets
        sensitive_detail = f"fatal error at /home/admin/config.json with key {aws_token}"

        anomaly = AnomalyMatch(
            anomaly_class=AnomalyClass.CLASS_3_GLOBAL_ENV,
            signature="Prohibited toolchain anomaly",
            detail=sensitive_detail,
            impact="Fatal failure with credential leak risk",
            remediation=("Remediate immediately",),
            source=sensitive_cmd,
        )

        report = trip_breaker(self.tmp, anomaly)

        # 1. Escalation report stderr rendering must be redacted
        self.assertNotIn(anthropic_key, report)
        self.assertNotIn(aws_token, report)
        self.assertNotIn("/home/admin", report)
        self.assertIn("Bearer [REDACTED]", report)
        self.assertIn("[REDACTED_AWS_KEY]", report)
        self.assertIn("~/config.json", report)

        # 2. circuit_breaker.json on disk must be redacted
        state = load_circuit_state(self.tmp)
        self.assertEqual(state["state"], "tripped")
        anomaly_dict = state["anomaly"]
        self.assertIsNotNone(anomaly_dict)
        self.assertNotIn(anthropic_key, anomaly_dict["source"])
        self.assertNotIn(aws_token, anomaly_dict["detail"])
        self.assertNotIn("/home/admin", anomaly_dict["detail"])
        self.assertIn("Bearer [REDACTED]", anomaly_dict["source"])
        self.assertIn("[REDACTED_AWS_KEY]", anomaly_dict["detail"])
        self.assertIn("~/config.json", anomaly_dict["detail"])

    def test_save_circuit_state_sanitizes_history_and_extra_data(self) -> None:
        gh_token = "ghp_123456789012345678901234"  # along: allow-no-tracked-secrets
        data = {
            "state": "tripped",
            "anomaly": None,
            "history": [
                {
                    "source": f"git clone https://{gh_token}@github.com/repo.git",
                    "detail": "auth failed for password: my_plain_password",
                }
            ],
            "password": "unmasked_password",
        }

        save_circuit_state(self.tmp, data)

        state_file = os.path.join(self.tmp, ".along", "diagnostics", "circuit_breaker.json")
        self.assertTrue(os.path.isfile(state_file))
        with open(state_file, "r", encoding="utf-8") as handle:
            saved = json.load(handle)

        self.assertNotIn(gh_token, saved["history"][0]["source"])
        self.assertIn("[REDACTED_GITHUB_TOKEN]", saved["history"][0]["source"])
        self.assertIn("password: [REDACTED]", saved["history"][0]["detail"])
        self.assertEqual(saved["password"], "[REDACTED]")


if __name__ == "__main__":
    unittest.main()
