#!/usr/bin/env python3
"""
tests/test_subproject_model.py - [bug--subproject-model-overdetection].

Per [ADR-2026-10-06--subproject-boundary-is-git-or-explicit-init]: a package manifest is no
subproject (update offers no init and creates no context, the subproject-boundary gate ignores
a bare `package.json`), monorepo root markers are recognized, nested installs without `.git`
are reported (unless marked intentional) and left untouched, gate excludes match relative to
the owning context, sibling contexts resolve entity references, and a bound issue's
`write_scope` / `allowed_roots` cover edits outside its subproject. Throwaway directories only.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPTS_DIR = os.path.join(REPO_ROOT, "scripts")
if SCRIPTS_DIR not in sys.path:
    sys.path.insert(0, SCRIPTS_DIR)

from alongkit import bootstrap
bootstrap.ensure_deps()

from alongkit import entities, repo, session, textio
from alongkit.hooks import containment
from alongkit.hooks.predicates import (
    check_active_issue,
    check_mutation_authorization,
    check_subproject_boundary,
)

from test_entity_reference_integrity import _er_git, _er_issue, _er_write
from test_subproject_and_team_gates import KEY, Workspace, _put_issue, _write_event

UPDATE = os.path.join(SCRIPTS_DIR, "along_update.py")


def _scoped_issue(ctx: str, key: str, write_scope=(), allowed_roots=()) -> None:
    itype, slug = key.split("--", 1)
    textio.write_text(os.path.join(ctx, ".along", "ISSUES", f"{key}.md"),
                      f"---\nslug: {slug}\ntype: {itype}\nstatus: in-progress\n"
                      f"write_scope: [{', '.join(write_scope)}]\n"
                      f"allowed_roots: [{', '.join(allowed_roots)}]\n---\n\n# {slug}\n")


class TestContextRelativeExcludes(Workspace):
    """REQ-6: a sibling subproject's Along state passes; its scripts and sources do not."""

    def setUp(self):
        super().setUp()
        self.api = os.path.join(self.root, "api")
        os.makedirs(os.path.join(self.api, ".along", "ISSUES"))
        _put_issue(self.web, "feat--web-form")

    def test_other_subproject_state_passes_issue_anchoring(self):
        self.start(self.web, "feat--web-form")
        for rel in ("api/.along/ISSUES/feat--api-new.md", "api/.along/SESSIONS/2026/s.md",
                    "api/docs/topic--x.md"):
            self.assertIsNone(check_active_issue(_write_event(self.root, rel), self.root), rel)
        for rel in ("api/.along/scripts/test.py", "api/src/server.py"):
            self.assertIn("require-active-issue", check_active_issue(_write_event(self.root, rel), self.root), rel)

    def test_other_subproject_issue_passes_plan_gate_before_approval(self):
        self.start(self.web, "feat--web-form", approved=False)
        edit = _write_event(self.root, "api/.along/ISSUES/feat--api-new.md")
        self.assertIsNone(check_mutation_authorization(edit, self.root))
        self.assertIsNotNone(check_mutation_authorization(_write_event(self.root, "api/src/a.py"), self.root))


class TestBoundIssueScope(Workspace):
    """REQ-8: `write_scope` / `allowed_roots` of the bound subproject issue cover outside edits."""

    def setUp(self):
        super().setUp()
        _scoped_issue(self.web, "feat--web-form", write_scope=["../tests"])
        self.start(self.web, "feat--web-form")

    def test_scope_covers_edit_outside_the_subproject(self):
        self.assertIsNone(check_active_issue(_write_event(self.root, "tests/test_form.py"), self.root))
        message = check_active_issue(_write_event(self.root, "other/a.py"), self.root)
        self.assertIn("outside that subproject", message)
        self.assertIn("--write-scope", message)

    def test_containment_reads_the_bound_issue_and_keeps_its_context(self):
        policy = containment.build_policy(self.root, session_key=KEY)
        canon = containment.canonical
        self.assertTrue(policy.can_write(canon(os.path.join(self.root, "tests", "t.py"))))
        self.assertTrue(policy.can_write(canon(os.path.join(self.web, "src", "form.ts"))))
        self.assertFalse(policy.can_write(canon(os.path.join(self.root, "other", "a.py"))))


class TestBoundaryIgnoresBareManifest(Workspace):
    """REQ-5: a `package.json` folder without `.along/` is not a subproject."""

    def test_root_entity_write_from_manifest_folder(self):
        lib = os.path.join(self.root, "lib")
        os.makedirs(lib)
        textio.write_text(os.path.join(lib, "package.json"), "{}\n")
        edit = _write_event(self.root, ".along/ISSUES/feat--root-new.md")
        with mock.patch("os.getcwd", return_value=lib):
            self.assertIsNone(check_subproject_boundary(edit, self.root))
        with mock.patch("os.getcwd", return_value=self.web):
            self.assertIn("subproject-boundary", check_subproject_boundary(edit, self.root))


