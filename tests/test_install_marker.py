#!/usr/bin/env python3
"""
tests/test_install_marker.py - [bug--along-install-marker-ambiguous].

Per [ADR-2026-10-07--along-installation-is-state-not-agents-md]: a folder has Along installed
only when it holds Along state; a nested AGENTS.md is a folder guide and a stateless `.along/`
is a side effect. Board commands refuse outside an installation, lifecycle and history sync
create nothing there, `along update` leaves folder guides alone, `kb-sync` compiles package
docs without a `.along/`, and a known test runner's silence is no test run. Throwaway
directories only, child processes run with an isolated home.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
import unittest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPTS_DIR = os.path.join(REPO_ROOT, "scripts")
if SCRIPTS_DIR not in sys.path:
    sys.path.insert(0, SCRIPTS_DIR)

from alongkit import bootstrap
bootstrap.ensure_deps()

from alongkit import lifecycle, repo, session, textio

import hermetic

EXEC = os.path.join(SCRIPTS_DIR, "along_exec.py")
ENV = {k: v for k, v in hermetic.isolated_home_env().items() if k not in session.SESSION_ENV_VARS}


def _run(script, *args, cwd):
    return subprocess.run([sys.executable, script, *args], cwd=cwd, env=ENV, capture_output=True,
                          text=True, encoding="utf-8", errors="replace", stdin=subprocess.DEVNULL)


class _Tmp(unittest.TestCase):

    def setUp(self):
        self.root = tempfile.mkdtemp(prefix="along_marker_")
        subprocess.run(["git", "init", "-q", self.root], check=True)

    def tearDown(self):
        shutil.rmtree(self.root, ignore_errors=True)

    def path(self, *parts):
        return os.path.join(self.root, *parts)

    def write(self, rel, text="x\n"):
        textio.write_text(self.path(*rel.split("/")), text)


class TestDefinition(_Tmp):
    """REQ-1, REQ-2."""

    def test_only_state_makes_an_installation(self):
        os.makedirs(self.path("empty", ".along"))
        os.makedirs(self.path("side", ".along", "scripts"))
        os.makedirs(self.path("side", ".along", "artifacts"))
        self.write("guide/AGENTS.md", "# guide\n")
        os.makedirs(self.path("real", ".along", "ISSUES"))
        for name, expected in (("empty", False), ("side", False), ("guide", False), ("real", True)):
            self.assertEqual(repo.is_installed(self.path(name)), expected, name)

    def test_walk_passes_guides_and_side_effect_dirs(self):
        os.makedirs(self.path(".along", "ISSUES"))
        self.write("pkg/AGENTS.md", "# guide\n")
        os.makedirs(self.path("pkg", "src", ".along", "artifacts"))
        start = self.path("pkg", "src", "deep")
        os.makedirs(start)
        self.assertEqual(os.path.normcase(repo.find_repo_root(start)), os.path.normcase(self.root))
        self.assertEqual(repo.find_agent_contexts(self.root), [os.path.abspath(self.root)])

    def test_diagnostics_never_create_a_state_dir_outside_an_installation(self):
        self.assertNotIn(os.path.normcase(self.root), os.path.normcase(repo.diagnostics_dir(self.root)))
        os.makedirs(self.path(".along", "ISSUES"))
        self.assertEqual(os.path.normcase(repo.diagnostics_dir(self.root)),
                         os.path.normcase(self.path(".along", "diagnostics")))


class TestNothingCreatesAContext(_Tmp):
    """REQ-3."""

    def test_board_command_refuses_outside_an_installation(self):
        res = _run(EXEC, "issue", "create", "bug", "stray-issue-here", "--title", "T", cwd=self.root)
        self.assertEqual(res.returncode, 2, res.stdout + res.stderr)
        self.assertIn("not installed", res.stderr)
        self.assertFalse(os.path.exists(self.path(".along")))

    def test_issue_from_a_guide_folder_lands_in_the_installation(self):
        os.makedirs(self.path(".along", "ISSUES"))
        self.write("pkg/AGENTS.md", "# package guide\n")
        res = _run(EXEC, "issue", "create", "bug", "guide-folder-issue", "--title", "T",
                   "--no-milestone", cwd=self.path("pkg"))
        self.assertEqual(res.returncode, 0, res.stdout + res.stderr)
        self.assertTrue(os.path.isfile(self.path(".along", "ISSUES", "bug--guide-folder-issue.md")))
        self.assertFalse(os.path.exists(self.path("pkg", ".along")))

    def test_lifecycle_runs_without_writing_a_hook(self):
        self.write("pyproject.toml", "[project]\nname = 'x'\n")
        self.write("tests/test_x.py", "import unittest\n\nclass T(unittest.TestCase):\n"
                                      "    def test_ok(self):\n        self.assertTrue(True)\n")
        res = _run(EXEC, "test", "--distill", cwd=self.root)
        self.assertIn("without writing a hook", res.stdout)
        self.assertFalse(os.path.exists(self.path(".along")))

    def test_history_sync_refuses_to_synthesize_outside_an_installation(self):
        res = _run(os.path.join(SCRIPTS_DIR, "along_history_sync.py"), self.root, "--synthesize", cwd=self.root)
        self.assertEqual(res.returncode, 2, res.stdout + res.stderr)
        self.assertFalse(os.path.exists(self.path(".along")))


class TestUpdateAndKnowledgeBase(_Tmp):
    """REQ-2, REQ-4."""

    def test_update_leaves_folder_guides_alone(self):
        self.write("AGENTS.md", "# App\n\n## Project specifics\n")
        os.makedirs(self.path(".along", "ISSUES"))
        self.write("pkg/AGENTS.md", "# Package guide\n")
        res = _run(os.path.join(SCRIPTS_DIR, "along_update.py"), self.root, "--local-only", "--no-hooks",
                   cwd=self.root)
        self.assertEqual(res.returncode, 0, res.stdout + res.stderr)
        self.assertEqual(textio.read_text(self.path("pkg", "AGENTS.md")), "# Package guide\n")
        self.assertIn("BEGIN ALONG-PROTOCOL", textio.read_text(self.path("AGENTS.md")))

    def test_kb_sync_compiles_package_docs_without_a_context(self):
        os.makedirs(self.path(".along", "ISSUES"))
        self.write("docs/topic--root.md", "---\nslug: root\ntitle: Root\ntype: topic\n---\n# Root\nBody.\n")
        self.write("Pkg/Pkg.csproj", "<Project/>\n")
        self.write("Pkg/docs/topic--pkg.md", "---\nslug: pkg\ntitle: Pkg\ntype: topic\n---\n# Pkg\nBody.\n")
        self.assertEqual(repo.find_package_doc_roots(self.root), [os.path.abspath(self.path("Pkg"))])
        res = _run(os.path.join(SCRIPTS_DIR, "along_kb_sync.py"), self.root, cwd=self.root)
        self.assertEqual(res.returncode, 0, res.stdout + res.stderr)
        self.assertTrue(os.path.isfile(self.path("Pkg", "docs", "INDEX.md")))
        self.assertFalse(os.path.exists(self.path("Pkg", ".along")))


class TestKnownRunnerSilence(unittest.TestCase):
    """REQ-5."""

    def test_silence_of_a_known_runner_is_no_test_run(self):
        hook = ["python", ".along/scripts/test.py"]
        self.assertEqual(lifecycle.tests_ran(hook, "-> Running: dotnet test -v q\nBuild succeeded.\n"), 0)
        self.assertEqual(lifecycle.tests_ran(["pytest", "-q"], ""), 0)
        self.assertEqual(lifecycle.tests_ran(["go", "test", "./..."], "ok  \texample.com/x\t0.1s\n"), 1)
        self.assertIsNone(lifecycle.tests_ran(hook, "custom check passed\n"))


if __name__ == "__main__":
    unittest.main()
