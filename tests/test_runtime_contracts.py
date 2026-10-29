#!/usr/bin/env python3
"""tests/test_runtime_contracts.py - Verification that adapter flags match recorded CLI help fixtures."""

from __future__ import annotations

import os
import shutil
import unittest

if not os.environ.get("ALONG_TEST_RUNNER"):
    raise SystemExit(
        "[Error] Tests must not be run directly or via standard test commands (unittest/pytest).\n"
        "To run tests with automatically resolved dependencies, use the official project entry point:\n"
        "    python .along/scripts/test.py"
    )

import hermetic
from alongkit import orchestrator
from alongkit.runner import ClaudeCodeRunner, CodexRunner, OpenCodeRunner


class TestRuntimeContracts(unittest.TestCase):
    """Verify that runner commands use only flags recorded in real CLI help fixtures."""

    def setUp(self) -> None:
        self.repo = hermetic.make_repo_fixture(prefix="along-test-contract-")

    def tearDown(self) -> None:
        shutil.rmtree(self.repo, ignore_errors=True)

    def test_claude_contracts_against_help_fixture(self) -> None:
        self._verify_runner_contract(ClaudeCodeRunner, default_model="claude-3-7-sonnet")

    def test_codex_contracts_against_help_fixture(self) -> None:
        self._verify_runner_contract(CodexRunner, default_model="o3-mini")

    def test_opencode_contracts_against_help_fixture(self) -> None:
        self._verify_runner_contract(OpenCodeRunner, default_model="ollama/qwen2.5-coder:32b")

    def _verify_runner_contract(self, runner_cls: type, default_model: str) -> None:
        self.assertTrue(hasattr(runner_cls, "cli_version"), f"{runner_cls.__name__} missing cli_version")
        self.assertTrue(bool(runner_cls.cli_version), f"{runner_cls.__name__} has empty cli_version")

        fdir = runner_cls.fixture_dir()
        self.assertTrue(os.path.isdir(fdir), f"Fixture directory not found: {fdir}")

        vpath = os.path.join(fdir, "version.txt")
        self.assertTrue(os.path.isfile(vpath), f"version.txt not found: {vpath}")
        with open(vpath, "r", encoding="utf-8") as f:
            vtext = f.read()
        self.assertIn(runner_cls.cli_version, vtext)

        hpath = os.path.join(fdir, "help.txt")
        self.assertTrue(os.path.isfile(hpath), f"help.txt not found: {hpath}")
        with open(hpath, "r", encoding="utf-8") as f:
            htext = f.read()

        for role in orchestrator.SUPPORTED_ROLES:
            runner = runner_cls(repo_root=self.repo, model=default_model, role=role)
            cmd = runner.build_command("Brief for testing")
            for token in cmd:
                if token.startswith("-") and token != "-":
                    flag = token.split("=")[0]
                    self.assertIn(
                        flag,
                        htext,
                        f"{runner_cls.__name__} role={role} generated flag '{flag}' not in help.txt fixture",
                    )


if __name__ == "__main__":
    unittest.main()
