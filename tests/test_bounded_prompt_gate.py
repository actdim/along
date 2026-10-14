#!/usr/bin/env python3
"""
tests/test_bounded_prompt_gate.py - Hermetic tests for Bounded Step Prompt Gate and Attention Leak Detector.

Covers [feat--bounded-prompt-footprint-gate] REQ-1, REQ-2, REQ-3, REQ-4:
- Declarative gate specification and runtime enforcement.
- Prompt footprint thresholds: 16 KB soft warning, 32 KB hard denial.
- Attention leak detectors: unparsed logs (> 50 lines), repeated reviews, raw code dumps (> 50 lines).
- CLI verification: along budget check-prompt <file|payload> (--json, --check, --allow-oversized).
- Activity trace recording in diagnostics.
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

from alongkit import bootstrap
bootstrap.ensure_deps()

from alongkit import budget, proc
from alongkit.hooks import HookEvent, HookEventType, GateDecision, GateResult
from alongkit.hooks import declarative, predicates
from hermetic import make_repo_fixture


class TestPromptBudgetEngine(unittest.TestCase):
    """Unit tests for alongkit.budget prompt measurement and attention leak detection."""

    def test_compliant_prompt_passes(self):
        text = "Implement user authentication with JWT tokens following existing patterns."
        rep = budget.check_prompt(text)
        self.assertEqual(rep["status"], "PASS")
        self.assertTrue(rep["passed"])
        self.assertFalse(rep["warn"])
        self.assertFalse(rep["is_oversized"])
        self.assertEqual(len(rep["leaks"]), 0)

    def test_soft_warning_threshold(self):
        # 16 KB is 16,384 bytes. Create payload between 16 KB and 32 KB.
        text = "A" * 20000
        rep = budget.check_prompt(text)
        self.assertEqual(rep["status"], "WARN")
        self.assertTrue(rep["passed"])
        self.assertTrue(rep["warn"])
        self.assertFalse(rep["is_oversized"])

    def test_hard_limit_rejection(self):
        # 32 KB is 32,768 bytes. Create payload exceeding 32 KB.
        text = "B" * 35000
        rep = budget.check_prompt(text)
        self.assertEqual(rep["status"], "FAIL")
        self.assertFalse(rep["passed"])
        self.assertTrue(rep["is_oversized"])

    def test_override_flag_allows_oversized(self):
        text = "C" * 35000
        rep = budget.check_prompt(text, allow_oversized=True)
        self.assertEqual(rep["status"], "WARN")
        self.assertTrue(rep["passed"])
        self.assertTrue(rep["is_oversized"])

    def test_unparsed_log_detection(self):
        # 60 lines of traceback and test failures
        log_lines = ["Traceback (most recent call last):"]
        for i in range(55):
            log_lines.append(f'  File "module_{i}.py", line {i}, in test_func')
            log_lines.append(f"    AssertionError: expected value {i} but got None")
        payload = "```log\n" + "\n".join(log_lines) + "\n```"

        leaks = budget.detect_attention_leaks(payload)
        self.assertTrue(any(l["type"] == "unparsed_log" for l in leaks))

        rep = budget.check_prompt(payload)
        self.assertTrue(rep["warn"])
        self.assertTrue(any(l["type"] == "unparsed_log" for l in rep["leaks"]))

    def test_repeated_reviews_detection(self):
        # Repeating previous review manifests in prompt
        review_block = (
            "Gate Execution Manifest:\n"
            "- Workspace Isolation: EXECUTED (PASS)\n"
            "- Automated Tests: EXECUTED (PASS)\n"
            "VERDICT: PASS\n"
        )
        prompt_with_repetition = (
            "Step 3 instructions:\n"
            + review_block
            + "\nContext from previous step:\n"
            + review_block
        )
        leaks = budget.detect_attention_leaks(prompt_with_repetition)
        self.assertTrue(any(l["type"] == "repeated_reviews" for l in leaks))

        rep = budget.check_prompt(prompt_with_repetition)
        self.assertTrue(any(l["type"] == "repeated_reviews" for l in rep["leaks"]))

    def test_raw_code_dump_detection(self):
        # Code fence with > 50 lines of Python implementation
        code_lines = ["```python", "import sys", "import os", ""]
        for i in range(60):
            code_lines.append(f"def helper_function_{i}(arg: int) -> int:")
            code_lines.append(f"    return arg * {i}")
        code_lines.append("```")
        payload = "\n".join(code_lines)

        leaks = budget.detect_attention_leaks(payload)
        self.assertTrue(any(l["type"] == "raw_file_dump" for l in leaks))

        rep = budget.check_prompt(payload)
        self.assertTrue(any(l["type"] == "raw_file_dump" for l in rep["leaks"]))

    def test_file_reading_and_format_text(self):
        with tempfile.NamedTemporaryFile("w", delete=False, suffix=".md", encoding="utf-8") as f:
            f.write("Clean prompt text inside temporary file.")
            path = f.name
        try:
            rep = budget.check_prompt(path)
            self.assertEqual(rep["status"], "PASS")
            self.assertEqual(rep["path"], path)
            formatted = budget.format_prompt_budget_text(rep)
            self.assertIn("=== Along Prompt Footprint & Attention Leak Report ===", formatted)
            self.assertIn("[PASS]", formatted)
            self.assertIn(path, formatted)
        finally:
            if os.path.exists(path):
                os.remove(path)


class TestBoundedPromptGatePredicate(unittest.TestCase):
    """Tests for check_bounded_prompt_footprint predicate and activity trace recording."""

    def setUp(self):
        self.root = make_repo_fixture(prefix="prompt-gate-", with_docs=False)

    def tearDown(self):
        shutil.rmtree(self.root, ignore_errors=True)

    def test_compliant_invoke_subagent_passes(self):
        event = HookEvent(
            event_type=HookEventType.PRE_TOOL_USE,
            tool_name="invoke_subagent",
            tool_args={
                "Subagents": [
                    {"Role": "Worker", "Prompt": "Implement step 1 following plan."}
                ]
            },
            workspace_root=self.root,
        )
        res = predicates.check_bounded_prompt_footprint(event, repo_root=self.root)
        self.assertIsNone(res)

        # Activity trace recorded
        trace = predicates.load_activity_trace(self.root)
        self.assertIn("prompt_budget", trace)
        self.assertGreater(trace["prompt_budget"]["total_checks"], 0)

    def test_oversized_payload_denies_execution(self):
        oversized = "X" * 35000
        event = HookEvent(
            event_type=HookEventType.PRE_TOOL_USE,
            tool_name="invoke_subagent",
            tool_args={
                "Subagents": [
                    {"Role": "Worker", "Prompt": oversized}
                ]
            },
            workspace_root=self.root,
        )
        res = predicates.check_bounded_prompt_footprint(event, repo_root=self.root)
        self.assertIsInstance(res, GateResult)
        self.assertEqual(res.decision, GateDecision.DENY)
        self.assertIn("[gate: bounded-prompt-gate]", res.reason)
        self.assertEqual(res.exit_code, 2)

        # Activity trace increments violation
        trace = predicates.load_activity_trace(self.root)
        self.assertGreaterEqual(trace["prompt_budget"]["violations"], 1)

    def test_oversized_payload_with_override_passes_with_advisory(self):
        oversized = "Y" * 35000
        event = HookEvent(
            event_type=HookEventType.PRE_TOOL_USE,
            tool_name="invoke_subagent",
            tool_args={
                "allow_oversized_prompt": True,
                "Subagents": [
                    {"Role": "Worker", "Prompt": oversized}
                ]
            },
            workspace_root=self.root,
        )
        res = predicates.check_bounded_prompt_footprint(event, repo_root=self.root)
        self.assertIsInstance(res, GateResult)
        self.assertEqual(res.decision, GateDecision.ALLOW)
        self.assertIn("Advisory [gate: bounded-prompt-gate]", res.reason)

    def test_task_tool_extraction(self):
        event = HookEvent(
            event_type=HookEventType.PRE_TOOL_USE,
            tool_name="Task",
            tool_args={"prompt": "Do task cleanly."},
            workspace_root=self.root,
        )
        res = predicates.check_bounded_prompt_footprint(event, repo_root=self.root)
        self.assertIsNone(res)

    def test_send_message_extraction(self):
        event = HookEvent(
            event_type=HookEventType.PRE_TOOL_USE,
            tool_name="send_message",
            tool_args={"Recipient": "sub-1", "Message": "Z" * 35000},
            workspace_root=self.root,
        )
        res = predicates.check_bounded_prompt_footprint(event, repo_root=self.root)
        self.assertIsInstance(res, GateResult)
        self.assertEqual(res.decision, GateDecision.DENY)


class TestDeclarativeGateIntegration(unittest.TestCase):
    """Tests declarative gate catalogue loading and profile evaluation for bounded_prompt_gate."""

    def test_gate_catalog_contains_bounded_prompt_gate(self):
        gates = declarative.get_all_declarative_gates(repo_root=REPO_ROOT)
        gate_names = [g.name for g in gates]
        self.assertIn("bounded_prompt_gate", gate_names)

        target = next(g for g in gates if g.name == "bounded_prompt_gate")
        self.assertEqual(target.defn.event_type, HookEventType.PRE_TOOL_USE)
        self.assertIn("invoke_subagent", target.defn.tools)
        self.assertIn("Task", target.defn.tools)
        self.assertEqual(target.defn.profiles.get("strict"), "block")
        self.assertEqual(target.defn.profiles.get("light"), "warn")


class TestCliBudgetCheckPrompt(unittest.TestCase):
    """End-to-end CLI tests for along budget check-prompt."""

    def test_cli_check_prompt_pass(self):
        res = proc.run_capture(
            [sys.executable, os.path.join(SCRIPTS_DIR, "along_exec.py"), "budget", "check-prompt", "Small test prompt."],
            cwd=REPO_ROOT,
        )
        self.assertEqual(res.returncode, 0)
        self.assertIn("[PASS]", res.stdout)
        self.assertIn("ALL PROMPT CHECKS PASSED", res.stdout)

    def test_cli_check_prompt_json(self):
        res = proc.run_capture(
            [sys.executable, os.path.join(SCRIPTS_DIR, "along_exec.py"), "budget", "check-prompt", "JSON test prompt.", "--json"],
            cwd=REPO_ROOT,
        )
        self.assertEqual(res.returncode, 0)
        data = json.loads(res.stdout)
        self.assertEqual(data["status"], "PASS")
        self.assertTrue(data["passed"])

    def test_cli_check_prompt_fail_under_check_flag(self):
        with tempfile.NamedTemporaryFile("w", delete=False, suffix=".txt", encoding="utf-8") as f:
            f.write("W" * 35000)
            path = f.name
        try:
            res = proc.run_capture(
                [sys.executable, os.path.join(SCRIPTS_DIR, "along_exec.py"), "budget", "check-prompt", path, "--check"],
                cwd=REPO_ROOT,
            )
            self.assertEqual(res.returncode, 1)
            self.assertIn("[FAIL]", res.stdout)
        finally:
            if os.path.exists(path):
                os.remove(path)


if __name__ == "__main__":
    unittest.main()
