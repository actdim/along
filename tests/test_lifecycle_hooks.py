#!/usr/bin/env python3
"""
tests/test_lifecycle_hooks.py - Hermetic tests for repository lifecycle hook execution and synthesis.

Validates [bug--generated-lifecycle-hooks-use-shell-string-concat]:
  - REQ-1: Pass arguments as list; use shell=False everywhere; shlex.split at generation time.
  - REQ-2: Explicit interpreter selection per hook extension (.py, .sh, .ps1, .bat).
  - REQ-3: Extract hook templates to alongkit.lifecycle with syntax and compilation tests.
  - REQ-4: Generated hook uses shared repo-root resolver instead of fragile triple dirname.
  - REQ-5: Arguments with spaces and shell metacharacters arrive verbatim in the child process.
"""

from __future__ import annotations

import os
import sys

if not os.environ.get("ALONG_TEST_RUNNER"):
    raise SystemExit(
        "[Error] Tests must not be run directly or via standard test commands (unittest/pytest).\n"
        "To run tests with automatically resolved dependencies, use the official project entry point:\n"
        "    python .along/scripts/test.py"
    )

import ast
import json
import subprocess
import unittest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPTS_DIR = os.path.join(REPO_ROOT, "scripts")
if SCRIPTS_DIR not in sys.path:
    sys.path.insert(0, SCRIPTS_DIR)

from alongkit import lifecycle, proc
import hermetic


