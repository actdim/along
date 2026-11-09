#!/usr/bin/env python3
"""tests/test_domain_exceptions.py - Tests for domain exceptions hierarchy and central error boundary."""

from __future__ import annotations

import ast
import io
import os
import shutil
import sys
import tempfile
import unittest
from unittest import mock

if not os.environ.get("ALONG_TEST_RUNNER"):
    raise SystemExit(
        "[Error] Tests must not be run directly or via standard test commands (unittest/pytest).\n"
        "To run tests with automatically resolved dependencies, use the official project entry point:\n"
        "    python .along/scripts/test.py"
    )

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPTS_DIR = os.path.join(REPO_ROOT, "scripts")
if SCRIPTS_DIR not in sys.path:
    sys.path.insert(0, SCRIPTS_DIR)

from alongkit import exceptions, proc
from alongkit.exceptions import AlongError, CommandError, ValidationError
import along_exec


class TestDomainExceptionsHierarchy(unittest.TestCase):
    """Pin the exception hierarchy, default exit codes and attributes."""

    def test_hierarchy(self):
        self.assertTrue(issubclass(AlongError, Exception))
        self.assertTrue(issubclass(CommandError, AlongError))
        self.assertTrue(issubclass(ValidationError, CommandError))

    def test_command_error_defaults(self):
        err = CommandError("test operational failure")
        self.assertEqual(err.message, "test operational failure")
        self.assertEqual(str(err), "test operational failure")
        self.assertEqual(err.exit_code, 1)
        self.assertIsNone(err.usage)

    def test_command_error_custom_code_and_usage(self):
        err = CommandError("custom failure", exit_code=42, usage="along custom [options]")
        self.assertEqual(err.message, "custom failure")
        self.assertEqual(err.exit_code, 42)
        self.assertEqual(err.usage, "along custom [options]")

    def test_validation_error_defaults(self):
        val = ValidationError("invalid argument")
        self.assertEqual(val.message, "invalid argument")
        self.assertEqual(str(val), "invalid argument")
        self.assertEqual(val.exit_code, 2)
        self.assertIsNone(val.usage)

    def test_validation_error_with_usage(self):
        val = ValidationError("bad entity name", usage="along issue create <type> <slug>")
        self.assertEqual(val.message, "bad entity name")
        self.assertEqual(val.exit_code, 2)
        self.assertEqual(val.usage, "along issue create <type> <slug>")


class TestCentralErrorBoundary(unittest.TestCase):
    """Test along_exec.cli_entry formatting and error propagation."""

    def test_cli_entry_formats_command_error(self):
        err_buf = io.StringIO()
        with mock.patch("along_exec.main", side_effect=CommandError("disk full", exit_code=1)):
            with mock.patch("sys.stderr", err_buf):
                with self.assertRaises(SystemExit) as ctx:
                    along_exec.cli_entry()
                self.assertEqual(ctx.exception.code, 1)
        self.assertEqual(err_buf.getvalue(), "[Error] disk full\n")

    def test_cli_entry_formats_validation_error_with_usage(self):
        err_buf = io.StringIO()
        with mock.patch("along_exec.main", side_effect=ValidationError("missing slug", usage="along start <slug>")):
            with mock.patch("sys.stderr", err_buf):
                with self.assertRaises(SystemExit) as ctx:
                    along_exec.cli_entry()
                self.assertEqual(ctx.exception.code, 2)
        self.assertEqual(err_buf.getvalue(), "[Error] missing slug\nUsage: along start <slug>\n")

    def test_cli_entry_reraises_under_along_debug(self):
        with mock.patch.dict(os.environ, {"ALONG_DEBUG": "1"}):
            with mock.patch("along_exec.main", side_effect=CommandError("debug test", exit_code=1)):
                with self.assertRaises(CommandError) as ctx:
                    along_exec.cli_entry()
                self.assertEqual(ctx.exception.message, "debug test")


class TestGoldenCliErrorOutput(unittest.TestCase):
    """Golden subprocess execution tests verifying byte-exact stderr formatting and exit codes."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="along-domain-exc-")

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_uninstalled_board_command_exit_code_and_stderr(self):
        res = proc.run_capture([sys.executable, os.path.join(SCRIPTS_DIR, "along_exec.py"), "start", "any-slug"], cwd=self.tmp)
        self.assertEqual(res.returncode, 2)
        self.assertIn("[Error] Along is not installed in", res.stderr)
        self.assertIn("Run 'along init' there", res.stderr)

    def test_invalid_name_flag_like_rejected(self):
        from alongkit.commands.common import require_entity_name
        with self.assertRaises(ValidationError) as ctx:
            require_entity_name("-bad-flag", "along test <name>")
        self.assertEqual(ctx.exception.exit_code, 2)
        self.assertIn("Invalid name '-bad-flag'", ctx.exception.message)
        self.assertEqual(ctx.exception.usage, "along test <name>")

    def test_check_unknown_args_raises_validation_error(self):
        from alongkit.commands.common import check_unknown_args
        with self.assertRaises(ValidationError) as ctx:
            check_unknown_args(["--unknown", "val"], "along test")
        self.assertEqual(ctx.exception.exit_code, 2)
        self.assertIn("along test: error: unrecognized arguments: --unknown val", ctx.exception.message)


class TestNoDirectSysExitInCommands(unittest.TestCase):
    """Ensure command modules do not invoke sys.exit() directly; domain exceptions must be used."""

    def test_commands_have_no_sys_exit_calls(self):
        commands_dir = os.path.join(SCRIPTS_DIR, "alongkit", "commands")
        self.assertTrue(os.path.isdir(commands_dir), f"Directory not found: {commands_dir}")

        violations = []
        py_files = sorted([f for f in os.listdir(commands_dir) if f.endswith(".py")])
        self.assertGreater(len(py_files), 5, "Expected command modules to exist")

        for fname in py_files:
            fpath = os.path.join(commands_dir, fname)
            with open(fpath, "r", encoding="utf-8") as handle:
                tree = ast.parse(handle.read(), filename=fname)

            for node in ast.walk(tree):
                if isinstance(node, ast.Call):
                    # Check for sys.exit(...)
                    if (isinstance(node.func, ast.Attribute)
                            and node.func.attr == "exit"
                            and isinstance(node.func.value, ast.Name)
                            and node.func.value.id == "sys"):
                        violations.append(f"{fname}:{node.lineno}: sys.exit() call")
                    # Check for bare exit(...)
                    elif isinstance(node.func, ast.Name) and node.func.id in ("exit", "quit"):
                        violations.append(f"{fname}:{node.lineno}: {node.func.id}() call")

        self.assertEqual(violations, [], "Command modules must not call sys.exit(); raise CommandError or ValidationError instead.")


if __name__ == "__main__":
    unittest.main()