class TestSiblingReferences(unittest.TestCase):
    """REQ-7: entities of sibling subprojects resolve; a real dangling reference still fails."""

    def setUp(self):
        self.root = tempfile.mkdtemp(prefix="along_siblings_")
        _er_git(self.root, "init", "-q")
        self.web = os.path.join(self.root, "apps", "webapp")
        self.server = os.path.join(self.root, "apps", "server")
        _er_write(self.server, ".along/ISSUES/feat--catalog-import.md",
                  _er_issue("catalog-import", milestone=""))
        _er_write(self.web, ".along/ISSUES/feat--catalog-view.md",
                  _er_issue("catalog-view", milestone="", blocked_by=["feat--catalog-import"]))

    def tearDown(self):
        shutil.rmtree(self.root, ignore_errors=True)

    def test_sibling_reference_resolves(self):
        self.assertIn("feat--catalog-import", entities.sibling_entity_keys(self.web))
        self.assertEqual(entities.validate_entities(self.web)["errors"], [])
        messages = [m for _, m in entities.validate_entities(self.web, siblings=False)["errors"]]
        self.assertIn("dangling blocked_by reference: 'feat--catalog-import'", messages)

    def test_real_dangling_and_nested_repository_stay_out(self):
        nested = os.path.join(self.root, "apps", "vendored")
        os.makedirs(os.path.join(nested, ".git"))
        _er_write(nested, ".along/ISSUES/feat--vendored-task.md", _er_issue("vendored-task", milestone=""))
        _er_write(self.web, ".along/ISSUES/feat--catalog-view.md",
                  _er_issue("catalog-view", milestone="", blocked_by=["feat--vendored-task"]))
        self.assertNotIn("feat--vendored-task", entities.sibling_entity_keys(self.web))
        messages = [m for _, m in entities.validate_entities(self.web)["errors"]]
        self.assertEqual(messages, ["dangling blocked_by reference: 'feat--vendored-task'"])

    def test_git_top_has_no_siblings(self):
        self.assertEqual(entities.sibling_entity_keys(self.root), set())


class TestDiscoveryHelpers(unittest.TestCase):

    def setUp(self):
        self.root = tempfile.mkdtemp(prefix="along_discovery_")

    def tearDown(self):
        shutil.rmtree(self.root, ignore_errors=True)

    def test_monorepo_root_markers(self):
        self.assertEqual(repo.monorepo_root_markers(self.root), [])
        textio.write_text(os.path.join(self.root, "App.sln"), "\n")
        textio.write_text(os.path.join(self.root, "Directory.Packages.props"), "<Project/>\n")
        textio.write_text(os.path.join(self.root, "Cargo.toml"), "[workspace]\nmembers = []\n")
        self.assertEqual(repo.monorepo_root_markers(self.root),
                         ["App.sln", "Directory.Packages.props", "Cargo.toml [workspace]"])
        self.assertNotIn("Directory.Build.props", repo.STANDARD_MANIFESTS)

    def test_nested_contexts_reported_unless_intentional(self):
        for name in ("LibA", "LibB", "ext"):
            _er_write(self.root, f"{name}/.along/ISSUES/feat--x.md", "x\n")
        os.makedirs(os.path.join(self.root, "ext", ".git"))
        found = [os.path.basename(p) for p in repo.find_unmarked_nested_contexts(self.root)]
        self.assertEqual(found, ["LibA", "LibB"])
        textio.write_text(os.path.join(self.root, "LibB", ".along", "config.json"),
                          json.dumps({"subproject": {"intentional": True}}))
        found = [os.path.basename(p) for p in repo.find_unmarked_nested_contexts(self.root)]
        self.assertEqual(found, ["LibA"])
        self.assertEqual([os.path.basename(p) for p in repo.find_nested_git_roots(self.root)], ["ext"])

    def test_lone_agents_md_does_not_start_a_context(self):
        _er_write(self.root, ".along/ISSUES/feat--x.md", "x\n")
        guide = os.path.join(self.root, "pkg")
        _er_write(guide, "AGENTS.md", "# guide\n")
        self.assertEqual(os.path.normcase(repo.find_repo_root(guide)),
                         os.path.normcase(os.path.abspath(self.root)))
        self.assertFalse(repo.is_installed(guide))
        self.assertEqual(repo.find_agent_contexts(self.root), [os.path.abspath(self.root)])


class TestUpdateInSolutionRepository(unittest.TestCase):
    """REQ-1..REQ-3: one root context; no init hint for project folders; nested installs kept."""

    def setUp(self):
        self.root = tempfile.mkdtemp(prefix="along_solution_")
        _er_git(self.root, "init", "-q")
        textio.write_text(os.path.join(self.root, "App.sln"), "\n")
        textio.write_text(os.path.join(self.root, "Directory.Packages.props"), "<Project/>\n")
        textio.write_text(os.path.join(self.root, "AGENTS.md"), "# App\n\n## Project specifics\n")
        _er_write(self.root, ".along/ISSUES/feat--root-task.md", _er_issue("root-task", milestone=""))
        for name in ("LibA", "LibB", "LibC"):
            textio.write_text(os.path.join(self.root, name, f"{name}.csproj"), "<Project/>\n")
        self.legacy_issue = _er_write(self.root, "LibC/.along/ISSUES/feat--legacy-task.md",
                                      _er_issue("legacy-task", milestone=""))
        os.makedirs(os.path.join(self.root, "ext", ".git"))

    def tearDown(self):
        shutil.rmtree(self.root, ignore_errors=True)

    def test_update_creates_no_context_and_keeps_existing_nested_install(self):
        res = subprocess.run([sys.executable, UPDATE, self.root, "--local-only", "--no-hooks"],
                             capture_output=True, text=True, encoding="utf-8", errors="replace",
                             stdin=subprocess.DEVNULL)
        self.assertEqual(res.returncode, 0, res.stdout + res.stderr)
        for name in ("LibA", "LibB"):
            self.assertFalse(os.path.exists(os.path.join(self.root, name, ".along")), name)
            self.assertFalse(os.path.exists(os.path.join(self.root, name, "AGENTS.md")), name)
            self.assertNotIn(name, res.stdout)
        self.assertTrue(os.path.isfile(self.legacy_issue))
        self.assertIn("- ext (run 'along init' there only if", res.stdout)
        self.assertNotIn("/along-init", res.stdout)


if __name__ == "__main__":
    unittest.main()