class TestLifecycleHooks(unittest.TestCase):
    def test_01_no_shell_true_in_along_exec(self):
        """REQ-1 & AC: No shell=True remains in scripts/along_exec.py."""
        along_exec_path = os.path.join(SCRIPTS_DIR, "along_exec.py")
        with open(along_exec_path, "r", encoding="utf-8") as f:
            code = f.read()

        # Parse AST to confirm no keyword argument shell=True exists in any Call node
        tree = ast.parse(code, filename=along_exec_path)
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                for kw in node.keywords:
                    if kw.arg == "shell":
                        val = getattr(kw.value, "value", None)
                        if val is True:
                            self.fail(f"Found shell=True call at line {node.lineno} in along_exec.py")

    def test_02_interpreter_cmd_selection(self):
        """REQ-2: Interpreter is selected explicitly by extension with shell=False."""
        # Python
        cmd_py = lifecycle.build_interpreter_cmd("run.py", ["--quiet", "arg with space"])
        self.assertEqual(cmd_py[0], sys.executable)
        self.assertEqual(cmd_py[1], "run.py")
        self.assertEqual(cmd_py[2:], ["--quiet", "arg with space"])

        # Shell
        cmd_sh = lifecycle.build_interpreter_cmd("run.sh", ["foo"])
        self.assertTrue(cmd_sh[0].lower().endswith(("bash", "bash.exe")))
        self.assertEqual(cmd_sh[1:], ["run.sh", "foo"])

        # PowerShell
        cmd_ps1 = lifecycle.build_interpreter_cmd("run.ps1", ["bar"])
        self.assertTrue(any(p in cmd_ps1[0].lower() for p in ("powershell", "pwsh")))
        self.assertIn("-File", cmd_ps1)
        self.assertEqual(cmd_ps1[-2:], ["run.ps1", "bar"])

        # Batch
        cmd_bat = lifecycle.build_interpreter_cmd("run.bat", ["baz"])
        self.assertTrue(cmd_bat[0].lower().endswith(("cmd", "cmd.exe")))
        self.assertEqual(cmd_bat[1:], ["/c", "run.bat", "baz"])

        # Binary fallback
        cmd_bin = lifecycle.build_interpreter_cmd("run.bin", ["qux"])
        self.assertEqual(cmd_bin, ["run.bin", "qux"])

    def test_03_render_lifecycle_script_syntax_and_compilation(self):
        """REQ-1 & REQ-3: Hook template renders valid Python and pre-splits command into argv list."""
        rendered = lifecycle.render_lifecycle_script(
            action="test",
            base_cmd="npm test -- --silent",
            status_tag="verified"
        )

        # Must parse as valid Python AST
        tree = ast.parse(rendered, filename="test.py")
        self.assertIsNotNone(tree)

        # Must compile without syntax errors
        compiled = compile(rendered, "test.py", "exec")
        self.assertIsNotNone(compiled)

        # Must contain base_cmd as a concrete list literal, not runtime shlex.split
        self.assertIn("base_cmd = ['npm', 'test', '--', '--silent']", rendered)
        self.assertNotIn("shlex.split", rendered)

        # Unconfigured template must also compile
        rendered_unconf = lifecycle.render_lifecycle_script(
            action="build",
            base_cmd=None,
            status_tag="unconfigured"
        )
        self.assertIn("# Status: unconfigured", rendered_unconf)
        compiled_unconf = compile(rendered_unconf, "build.py", "exec")
        self.assertIsNotNone(compiled_unconf)

    def test_04_generated_hook_resolves_repo_root_via_markers(self):
        """REQ-4: Hook resolves root via ROOT_MARKERS (.along) without fragile triple dirname."""
        with hermetic.repo_fixture() as fixture_root:
            scripts_dir = os.path.join(fixture_root, ".along", "scripts")
            os.makedirs(scripts_dir, exist_ok=True)
            hook_file = os.path.join(scripts_dir, "test.py")

            # Create a minimal target script that prints repo_root
            worker_file = os.path.join(fixture_root, "worker.py")
            with open(worker_file, "w", encoding="utf-8") as f:
                f.write(
                    "import os, sys\n"
                    "print(f'CWD:{os.getcwd()}')\n"
                )

            rendered = lifecycle.render_lifecycle_script(
                action="test",
                base_cmd=[sys.executable, worker_file],
                status_tag="verified"
            )
            with open(hook_file, "w", encoding="utf-8") as f:
                f.write(rendered)

            # Invoke hook from a deeply nested child folder
            nested_dir = os.path.join(fixture_root, "deep", "nested", "subfolder")
            os.makedirs(nested_dir, exist_ok=True)

            res = proc.run_capture([sys.executable, hook_file], cwd=nested_dir)
            self.assertEqual(res.returncode, 0, f"Hook failed: {res.stderr}")
            # CWD of the executed process must be fixture_root
            self.assertIn(f"CWD:{os.path.abspath(fixture_root)}", res.stdout)

    def test_05_arguments_with_spaces_and_metacharacters_preserved(self):
        """REQ-1 & REQ-5: Arguments containing spaces and shell metacharacters are passed verbatim."""
        with hermetic.repo_fixture() as fixture_root:
            scripts_dir = os.path.join(fixture_root, ".along", "scripts")
            os.makedirs(scripts_dir, exist_ok=True)
            hook_file = os.path.join(scripts_dir, "test.py")
            out_file = os.path.join(fixture_root, "args_out.json")

            worker_file = os.path.join(fixture_root, "record_args.py")
            with open(worker_file, "w", encoding="utf-8") as f:
                f.write(
                    "import json, sys\n"
                    f"with open(r'{out_file}', 'w', encoding='utf-8') as f:\n"
                    "    json.dump(sys.argv[1:], f)\n"
                )

            rendered = lifecycle.render_lifecycle_script(
                action="test",
                base_cmd=[sys.executable, worker_file],
                status_tag="verified"
            )
            with open(hook_file, "w", encoding="utf-8") as f:
                f.write(rendered)

            tricky_args = [
                "arg with spaces",
                "semi;colon",
                "pipe|char",
                "and&operator",
                "quote'single",
                'quote"double',
                "$VARIABLE_TEST",
                "<redirect_in>",
                ">redirect_out>",
                "-k", "TestClass and not test_flake",
            ]

            # Run via along_exec router
            along_exec_script = os.path.join(SCRIPTS_DIR, "along_exec.py")
            res = proc.run_capture(
                [sys.executable, along_exec_script, "test", *tricky_args],
                cwd=fixture_root
            )
            self.assertEqual(res.returncode, 0, f"Router failed: {res.stderr}\nSTDOUT: {res.stdout}")

            self.assertTrue(os.path.exists(out_file), "Worker did not write output JSON")
            with open(out_file, "r", encoding="utf-8") as f:
                received_args = json.load(f)

            self.assertEqual(received_args, tricky_args)


if __name__ == "__main__":
    unittest.main()
