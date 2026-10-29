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
from alongkit import handoff, proc, session
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
            "--output-format",
            "json",
            "--no-session-persistence",
            "--model",
            "claude-3-7-sonnet",
            "--dangerously-skip-permissions",
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
            "--json",
            "--color",
            "never",
            "-C",
            self.repo,
            "-m",
            "o3-mini",
            "--sandbox",
            "workspace-write",
            "--max-turns",
            "10",
            "-",
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
            "--format",
            "json",
            "--dir",
            self.repo,
            "-m",
            "ollama/qwen2.5-coder:32b",
            "--auto",
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
        expected = ["worker-bin", "--verbose", "--mode=batch"]
        self.assertEqual(cmd, expected)

    def test_generic_command_line_template(self) -> None:
        runner = GenericCliRunner(
            repo_root=self.repo,
            command_template=["python", "-m", "worker", "--brief={prompt}", "--timeout=30"],
        )
        cmd = runner.build_command("Run audit")
        expected = ["python", "-m", "worker", "--brief=Run audit", "--timeout=30"]
        self.assertEqual(cmd, expected)

    def test_brief_is_sent_on_stdin(self) -> None:
        session.init_session(self.repo, "test-slug", title="Test")
        script = os.path.join(self.repo, "echo_stdin.py")
        py_code = "import sys\ndata = sys.stdin.read()\nsys.stdout.write(f'read:{len(data)}')\n"
        with open(script, "w", encoding="utf-8") as f:
            f.write(py_code)

        runner = GenericCliRunner(
            repo_root=self.repo,
            issue_slug="test-slug",
            binary_path=sys.executable,
            extra_args=[script],
        )
        brief = "Hello stdin test brief"
        record = runner.execute_run(brief=brief)
        self.assertEqual(record["outcome"], "done")
        self.assertIn(f"read:{len(brief)}", runner.last_result.stdout)

    def test_stdin_closed_when_unused(self) -> None:
        session.init_session(self.repo, "test-slug", title="Test")
        script = os.path.join(self.repo, "read_stdin.py")
        py_code = "import sys\ndata = sys.stdin.read()\nsys.stdout.write(repr(data))\n"
        with open(script, "w", encoding="utf-8") as f:
            f.write(py_code)

        runner = GenericCliRunner(
            repo_root=self.repo,
            issue_slug="test-slug",
            command_template=[sys.executable, script, "--prompt={prompt}"],
        )
        record = runner.execute_run(brief="Arg prompt")
        self.assertEqual(record["outcome"], "done")
        self.assertIn("''", runner.last_result.stdout)

    @unittest.skipUnless(os.name == "nt", "Windows-specific .cmd shim test")
    def test_20kb_brief_through_cmd_shim(self) -> None:
        session.init_session(self.repo, "test-slug", title="Test")
        receiver_py = os.path.join(self.repo, "receiver.py")
        with open(receiver_py, "w", encoding="utf-8") as f:
            f.write("import sys\ndata = sys.stdin.read()\nsys.exit(0 if len(data) == 20480 else 1)\n")

        fake_cmd = os.path.join(self.repo, "fake.cmd")
        with open(fake_cmd, "w", encoding="utf-8") as f:
            f.write(f'@echo off\r\n"{sys.executable}" "{receiver_py}" %*\r\n')

        runner = CodexRunner(
            repo_root=self.repo,
            issue_slug="test-slug",
            binary_path=fake_cmd,
        )
        brief = "X" * 20480
        cmd = runner.build_command(brief)
        argv_str = " ".join(cmd)
        self.assertLess(len(argv_str), 1024)

        record = runner.execute_run(brief=brief)
        self.assertEqual(record["exit_code"], 0)
        self.assertEqual(record["outcome"], "done")

    @unittest.skipUnless(os.name != "nt", "POSIX-specific .sh shim test")
    def test_20kb_brief_through_sh_shim(self) -> None:
        session.init_session(self.repo, "test-slug", title="Test")
        receiver_py = os.path.join(self.repo, "receiver.py")
        with open(receiver_py, "w", encoding="utf-8") as f:
            f.write("import sys\ndata = sys.stdin.read()\nsys.exit(0 if len(data) == 20480 else 1)\n")

        fake_sh = os.path.join(self.repo, "fake.sh")
        with open(fake_sh, "w", encoding="utf-8") as f:
            f.write(f'#!/bin/sh\nexec "{sys.executable}" "{receiver_py}" "$@"\n')
        os.chmod(fake_sh, 0o755)

        runner = CodexRunner(
            repo_root=self.repo,
            issue_slug="test-slug",
            binary_path=fake_sh,
        )
        brief = "X" * 20480
        cmd = runner.build_command(brief)
        argv_str = " ".join(cmd)
        self.assertLess(len(argv_str), 1024)

        record = runner.execute_run(brief=brief)
        self.assertEqual(record["exit_code"], 0)
        self.assertEqual(record["outcome"], "done")

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

        with self.assertRaises(ValueError):
            get_runner("antigravity")

        with self.assertRaises(ValueError):
            get_runner("agy")


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
        sample_path = os.path.join(runner.fixture_dir(), "sample-ok.json")
        with open(sample_path, "r", encoding="utf-8") as f:
            stdout_payload = f.read()
        parsed = runner.parse_output(stdout_payload, "", exit_code=0)
        self.assertEqual(parsed["outcome"], "done")
        self.assertEqual(parsed["usage"]["input_tokens"], 1200)
        self.assertEqual(parsed["usage"]["output_tokens"], 5)
        self.assertEqual(parsed["usage"]["cost_usd"], 0.0035)
        self.assertEqual(parsed["text"], "OK")

    def test_claude_is_error_parsing(self) -> None:
        runner = ClaudeCodeRunner(repo_root=self.repo)
        stdout_payload = json.dumps({
            "is_error": True,
            "result": "Failed to authenticate",
            "total_cost_usd": 0,
        })
        parsed = runner.parse_output(stdout_payload, "", exit_code=0)
        self.assertEqual(parsed["outcome"], "fail")
        self.assertEqual(parsed["text"], "Failed to authenticate")

    def test_codex_jsonl_events_parsing(self) -> None:
        runner = CodexRunner(repo_root=self.repo)
        sample_path = os.path.join(runner.fixture_dir(), "sample-ok.jsonl")
        with open(sample_path, "r", encoding="utf-8") as f:
            stdout_payload = f.read()
        parsed = runner.parse_output(stdout_payload, "", exit_code=0)
        self.assertEqual(parsed["outcome"], "done")
        self.assertEqual(parsed["usage"]["input_tokens"], 17920)
        self.assertEqual(parsed["usage"]["output_tokens"], 5)
        self.assertIn("OK", parsed["text"])

    def test_codex_file_change_parsing(self) -> None:
        runner = CodexRunner(repo_root=self.repo)
        sample_path = os.path.join(runner.fixture_dir(), "sample-write.jsonl")
        with open(sample_path, "r", encoding="utf-8") as f:
            stdout_payload = f.read()
        parsed = runner.parse_output(stdout_payload, "", exit_code=0)
        self.assertEqual(parsed["outcome"], "done")
        self.assertIn("hello.txt", parsed["changed_files"])
        self.assertIn("Created hello.txt", parsed["text"])

    def test_opencode_json_output_parsing(self) -> None:
        runner = OpenCodeRunner(repo_root=self.repo)
        sample_path = os.path.join(runner.fixture_dir(), "sample-ok.jsonl")
        with open(sample_path, "r", encoding="utf-8") as f:
            stdout_payload = f.read()
        parsed = runner.parse_output(stdout_payload, "", exit_code=0)
        self.assertEqual(parsed["outcome"], "done")
        self.assertIn("OK", parsed["text"])
        self.assertIsNotNone(parsed["usage"])
        self.assertEqual(parsed["usage"]["input_tokens"], 9507)

    def test_opencode_tool_use_changed_files_parsing(self) -> None:
        runner = OpenCodeRunner(repo_root=self.repo)
        sample_path = os.path.join(runner.fixture_dir(), "sample-write.jsonl")
        with open(sample_path, "r", encoding="utf-8") as f:
            stdout_payload = f.read()
        parsed = runner.parse_output(stdout_payload, "", exit_code=0)
        self.assertEqual(parsed["outcome"], "done")
        self.assertIn("hello.txt", parsed["changed_files"])

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

    def test_timeout_kills_grandchild(self) -> None:
        import time
        from alongkit.daemon import is_pid_alive
        pid_file = os.path.join(self.repo, "grandchild.pid")
        py_grandchild = (
            f"import os, time, sys; "
            f"open({repr(pid_file)}, 'w').write(str(os.getpid())); "
            f"sys.stdout.flush(); "
            f"time.sleep(30)"
        )
        py_child = (
            f"import subprocess, sys, time; "
            f"p = subprocess.Popen([{repr(sys.executable)}, '-c', {repr(py_grandchild)}]); "
            f"p.wait()"
        )
        runner = GenericCliRunner(
            repo_root=self.repo,
            issue_slug=self.slug,
            binary_path=sys.executable,
            command_template=[sys.executable, "-c", py_child],
        )
        start = time.monotonic()
        record = runner.execute_run(brief="timeout task", timeout=2)
        elapsed = time.monotonic() - start
        self.assertLess(elapsed, 15.0)
        self.assertEqual(record["outcome"], "timeout")
        self.assertEqual(record["exit_code"], 124)

        self.assertTrue(os.path.isfile(pid_file))
        with open(pid_file, "r", encoding="utf-8") as f:
            grandchild_pid = int(f.read().strip())

        self.assertFalse(is_pid_alive(grandchild_pid))

    def test_missing_binary_fails_gracefully_without_exception(self) -> None:
        runner = GenericCliRunner(
            repo_root=self.repo,
            issue_slug=self.slug,
            binary_path="/nonexistent/binary/path/which/does/not/exist",
        )
        record = runner.execute_run(brief="task")
        self.assertEqual(record["outcome"], "fail")
        self.assertEqual(record["exit_code"], 127)


