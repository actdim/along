#!/usr/bin/env python3
"""
tests/test_cli_entity_sync.py - [bug--cli-entity-sync-defects].

Covers: `sync_milestones` leaving completed milestones alone unless named and keeping explicit
`target_issues` entries, `along session create` filing issues by status with a real Work
Completed section and test evidence from recorded `along test` runs, `along issue cancel`, and
`along issue delete` (reference cleanup, refusals). Every test runs in a throwaway git
repository; nothing touches the live repository.
"""

from __future__ import annotations

import glob
import os
import subprocess
import sys
import unittest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPTS_DIR = os.path.join(REPO_ROOT, "scripts")
if SCRIPTS_DIR not in sys.path:
    sys.path.insert(0, SCRIPTS_DIR)

from alongkit import bootstrap
bootstrap.ensure_deps()

from alongkit import entities, frontmatter, session, testruns, textio

from test_entity_reference_integrity import (
    EXEC, MILESTONE, _ErRepo, _er_fm, _er_git, _er_issue, _er_milestone, _er_write,
)

CLEAN_ENV = {k: v for k, v in os.environ.items() if k not in session.SESSION_ENV_VARS}


class _CliRepo(_ErRepo):

    def run_cli(self, *args):
        return subprocess.run([sys.executable, EXEC, *args], cwd=self.root, env=CLEAN_ENV,
                              capture_output=True, text=True, encoding="utf-8", errors="replace")


class TestMilestoneSyncKeepsExplicitLists(_CliRepo):
    """REQ-1."""

    def setUp(self):
        super().setUp()
        self.done_m = _er_write(self.root, ".along/MILESTONES/v0.9.0-old-release.md",
                                _er_milestone(["feat--alpha-task"], status="completed",
                                              slug="v0.9.0-old-release"))

    def test_completed_milestone_left_alone_unless_named(self):
        before = textio.read_text(self.done_m)
        entities.sync_milestones(self.root)
        self.assertEqual(textio.read_text(self.done_m), before)
        entities.sync_milestones(self.root, "v0.9.0-old-release")
        self.assertNotEqual(textio.read_text(self.done_m), before)

    def test_explicit_entry_kept_unless_issue_names_another_milestone(self):
        _er_write(self.root, ".along/ISSUES/feat--gamma-task.md", _er_issue("gamma-task", milestone=""))
        _er_write(self.root, f".along/MILESTONES/{MILESTONE}.md",
                  _er_milestone(["feat--alpha-task", "feat--beta-task", "feat--gamma-task",
                                 "feat--long-gone-task"]))
        _er_write(self.root, ".along/ISSUES/feat--beta-task.md",
                  _er_issue("beta-task", milestone="v0.9.0-old-release"))
        entities.sync_milestones(self.root, MILESTONE)
        targets = _er_fm(self.m)["target_issues"]
        self.assertEqual(targets, ["feat--alpha-task", "feat--gamma-task"])


class TestSessionCreateScaffold(_CliRepo):
    """REQ-2."""

    def test_issues_filed_by_status_with_work_lines(self):
        _er_write(self.root, ".along/ISSUES/done/feat--old-task.md", _er_issue("old-task", status="done"))
        res = self.run_cli("session", "create", "fixture-run", "--summary", "S",
                           "--issues", "alpha-task,feat--old-task")
        self.assertEqual(res.returncode, 0, res.stdout + res.stderr)
        path = glob.glob(os.path.join(self.root, ".along", "SESSIONS", "*", "*--fixture-run.md"))[0]
        fm, body = frontmatter.parse(textio.read_text(path), path=path)
        self.assertEqual(fm["issues_advanced"], ["feat--alpha-task"])
        self.assertEqual(fm["issues_completed"], ["feat--old-task"])
        self.assertNotIn("Document key tasks", body)
        self.assertIn("`feat--alpha-task`: alpha-task (open)", body)

    def test_recorded_green_run_is_test_evidence(self):
        self.commit_all()
        testruns.record_run(self.root, True, testruns.tree_hash(self.root), "along test")
        res = self.run_cli("session", "create", "fixture-run", "--summary", "S")
        self.assertEqual(res.returncode, 0, res.stdout + res.stderr)
        path = glob.glob(os.path.join(self.root, ".along", "SESSIONS", "*", "*--fixture-run.md"))[0]
        self.assertIn("passing `along test` run was recorded", textio.read_text(path))


class TestIssueCancelAndDelete(_CliRepo):
    """REQ-3."""

    def test_cancel_closes_as_cancelled(self):
        res = self.run_cli("issue", "cancel", "beta-task")
        self.assertEqual(res.returncode, 0, res.stdout + res.stderr)
        path = os.path.join(self.root, ".along", "ISSUES", "done", "feat--beta-task.md")
        self.assertEqual(_er_fm(path)["status"], "cancelled")

    def test_delete_strips_references(self):
        _er_write(self.root, ".along/ISSUES/feat--gamma-task.md",
                  _er_issue("gamma-task", related=["feat--beta-task"]))
        res = self.run_cli("issue", "delete", "beta-task")
        self.assertEqual(res.returncode, 0, res.stdout + res.stderr)
        self.assertFalse(os.path.exists(self.b))
        self.assertNotIn("feat--beta-task", _er_fm(self.m)["target_issues"])
        gamma = os.path.join(self.root, ".along", "ISSUES", "feat--gamma-task.md")
        self.assertEqual(_er_fm(gamma)["related"], [])
        self.assertEqual(entities.validate_entities(self.root)["errors"], [])

    def test_delete_refused_when_history_or_commit_names_it(self):
        res = self.run_cli("issue", "delete", "alpha-task")      # named by the session log
        self.assertEqual(res.returncode, 1)
        self.assertIn("issue cancel", res.stderr)
        self.assertTrue(os.path.exists(self.a))
        self.commit_all()
        _er_git(self.root, "commit", "-q", "--allow-empty", "--no-verify", "-m", "fix(x): y (refs #beta-task)")
        res = self.run_cli("issue", "delete", "beta-task")
        self.assertEqual(res.returncode, 1)
        self.assertIn("mentions 'beta-task'", res.stderr)
        self.assertTrue(os.path.exists(self.b))


if __name__ == "__main__":
    unittest.main()
