#!/usr/bin/env python3
"""
tests/test_cli_argparse.py - Tests for modular argparse subparsers and flag validation.
[debt--along-exec-argparse-migration]
"""

from __future__ import annotations

import glob
import os
import re
import shlex
import shutil
import sys
import unittest

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
TESTS_DIR = os.path.dirname(os.path.abspath(__file__))
if TESTS_DIR not in sys.path:
    sys.path.insert(0, TESTS_DIR)

import hermetic
from alongkit import proc
from alongkit.commands import (
    decision,
    issue,
    milestone,
    scratch,
    session,
    worktree,
)

ALONG_EXEC = os.path.join(SCRIPTS_DIR, "along_exec.py")


class TestCliArgparse(unittest.TestCase):
    def setUp(self):
        self.repo = hermetic.make_repo_fixture(prefix="along-cli-argparse-test-")
        self.env = hermetic.isolated_home_env()
        self.env.pop("ALONG_SESSION_ID", None)

    def tearDown(self):
        shutil.rmtree(self.repo, ignore_errors=True)

    def _run(self, *args: str) -> proc.Result:
        return proc.run_capture(
            [sys.executable, ALONG_EXEC, *args],
            cwd=self.repo,
            env=self.env,
            timeout=30,
        )

    def test_misspelled_flags_fail_with_code_2(self):
        """Misspelled or unrecognized flags must fail loudly with exit code 2."""
        cases = [
            # issue
            (["issue", "create", "feat", "x-y", "--prioirty", "high"], "along issue create"),
            (["issue", "create", "feat", "x-y", "--title", "T", "--unknown-flag"], "along issue create"),
            (["issue", "update", "x-y", "--milstone", "v1.0"], "along issue update"),
            (["issue", "done", "x-y", "--statuss", "done"], "along issue done"),
            (["issue", "list", "--invlaid"], "along issue list"),
            (["issue", "sync", "--bad-arg"], "along issue sync"),
            # milestone
            (["milestone", "create", "v9.9.9", "--tilte", "Release"], "along milestone create"),
            (["milestone", "list", "--stauts", "open"], "along milestone list"),
            (["milestone", "sync", "--bad"], "along milestone sync"),
            # session
            (["session", "create", "s-1", "--sumary", "Work"], "along session create"),
            (["session", "wrap", "s-1", "--statuss", "done", "--no-decisions"], "along session wrap"),
            (["session", "gc", "--invlaid"], "along session gc"),
            (["session", "list", "--bad"], "along session list"),
            # decision
            (["decision", "create", "d-1", "--titel", "Dec"], "along decision create"),
            (["decision", "sync", "--chekc"], "along decision sync"),
            # scratch
            (["scratch", "init", "sc-1", "--setps", "3"], "along scratch init"),
            (["scratch", "update", "sc-1", "--stpe", "1"], "along scratch update"),
            (["scratch", "state", "sc-1", "--invalid"], "along scratch state"),
            # worktree
            (["worktree", "create", "wt-1", "--branc", "main"], "along worktree create"),
            (["worktree", "remove", "wt-1", "--froce"], "along worktree remove"),
            (["worktree", "list", "--bad"], "along worktree list"),
            (["worktree", "gc", "--extra"], "along worktree gc"),
        ]

        for argv, expected_prog in cases:
            with self.subTest(cmd=" ".join(argv)):
                res = self._run(*argv)
                self.assertEqual(res.returncode, 2, f"Expected exit code 2 for {argv}, got {res.returncode}. stderr={res.stderr}")
                self.assertIn("error: unrecognized argument", res.stderr.lower())

    def test_commands_library_modules_execution_guards(self):
        """Every module under scripts/alongkit/commands/*.py must refuse direct execution."""
        commands_dir = os.path.join(SCRIPTS_DIR, "alongkit", "commands")
        py_files = glob.glob(os.path.join(commands_dir, "*.py"))
        self.assertGreaterEqual(len(py_files), 7)

        for py_path in py_files:
            rel = os.path.basename(py_path)
            with self.subTest(module=rel):
                res = proc.run_capture([sys.executable, py_path], cwd=self.repo)
                self.assertNotEqual(res.returncode, 0)
                self.assertIn("is a library module, not a command.", res.stderr + res.stdout)
                self.assertIn("Run: python .along/scripts/test.py", res.stderr + res.stdout)

    def test_documented_concrete_invocations_parse_cleanly(self):
        """All concrete along invocations in topic--cli-reference.md must parse without exit 2."""
        cli_ref = os.path.join(REPO_ROOT, "docs", "topic--cli-reference.md")
        self.assertTrue(os.path.exists(cli_ref))

        parsers = {
            "issue": issue.build_parser(),
            "milestone": milestone.build_parser(),
            "session": session.build_parser(),
            "decision": decision.build_parser(),
            "scratch": scratch.build_parser(),
            "worktree": worktree.build_parser(),
        }

        with open(cli_ref, "r", encoding="utf-8") as f:
            content = f.read()

        # Find concrete command invocations: indented lines starting with '  along <cmd> <subcmd> ...'
        lines = [line.strip() for line in content.splitlines()]
        concrete_cmds = []
        for line in lines:
            if line.startswith("along ") and not any(placeholder in line for placeholder in ["<", ">", "[", "...", "|", "{"]):
                concrete_cmds.append(line)

        self.assertGreaterEqual(len(concrete_cmds), 20)

        for cmd_str in concrete_cmds:
            parts = shlex.split(cmd_str)
            router = parts[1]
            if router not in parsers:
                continue

            sub_args = parts[2:]
            with self.subTest(cmd=cmd_str):
                p = parsers[router]
                try:
                    p.parse_args(sub_args)
                except SystemExit as exc:
                    self.fail(f"Documented command failed argparse parsing: {cmd_str} (exit code {exc.code})")

    def test_skills_documented_commands_parse_cleanly(self):
        """Documented command invocations in skills/*/SKILL.md must parse cleanly."""
        skill_files = glob.glob(os.path.join(REPO_ROOT, "skills", "*", "SKILL.md"))
        parsers = {
            "issue": issue.build_parser(),
            "milestone": milestone.build_parser(),
            "session": session.build_parser(),
            "decision": decision.build_parser(),
            "scratch": scratch.build_parser(),
            "worktree": worktree.build_parser(),
        }

        tested_count = 0
        for s_file in skill_files:
            with open(s_file, "r", encoding="utf-8") as f:
                lines = f.readlines()

            for line in lines:
                m = re.search(r'`(along (issue|milestone|session|decision|scratch|worktree)\s+[^`]+)`', line)
                if not m:
                    m = re.search(r'^\s*(along (issue|milestone|session|decision|scratch|worktree)\s+.*)$', line)
                if not m:
                    continue

                raw_cmd = m.group(1).strip()
                # Remove optional brackets [--flag ...]
                normalized = re.sub(r'\[[^\]]*\]', '', raw_cmd)
                # Substitute placeholders <...> with dummy valid values
                normalized = re.sub(r'<type>', 'feat', normalized)
                normalized = re.sub(r'<slug[^>]*>', 'fixture-slug', normalized)
                normalized = re.sub(r'<old-key>', 'feat--old-key', normalized)
                normalized = re.sub(r'<new-key>', 'feat--new-key', normalized)
                normalized = re.sub(r'<[N0-9+]+>', '1', normalized)
                normalized = re.sub(r'<text>', 'reason', normalized)
                normalized = re.sub(r'<ADR\.\.\.>', 'ADR-1', normalized)
                normalized = re.sub(r'<target>', 'target', normalized)

                # Skip unparseable syntax templates like "close <slug>... | --ready"
                if "|" in normalized or "..." in normalized or "<" in normalized:
                    continue

                parts = shlex.split(normalized)
                if len(parts) < 3:
                    continue
                router = parts[1]
                if router not in parsers:
                    continue

                sub_args = parts[2:]
                # Skip bare mentions like `along decision create` or `along issue create` without a slug
                if len(sub_args) < 2 and sub_args and sub_args[0] in ("create", "update", "fallback", "phase", "supersede", "rename"):
                    continue
                with self.subTest(cmd=normalized, file=os.path.basename(s_file)):
                    p = parsers[router]
                    try:
                        p.parse_args(sub_args)
                        tested_count += 1
                    except SystemExit as exc:
                        self.fail(f"Skill invocation failed argparse: {normalized} from {s_file} (code {exc.code})")

        self.assertGreaterEqual(tested_count, 10)


if __name__ == "__main__":
    unittest.main()
