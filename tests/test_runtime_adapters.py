#!/usr/bin/env python3
"""tests/test_runtime_adapters.py - Unit tests for multi-runtime agent CLI adapters."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
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
from alongkit import handoff, session
from alongkit.runner import (
    BaseRunner,
    ClaudeCodeRunner,
    CodexRunner,
    GenericCliRunner,
    OpenCodeRunner,
    RunResult,
    get_runner,
)


class TestCommandLineAndFlagMapping(unittest.TestCase):
    """Verify command line construction and argument mapping across runtime adapters."""

    def setUp(self) -> None:
        self.repo = hermetic.make_repo_fixture(prefix="along-test-cmd-")

    def tearDown(self) -> None:
        shutil.rmtree(self.repo, ignore_errors=True)

    def test_claude_command_line_and_flags(self) -> None:
        runner = ClaudeCodeRunner(
            repo_root=self.repo,
            binary_path="custom-claude",
            model="claude-3-7-sonnet",
            extra_args=["--max-thinking-tokens", "2048"],
        )
        cmd = runner.build_command("Implement authentication module")
        expected = [
            "custom-claude",
            "-p",
            "Implement authentication module",
            "--dangerously-skip-permissions",
            "--output-format",
            "json",
            "--model",
            "claude-3-7-sonnet",
            "--max-thinking-tokens",
            "2048",
        ]
        self.assertEqual(cmd, expected)

    def test_codex_command_line_and_flags(self) -> None:
        runner = CodexRunner(
            repo_root=self.repo,
            binary_path="custom-codex",
            model="o3-mini",
            extra_args=["--max-turns", "10"],
        )
        cmd = runner.build_command("Refactor cache layout")
        expected = [
            "custom-codex",
            "exec",
            "Refactor cache layout",
            "--non-interactive",
            "--json",
            "--model",
            "o3-mini",
            "--max-turns",
            "10",
        ]
        self.assertEqual(cmd, expected)

    def test_opencode_command_line_and_flags(self) -> None:
        runner = OpenCodeRunner(
            repo_root=self.repo,
            binary_path="custom-opencode",
            model="ollama/qwen2.5-coder:32b",
            extra_args=["--port", "8080"],
        )
        cmd = runner.build_command("Review security policy")
        expected = [
            "custom-opencode",
            "run",
            "Review security policy",
            "--yes",
            "--format",
            "json",
            "--model",
            "ollama/qwen2.5-coder:32b",
            "--port",
            "8080",
        ]
        self.assertEqual(cmd, expected)

    def test_generic_command_line_default(self) -> None:
        runner = GenericCliRunner(
            repo_root=self.repo,
            binary_path="worker-bin",
            extra_args=["--verbose", "--mode=batch"],
        )
        cmd = runner.build_command("Run tests")
        expected = ["worker-bin", "--verbose", "--mode=batch", "Run tests"]
        self.assertEqual(cmd, expected)

    def test_generic_command_line_template(self) -> None:
        runner = GenericCliRunner(
            repo_root=self.repo,
            command_template=["python", "-m", "worker", "--brief={prompt}", "--timeout=30"],
        )
        cmd = runner.build_command("Run audit")
        expected = ["python", "-m", "worker", "--brief=Run audit", "--timeout=30"]
        self.assertEqual(cmd, expected)

    def test_runner_factory_get_runner(self) -> None:
        claude = get_runner("claude", repo_root=self.repo)
        self.assertIsInstance(claude, ClaudeCodeRunner)

        claude_alias = get_runner("claude-code", repo_root=self.repo)
        self.assertIsInstance(claude_alias, ClaudeCodeRunner)

        codex = get_runner("codex", repo_root=self.repo)
        self.assertIsInstance(codex, CodexRunner)

        opencode = get_runner("opencode", repo_root=self.repo)
        self.assertIsInstance(opencode, OpenCodeRunner)

        generic = get_runner("generic", repo_root=self.repo)
        self.assertIsInstance(generic, GenericCliRunner)

        with self.assertRaises(ValueError):
            get_runner("unsupported-runtime")


class TestOpenCodeEnvironmentAndLocalEndpoint(unittest.TestCase):
    """Verify local Ollama/vLLM OPENAI_BASE_URL endpoint configuration and containment."""

    def setUp(self) -> None:
        self.repo = hermetic.make_repo_fixture(prefix="along-test-opencode-")
        self.slug = "air-gapped-task"
        session.init_session(self.repo, self.slug, title="Air Gapped Task")

    def tearDown(self) -> None:
        shutil.rmtree(self.repo, ignore_errors=True)

    def test_opencode_base_url_constructor_parameter(self) -> None:
        runner = OpenCodeRunner(
            repo_root=self.repo,
            issue_slug=self.slug,
            base_url="http://localhost:11434/v1",
        )
        env = runner.build_env()
        self.assertEqual(env.get("OPENAI_BASE_URL"), "http://localhost:11434/v1")
        self.assertEqual(env.get("ALONG_ISSUE_SLUG"), self.slug)
        self.assertEqual(env.get("ALONG_REPO_ROOT"), self.repo)

    def test_opencode_base_url_from_environment(self) -> None:
        original = os.environ.get("OPENAI_BASE_URL")
        try:
            os.environ["OPENAI_BASE_URL"] = "http://10.0.0.5:8000/v1"
            runner = OpenCodeRunner(repo_root=self.repo, issue_slug=self.slug)
            env = runner.build_env()
            self.assertEqual(env.get("OPENAI_BASE_URL"), "http://10.0.0.5:8000/v1")
        finally:
            if original is not None:
                os.environ["OPENAI_BASE_URL"] = original
            else:
                os.environ.pop("OPENAI_BASE_URL", None)


class TestOutputParsing(unittest.TestCase):
    """Verify structured output parsing across Claude Code, Codex, OpenCode, and Generic CLI."""

    def setUp(self) -> None:
        self.repo = hermetic.make_repo_fixture(prefix="along-test-parse-")

    def tearDown(self) -> None:
        shutil.rmtree(self.repo, ignore_errors=True)

    def test_claude_json_output_parsing(self) -> None:
        runner = ClaudeCodeRunner(repo_root=self.repo)
        stdout_payload = json.dumps({
            "result": "Refactored service layers successfully.",
            "status": "success",
            "cost": 0.035,
            "tokens": {"input": 1200, "output": 450},
            "tool_calls": [
                {"name": "Write", "parameters": {"file_path": "scripts/auth.py"}},
                {"name": "Edit", "parameters": {"path": "tests/test_auth.py"}},
            ],
            "handoff_note": "Added JWT support.",
        })
        parsed = runner.parse_output(stdout_payload, "", exit_code=0)
        self.assertEqual(parsed["outcome"], "done")
        self.assertEqual(parsed["usage"]["input_tokens"], 1200)
        self.assertEqual(parsed["usage"]["output_tokens"], 450)
        self.assertEqual(parsed["usage"]["cost"], 0.035)
        self.assertEqual(parsed["changed_files"], ["scripts/auth.py", "tests/test_auth.py"])
        self.assertEqual(parsed["handoff_note"], "Added JWT support.")

    def test_claude_needs_input_parsing(self) -> None:
        runner = ClaudeCodeRunner(repo_root=self.repo)
        stdout_payload = json.dumps({
            "result": "Which database adapter do you prefer: sqlite or postgres?",
            "status": "needs-input",
        })
        parsed = runner.parse_output(stdout_payload, "", exit_code=0)
        self.assertEqual(parsed["outcome"], "needs-input")

    def test_codex_jsonl_events_parsing(self) -> None:
        runner = CodexRunner(repo_root=self.repo)
        lines = [
            json.dumps({"type": "turn.start"}),
            json.dumps({
                "type": "item.created",
                "item": {
                    "type": "tool_call",
                    "call": {"file": "src/cache.py"},
                },
            }),
            json.dumps({
                "type": "item.created",
                "item": {
                    "type": "message",
                    "content": "Applied eviction fix in cache.",
                },
            }),
            json.dumps({
                "type": "turn.end",
                "usage": {"input_tokens": 850, "output_tokens": 120},
            }),
        ]
        stdout_payload = "\n".join(lines) + "\n"
        parsed = runner.parse_output(stdout_payload, "", exit_code=0)
        self.assertEqual(parsed["outcome"], "done")
        self.assertEqual(parsed["usage"]["input_tokens"], 850)
        self.assertEqual(parsed["usage"]["output_tokens"], 120)
        self.assertEqual(parsed["changed_files"], ["src/cache.py"])
        self.assertIn("Applied eviction fix in cache.", parsed["text"])

    def test_opencode_json_output_parsing(self) -> None:
        runner = OpenCodeRunner(repo_root=self.repo)
        stdout_payload = json.dumps({
            "output": "Completed tasks via local model.",
            "usage": {"input_tokens": 600, "output_tokens": 90},
            "tool_calls": [
                {"name": "file_edit", "parameters": {"file": "config.yaml"}},
            ],
        })
        parsed = runner.parse_output(stdout_payload, "", exit_code=0)
        self.assertEqual(parsed["outcome"], "done")
        self.assertEqual(parsed["usage"]["input_tokens"], 600)
        self.assertEqual(parsed["usage"]["output_tokens"], 90)
        self.assertEqual(parsed["changed_files"], ["config.yaml"])

    def test_generic_line_buffered_capture(self) -> None:
        runner = GenericCliRunner(repo_root=self.repo)
        stdout_text = "line 1: start\nline 2: executing step\nline 3: done\n"
        stderr_text = "warning: deprecated option\n"
        parsed = runner.parse_output(stdout_text, stderr_text, exit_code=0)
        self.assertEqual(parsed["outcome"], "done")
        self.assertEqual(parsed["stdout_lines"], ["line 1: start", "line 2: executing step", "line 3: done"])
        self.assertEqual(parsed["stderr_lines"], ["warning: deprecated option"])


class TestProcessExecutionAndExitCodes(unittest.TestCase):
    """Verify live process execution, exit codes, and timeout handling."""

    def setUp(self) -> None:
        self.repo = hermetic.make_repo_fixture(prefix="along-test-exec-")
        self.slug = "exec-task"
        session.init_session(self.repo, self.slug, title="Exec Task")

    def tearDown(self) -> None:
        shutil.rmtree(self.repo, ignore_errors=True)

    def test_process_exit_code_zero(self) -> None:
        runner = GenericCliRunner(
            repo_root=self.repo,
            issue_slug=self.slug,
            binary_path=sys.executable,
            command_template=[sys.executable, "-c", "import sys; print('worker ok'); sys.exit(0)"],
        )
        record = runner.execute_run(brief="execute task")
        self.assertEqual(record["outcome"], "done")
        self.assertEqual(record["exit_code"], 0)
        self.assertIsNotNone(runner.last_result)
        self.assertIn("worker ok", runner.last_result.stdout)

    def test_process_exit_code_nonzero(self) -> None:
        runner = GenericCliRunner(
            repo_root=self.repo,
            issue_slug=self.slug,
            binary_path=sys.executable,
            command_template=[sys.executable, "-c", "import sys; sys.stderr.write('fatal error\\n'); sys.exit(42)"],
        )
        record = runner.execute_run(brief="execute failing task")
        self.assertEqual(record["outcome"], "fail")
        self.assertEqual(record["exit_code"], 42)
        self.assertIsNotNone(runner.last_result)
        self.assertIn("fatal error", runner.last_result.stderr)

    def test_timeout_handling_terminates_child_process(self) -> None:
        runner = GenericCliRunner(
            repo_root=self.repo,
            issue_slug=self.slug,
            binary_path=sys.executable,
            command_template=[sys.executable, "-c", "import time; time.sleep(10)"],
        )
        record = runner.execute_run(brief="sleep task", timeout=1)
        self.assertEqual(record["outcome"], "timeout")
        self.assertEqual(record["exit_code"], 124)

    def test_missing_binary_fails_gracefully_without_exception(self) -> None:
        runner = GenericCliRunner(
            repo_root=self.repo,
            issue_slug=self.slug,
            binary_path="/nonexistent/binary/path/which/does/not/exist",
        )
        record = runner.execute_run(brief="task")
        self.assertEqual(record["outcome"], "fail")
        self.assertEqual(record["exit_code"], 127)


class TestRunRecordSynthesis(unittest.TestCase):
    """Verify run record persistence in .along/.session/<slug>/runs/<run-id>.json."""

    def setUp(self) -> None:
        self.repo = hermetic.make_repo_fixture(prefix="along-test-synthesis-")
        self.slug = "record-task"
        session.init_session(self.repo, self.slug, title="Record Synthesis Task")

    def tearDown(self) -> None:
        shutil.rmtree(self.repo, ignore_errors=True)

    def test_run_record_synthesis_on_disk(self) -> None:
        run_id = "test-run-record-456"
        runner = ClaudeCodeRunner(
            repo_root=self.repo,
            issue_slug=self.slug,
            run_id=run_id,
            binary_path=sys.executable,
        )
        # Patch build_command to run a lightweight python echo emitting valid Claude Code JSON
        json_output = json.dumps({
            "result": "Created new test records.",
            "status": "success",
            "usage": {"input_tokens": 400, "output_tokens": 150},
            "tool_calls": [{"name": "Write", "parameters": {"file": "new_file.txt"}}],
        })
        py_code = f"import sys; print({repr(json_output)}); sys.exit(0)"
        runner.build_command = lambda prompt: [sys.executable, "-c", py_code]

        record = runner.execute_run(brief="Execute synthesis test", role="implementer", model="claude-3-7-sonnet")
        self.assertEqual(record["run_id"], run_id)
        self.assertEqual(record["outcome"], "done")
        self.assertEqual(record["exit_code"], 0)
        self.assertEqual(record["role"], "implementer")
        self.assertEqual(record["runtime"], "claude")
        self.assertEqual(record["model"], "claude-3-7-sonnet")

        # Verify disk persistence
        runs_dir = handoff.get_runs_dir(self.repo, self.slug)
        target_file = os.path.join(runs_dir, f"{run_id}.json")
        self.assertTrue(os.path.isfile(target_file))

        with open(target_file, "r", encoding="utf-8") as f:
            disk_data = json.load(f)

        self.assertEqual(disk_data["run_id"], run_id)
        self.assertEqual(disk_data["outcome"], "done")
        self.assertEqual(disk_data["exit_code"], 0)
        self.assertEqual(disk_data["runtime"], "claude")
        self.assertEqual(disk_data["changed_files"], ["new_file.txt"])
        self.assertEqual(disk_data["usage"]["input_tokens"], 400)
        self.assertEqual(disk_data["usage"]["output_tokens"], 150)
        self.assertIsNotNone(disk_data["start"])
        self.assertIsNotNone(disk_data["end"])

    def test_dry_run_record_synthesis(self) -> None:
        run_id = "dry-run-rec-789"
        runner = OpenCodeRunner(
            repo_root=self.repo,
            issue_slug=self.slug,
            run_id=run_id,
            dry_run=True,
            model="ollama/qwen2.5-coder:32b",
        )
        record = runner.execute_run(brief="Dry run test", role="architect")
        self.assertEqual(record["outcome"], "done")
        self.assertEqual(record["exit_code"], 0)

        runs_dir = handoff.get_runs_dir(self.repo, self.slug)
        target_file = os.path.join(runs_dir, f"{run_id}.json")
        self.assertTrue(os.path.isfile(target_file))

        with open(target_file, "r", encoding="utf-8") as f:
            disk_data = json.load(f)
        self.assertEqual(disk_data["run_id"], run_id)
        self.assertEqual(disk_data["role"], "architect")
        self.assertEqual(disk_data["runtime"], "opencode")


if __name__ == "__main__":
    unittest.main()
