#!/usr/bin/env python3
"""tests/test_webdev_local_llm.py - Unit tests for offline natural language scenario compiler."""

from __future__ import annotations

import json
import os
import shutil
import sys
import tempfile
import unittest

if not os.environ.get("ALONG_TEST_RUNNER"):
    raise SystemExit(
        "[Error] Tests must not be run directly or via standard test commands (unittest/pytest).\n"
        "To run tests with automatically resolved dependencies, use the official project entry point:\n"
        "    python .along/scripts/test.py"
    )

import hermetic
from alongkit.webdev import schema
from alongkit.webdev.compiler import NLScenarioCompiler
from alongkit.webdev.local_llm import LocalInferenceClient


class TestNLScenarioCompiler(unittest.TestCase):
    """Verify natural language to declarative scenario compilation."""

    def setUp(self) -> None:
        self.compiler = NLScenarioCompiler(base_url="http://localhost:3000")

    def test_russian_instruction_compilation(self) -> None:
        instruction = (
            "открой http://localhost:3000/login, "
            "введи 'alice' в input[name=username], "
            "кликни по 'Войти', "
            "проверь, что виден .dashboard, "
            "сделай скриншот audit.png"
        )
        scenario = self.compiler.compile(instruction, backend="template")
        ok, errors = schema.validate_scenario_dict(scenario)
        self.assertTrue(ok, f"Validation errors: {errors}")

        steps = scenario["checks"][0]["steps"]
        self.assertEqual(len(steps), 5)
        self.assertEqual(steps[0]["action"], "goto")
        self.assertEqual(steps[0]["goto"], "http://localhost:3000/login")
        self.assertEqual(steps[1]["action"], "fill")
        self.assertEqual(steps[1]["selector"], "input[name=username]")
        self.assertEqual(steps[1]["value"], "alice")
        self.assertEqual(steps[2]["action"], "click")
        self.assertEqual(steps[2]["selector"], 'button:has-text("Войти")')
        self.assertEqual(steps[3]["action"], "assert_visible")
        self.assertEqual(steps[3]["selector"], ".dashboard")
        self.assertEqual(steps[4]["action"], "screenshot")
        self.assertEqual(steps[4]["path"], "audit.png")

    def test_english_instruction_compilation(self) -> None:
        instruction = (
            "open http://localhost:3000/cart; "
            "click #checkout; "
            "fill #promo with 'DISCOUNT10'; "
            "verify .summary is visible; "
            "take screenshot cart.png"
        )
        scenario = self.compiler.compile(instruction, backend="template")
        ok, errors = schema.validate_scenario_dict(scenario)
        self.assertTrue(ok, f"Validation errors: {errors}")

        steps = scenario["checks"][0]["steps"]
        self.assertEqual(len(steps), 5)
        self.assertEqual(steps[0]["action"], "goto")
        self.assertEqual(steps[1]["action"], "click")
        self.assertEqual(steps[1]["selector"], "#checkout")
        self.assertEqual(steps[2]["action"], "fill")
        self.assertEqual(steps[2]["selector"], "#promo")
        self.assertEqual(steps[2]["value"], "DISCOUNT10")
        self.assertEqual(steps[3]["action"], "assert_visible")
        self.assertEqual(steps[3]["selector"], ".summary")
        self.assertEqual(steps[4]["action"], "screenshot")
        self.assertEqual(steps[4]["path"], "cart.png")

    def test_relative_url_expansion(self) -> None:
        instruction = "открой /profile"
        scenario = self.compiler.compile(instruction, backend="template")
        step = scenario["checks"][0]["steps"][0]
        self.assertEqual(step["goto"], "http://localhost:3000/profile")

    def test_wait_step_compilation(self) -> None:
        instruction = "подожди 5 секунд"
        scenario = self.compiler.compile(instruction, backend="template")
        step = scenario["checks"][0]["steps"][0]
        self.assertEqual(step["action"], "wait_for")
        self.assertEqual(step["timeout_ms"], 5000)

    def test_security_origin_restriction(self) -> None:
        instruction = "open https://unauthorized-evil.com/phishing"
        with self.assertRaises(ValueError) as ctx:
            self.compiler.compile(instruction, backend="template")
        self.assertIn("forbidden by security policy", str(ctx.exception))

    def test_security_forbidden_scheme(self) -> None:
        instruction = "open javascript:alert(1)"
        with self.assertRaises(ValueError) as ctx:
            self.compiler.compile(instruction, backend="template")
        self.assertIn("Forbidden URL scheme", str(ctx.exception))


class MockInferenceClient(LocalInferenceClient):
    """Mock inference client returning predefined LLM responses."""

    def __init__(self, response_text: Optional[str]) -> None:
        super().__init__()
        self.response_text = response_text

    def is_available(self) -> bool:
        return True

    def generate(self, prompt: str, system: Optional[str] = None) -> Optional[str]:
        return self.response_text


class TestMockLLMCompilation(unittest.TestCase):
    """Verify compiler handling of LLM JSON responses."""

    def test_successful_llm_json_compilation(self) -> None:
        llm_json = json.dumps([
            {"action": "goto", "goto": "http://localhost:3000/settings"},
            {"action": "click", "selector": "#save"},
            {"action": "screenshot", "path": "saved.png"},
        ])
        mock_client = MockInferenceClient(llm_json)
        compiler = NLScenarioCompiler(client=mock_client)
        scenario = compiler.compile("go to settings, save and screenshot", backend="local-http")
        steps = scenario["checks"][0]["steps"]
        self.assertEqual(len(steps), 3)
        self.assertEqual(steps[0]["goto"], "http://localhost:3000/settings")
        self.assertEqual(steps[1]["selector"], "#save")
        self.assertEqual(steps[2]["path"], "saved.png")

    def test_llm_malformed_json_falls_back_to_template(self) -> None:
        mock_client = MockInferenceClient("I cannot produce JSON.")
        compiler = NLScenarioCompiler(client=mock_client)
        scenario = compiler.compile("open http://localhost:3000/about", backend="auto")
        steps = scenario["checks"][0]["steps"]
        self.assertEqual(len(steps), 1)
        self.assertEqual(steps[0]["goto"], "http://localhost:3000/about")
