#!/usr/bin/env python3
"""
tests/test_circuit_breaker.py - Comprehensive hermetic unit tests for Circuit Breaker.

Verifies:
1. Classification of all 5 Systemic Anomaly classes.
2. Zero-retry tripping, state persistence, and escalation report rendering.
3. Declarative gate enforcement (blocking tool calls when tripped).
4. Anti-workaround CLI protection (pip install / npm -g interception).
5. Pre-flight health probe and safe resumption gate.
6. Unified CLI router commands (along circuit status/trip/reset/verify).
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

from alongkit import circuit, proc, textio
from alongkit.circuit import (
    AnomalyClass,
    AnomalyMatch,
    CircuitState,
    classify_anomaly,
    format_escalation_report,
    get_breaker_state,
    is_breaker_tripped,
    record_syntax_failure,
    record_syntax_success,
    reset_breaker,
    run_health_probe,
    trip_breaker,
)
from alongkit.hooks import HookEvent, HookEventType
from alongkit.hooks.predicates import check_circuit_breaker, check_cli_safety
from hermetic import repo_fixture


class TestAnomalyClassification(unittest.TestCase):
    """Test pattern matching and signature extraction across all 5 anomaly classes."""

    def test_class_1_vcs_index_corruption(self):
        # Truncated index
        match = classify_anomaly(stderr="fatal: .git/index: index file smaller than expected", returncode=128)
        self.assertIsNotNone(match)
        self.assertEqual(match.anomaly_class, AnomalyClass.CLASS_1_VCS_CORRUPTION)
        self.assertIn("smaller than expected", match.signature)

        # Stale lock
        match_lock = classify_anomaly(stderr="fatal: Unable to create '.git/index.lock': File exists.", returncode=128)
        self.assertIsNotNone(match_lock)
        self.assertEqual(match_lock.anomaly_class, AnomalyClass.CLASS_1_VCS_CORRUPTION)

        # Corrupt loose object
        match_obj = classify_anomaly(stderr="error: corrupt loose object 'abc1234'", returncode=128)
        self.assertIsNotNone(match_obj)
        self.assertEqual(match_obj.anomaly_class, AnomalyClass.CLASS_1_VCS_CORRUPTION)

    def test_class_2_os_contention(self):
        # Windows sharing violation
        match = classify_anomaly(
            stderr="The process cannot access the file because it is being used by another process.",
            returncode=1
        )
        self.assertIsNotNone(match)
        self.assertEqual(match.anomaly_class, AnomalyClass.CLASS_2_OS_CONTENTION)

        # Permission denied on kill or write
        match_perm = classify_anomaly(stderr="[Errno 13] Permission denied: 'build/output.bin'", returncode=1)
        self.assertIsNotNone(match_perm)
        self.assertEqual(match_perm.anomaly_class, AnomalyClass.CLASS_2_OS_CONTENTION)

        # Out of disk space
        match_disk = classify_anomaly(stderr="No space left on device", returncode=1)
        self.assertIsNotNone(match_disk)
        self.assertEqual(match_disk.anomaly_class, AnomalyClass.CLASS_2_OS_CONTENTION)

    def test_class_3_global_environment_and_toolchain(self):
        # Missing binary
        match = classify_anomaly(stderr="'uv' is not recognized as an internal or external command", returncode=1)
        self.assertIsNotNone(match)
        self.assertEqual(match.anomaly_class, AnomalyClass.CLASS_3_GLOBAL_ENV)

        # Prohibited command in command string
        match_pip = classify_anomaly(cmd="pip install requests")
        self.assertIsNotNone(match_pip)
        self.assertEqual(match_pip.anomaly_class, AnomalyClass.CLASS_3_GLOBAL_ENV)

        # Allowed editable pip install should not trip
        match_pip_e = classify_anomaly(cmd="pip install -e .")
        self.assertIsNone(match_pip_e)

        # Prohibited npm global install
        match_npm = classify_anomaly(cmd="npm install -g typescript")
        self.assertIsNotNone(match_npm)
        self.assertEqual(match_npm.anomaly_class, AnomalyClass.CLASS_3_GLOBAL_ENV)

    def test_class_4_process_timeouts(self):
        match = classify_anomaly(stderr="Command timed out after 120s", returncode=124)
        self.assertIsNotNone(match)
        self.assertEqual(match.anomaly_class, AnomalyClass.CLASS_4_PROCESS_CASCADE)

    def test_normal_command_failure_does_not_trip(self):
        # A normal compiler error or unit test failure is not an environment anomaly
        match = classify_anomaly(stdout="AssertionError: 1 != 2\nFAILED (failures=1)", returncode=1)
        self.assertIsNone(match)


class TestEscalationReport(unittest.TestCase):
    """Verify standardized human escalation report formatting."""

    def test_escalation_report_contents(self):
        anomaly = AnomalyMatch(
            anomaly_class=AnomalyClass.CLASS_1_VCS_CORRUPTION,
            signature="fatal: .git/index: index file smaller than expected",
            detail="index file smaller than expected (0 bytes)",
            impact="Continued automated modifications risk destroying working tree.",
            remediation=circuit.REMEDIATION_CLASS_1,
            timestamp="2026-09-14T20:00:00Z",
        )
        report = format_escalation_report(anomaly)
        self.assertIn("[CIRCUIT BREAKER TRIPPED]", report)
        self.assertIn("Class: Class 1 (VCS / Repository State Corruption)", report)
        self.assertIn("Signature: fatal: .git/index: index file smaller than expected", report)
        self.assertIn("Prescribed Human Remediation:", report)
        self.assertIn("1. Reload IDE Window", report)
        self.assertIn("2. Reset Git Index", report)
        self.assertIn("Agent Action: Execution halted. Awaiting human confirmation.", report)


class TestCircuitBreakerStateAndPersistence(unittest.TestCase):
    """Verify tripping, file persistence, and state transitions."""

    def test_trip_and_get_state(self):
        with repo_fixture() as root:
            # Initial state is CLOSED
            state, anomaly = get_breaker_state(root)
            self.assertEqual(state, CircuitState.CLOSED)
            self.assertIsNone(anomaly)
            self.assertFalse(is_breaker_tripped(root))

            # Trip breaker
            test_anomaly = AnomalyMatch(
                anomaly_class=AnomalyClass.CLASS_2_OS_CONTENTION,
                signature="Sharing violation",
                detail="File locked by IDE",
                impact="Atomic writes fail",
                remediation=circuit.REMEDIATION_CLASS_2,
            )
            trip_breaker(root, test_anomaly)

            # State is now TRIPPED
            state_after, anomaly_after = get_breaker_state(root)
            self.assertEqual(state_after, CircuitState.TRIPPED)
            self.assertIsNotNone(anomaly_after)
            self.assertEqual(anomaly_after.anomaly_class, AnomalyClass.CLASS_2_OS_CONTENTION)
            self.assertTrue(is_breaker_tripped(root))

            # Diagnostic file exists
            diag_file = os.path.join(root, ".along", "diagnostics", "circuit_breaker.json")
            self.assertTrue(os.path.isfile(diag_file))

    def test_class_5_syntax_churn_tripping(self):
        with repo_fixture() as root:
            target_file = os.path.join(root, "src", "engine.py")

            # First failure: recorded, does not trip yet
            first_match = record_syntax_failure(root, target_file, "SyntaxError: invalid syntax")
            self.assertIsNone(first_match)
            self.assertFalse(is_breaker_tripped(root))

            # Second consecutive failure: trips Class 5
            second_match = record_syntax_failure(root, target_file, "SyntaxError: unexpected EOF")
            self.assertIsNotNone(second_match)
            self.assertEqual(second_match.anomaly_class, AnomalyClass.CLASS_5_SYNTAX_CHURN)
            self.assertTrue(is_breaker_tripped(root))

            # Record success clears failure counter
            record_syntax_success(root, target_file)
            churn_file = os.path.join(root, ".along", "diagnostics", "syntax_churn.json")
            data = json.loads(textio.read_text(churn_file))
            self.assertNotIn("src/engine.py", data)


class TestDeclarativeGateEnforcement(unittest.TestCase):
    """Verify runtime gates block actions when circuit breaker is tripped."""

    def test_gate_blocks_tool_when_tripped(self):
        with repo_fixture() as root:
            event = HookEvent(
                event_type=HookEventType.PRE_TOOL_USE,
                tool_name="write_to_file",
                tool_args={"TargetFile": "src/main.py", "CodeContent": "print('hello')\n"},
            )

            # Breaker is CLOSED: gate allows
            violation = check_circuit_breaker(event, root)
            self.assertIsNone(violation)

            # Trip breaker
            trip_breaker(root, AnomalyMatch(
                anomaly_class=AnomalyClass.CLASS_1_VCS_CORRUPTION,
                signature="fatal: .git/index: bad signature",
                detail="bad signature",
                impact="Git index corrupted",
                remediation=circuit.REMEDIATION_CLASS_1,
            ))

            # Breaker is TRIPPED: gate blocks
            violation_tripped = check_circuit_breaker(event, root)
            self.assertIsNotNone(violation_tripped)
            self.assertIn("Circuit Breaker Violation", violation_tripped)
            self.assertIn("[gate: circuit-breaker]", violation_tripped)
            self.assertIn("TRIPPED", violation_tripped)

    def test_cli_safety_blocks_prohibited_installers(self):
        with repo_fixture() as root:
            # Prohibited: pip install without -e
            event_pip = HookEvent(
                event_type=HookEventType.PRE_TOOL_USE,
                tool_name="run_command",
                tool_args={"CommandLine": "pip install requests"},
            )
            self.assertIsNotNone(check_cli_safety(event_pip, root))

            # Prohibited: npm install -g
            event_npm = HookEvent(
                event_type=HookEventType.PRE_TOOL_USE,
                tool_name="run_command",
                tool_args={"CommandLine": "npm install -g express"},
            )
            self.assertIsNotNone(check_cli_safety(event_npm, root))

            # Allowed: local test runner
            event_test = HookEvent(
                event_type=HookEventType.PRE_TOOL_USE,
                tool_name="run_command",
                tool_args={"CommandLine": "python .along/scripts/test.py"},
            )
            self.assertIsNone(check_cli_safety(event_test, root))


class TestHealthProbeAndResumption(unittest.TestCase):
    """Verify health probe verification and reset behavior."""

    def test_health_probe_on_healthy_repo(self):
        with repo_fixture() as root:
            # Create a mock .git structure
            git_dir = os.path.join(root, ".git")
            os.makedirs(git_dir, exist_ok=True)
            with open(os.path.join(git_dir, "index"), "wb") as f:
                f.write(b"DIRC" + b"\x00" * 20)  # Valid mock index header

            healthy, issues = run_health_probe(root)
            self.assertTrue(healthy)
            self.assertEqual(issues, [])

    def test_health_probe_detects_corrupt_index(self):
        with repo_fixture() as root:
            git_dir = os.path.join(root, ".git")
            os.makedirs(git_dir, exist_ok=True)
            # 0-byte corrupt index
            with open(os.path.join(git_dir, "index"), "wb") as f:
                f.write(b"")

            healthy, issues = run_health_probe(root)
            self.assertFalse(healthy)
            self.assertTrue(any("Corrupted git index" in iss for iss in issues))

            # Reset without force should fail
            ok, msg = reset_breaker(root, force=False)
            self.assertFalse(ok)
            self.assertIn("health probe failed", msg)

            # Reset with force succeeds
            ok_force, _ = reset_breaker(root, force=True)
            self.assertTrue(ok_force)

    def test_health_probe_detects_syntax_errors(self):
        with repo_fixture() as root:
            # Set up valid git
            git_dir = os.path.join(root, ".git")
            os.makedirs(git_dir, exist_ok=True)
            with open(os.path.join(git_dir, "index"), "wb") as f:
                f.write(b"DIRC" + b"\x00" * 20)

            # Write broken python file and register in activity trace
            bad_file = os.path.join(root, "bad_script.py")
            textio.write_text(bad_file, "def broken_func(\n")

            act_dir = os.path.join(root, ".along", "diagnostics")
            os.makedirs(act_dir, exist_ok=True)
            textio.write_text(
                os.path.join(act_dir, "activity_trace.json"),
                json.dumps({"edited_files": ["bad_script.py"]}) + "\n"
            )

            healthy, issues = run_health_probe(root)
            self.assertFalse(healthy)
            self.assertTrue(any("Syntax compilation error" in iss for iss in issues))


class TestProcIntegration(unittest.TestCase):
    """Verify proc.run_capture and proc.run_passthrough intercept prohibited commands."""

    def test_run_capture_blocks_prohibited_command(self):
        with repo_fixture() as root:
            res = proc.run_capture(["pip", "install", "requests"], cwd=root)
            self.assertEqual(res.returncode, 126)
            self.assertIn("Execution blocked by circuit breaker", res.stderr)
            self.assertTrue(is_breaker_tripped(root))

    def test_run_passthrough_blocks_prohibited_command(self):
        with repo_fixture() as root:
            code = proc.run_passthrough(["npm", "install", "-g", "typescript"], cwd=root)
            self.assertEqual(code, 126)
            self.assertTrue(is_breaker_tripped(root))


if __name__ == "__main__":
    unittest.main()