class TestPorcelainParsing(unittest.TestCase):
    """Verify porcelain status parsing without path corruption."""

    def setUp(self) -> None:
        self.repo = hermetic.make_repo_fixture(prefix="along-test-porcelain-")
        self.slug = "porcelain-task"
        session.init_session(self.repo, self.slug, title="Porcelain Task")

    def tearDown(self) -> None:
        shutil.rmtree(self.repo, ignore_errors=True)

    def test_porcelain_parsing_with_leading_space(self) -> None:
        runner = GenericCliRunner(repo_root=self.repo)
        fake_result = proc.Result(
            cmd=["git", "status"],
            returncode=0,
            stdout=" M foo.py\0?? bar.txt\0R  new.py\0old.py\0",
            stderr="",
        )
        orig_git = proc.git
        try:
            proc.git = lambda *args, **kwargs: fake_result
            snapshot = runner._snapshot_git_status()
            self.assertEqual(set(snapshot.keys()), {"foo.py", "bar.txt", "new.py"})
            self.assertEqual(snapshot["foo.py"], " M")
            self.assertEqual(snapshot["bar.txt"], "??")
            self.assertEqual(snapshot["new.py"], "R ")
        finally:
            proc.git = orig_git

    def test_hermetic_git_status_snapshot(self) -> None:
        runner = GenericCliRunner(repo_root=self.repo)
        proc.git(["init"], cwd=self.repo)
        proc.git(["config", "user.name", "Test Agent"], cwd=self.repo)
        proc.git(["config", "user.email", "agent@actdim.org"], cwd=self.repo)
        foo_path = os.path.join(self.repo, "foo.py")
        with open(foo_path, "w", encoding="utf-8") as f:
            f.write("# initial\n")
        proc.git(["add", "foo.py"], cwd=self.repo)
        proc.git(["commit", "-m", "init"], cwd=self.repo)

        with open(foo_path, "a", encoding="utf-8") as f:
            f.write("# modified\n")

        snapshot = runner._snapshot_git_status()
        self.assertIn("foo.py", snapshot)
        self.assertNotIn("oo.py", snapshot)


class TestAllowlistedEnvironment(unittest.TestCase):
    """Verify that runtimes receive allowlisted environment only."""

    def setUp(self) -> None:
        self.repo = hermetic.make_repo_fixture(prefix="along-test-env-")
        self.slug = "env-task"
        session.init_session(self.repo, self.slug, title="Env Task")

    def tearDown(self) -> None:
        shutil.rmtree(self.repo, ignore_errors=True)

    def test_runtime_env_is_allowlisted(self) -> None:
        orig = dict(os.environ)
        try:
            os.environ["ALONG_TELEGRAM_BOT_TOKEN"] = "secret-bot-token"
            os.environ["ANTHROPIC_API_KEY"] = "secret-anthropic-key"
            os.environ["OPENAI_API_KEY"] = "secret-openai-key"

            codex = CodexRunner(repo_root=self.repo, issue_slug=self.slug)
            c_env = codex.build_env()
            self.assertNotIn("ALONG_TELEGRAM_BOT_TOKEN", c_env)
            self.assertNotIn("ANTHROPIC_API_KEY", c_env)
            self.assertIn("OPENAI_API_KEY", c_env)
            self.assertIn("PATH", c_env)

            claude = ClaudeCodeRunner(repo_root=self.repo, issue_slug=self.slug)
            cl_env = claude.build_env()
            self.assertNotIn("ALONG_TELEGRAM_BOT_TOKEN", cl_env)
            self.assertNotIn("OPENAI_API_KEY", cl_env)
            self.assertIn("ANTHROPIC_API_KEY", cl_env)
            self.assertIn("PATH", cl_env)

            generic = GenericCliRunner(repo_root=self.repo, issue_slug=self.slug)
            g_env = generic.build_env()
            self.assertNotIn("ALONG_TELEGRAM_BOT_TOKEN", g_env)
            self.assertNotIn("ANTHROPIC_API_KEY", g_env)
            self.assertNotIn("OPENAI_API_KEY", g_env)
            self.assertIn("PATH", g_env)
        finally:
            os.environ.clear()
            os.environ.update(orig)


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
        json_output = json.dumps({
            "type": "result",
            "subtype": "success",
            "is_error": False,
            "result": "Created new test records.",
            "total_cost_usd": 0.015,
            "usage": {"input_tokens": 400, "output_tokens": 150},
        })
        py_code = f"import sys; print({repr(json_output)}); sys.exit(0)"
        runner.build_command = lambda prompt=None: [sys.executable, "-c", py_code]

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
        self.assertIsNotNone(runner.last_result)
        dry_payload = json.loads(runner.last_result.stdout)
        self.assertIn("stdin_bytes", dry_payload)
        self.assertEqual(dry_payload["stdin_bytes"], len("Dry run test".encode("utf-8")))


if __name__ == "__main__":
    unittest.main()
