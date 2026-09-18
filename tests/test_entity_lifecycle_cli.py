#!/usr/bin/env python3
"""
tests/test_entity_lifecycle_cli.py - Tests for entity lifecycle CLI, issue updates,
fuzzy milestone resolution, bidirectional milestone synchronization, and along start.
"""

from __future__ import annotations

import json
import os
import shutil
import sys
import unittest

if not os.environ.get("ALONG_TEST_RUNNER"):
    raise SystemExit(
        "[Error] Tests must not be run directly or via standard test commands (unittest/pytest).\n"
        "To run tests with automatically resolved dependencies, use the official project entry point:\n"
        "    python .along/scripts/test.py"
    )

import hermetic
from alongkit import entities, frontmatter, proc, textio


class TestEntityLifecycleCli(unittest.TestCase):

    def setUp(self):
        self.repo = hermetic.make_repo_fixture(prefix="along-entity-lifecycle-test-")
        self.along_exec = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "scripts", "along_exec.py"
        )
        self.issues_dir = os.path.join(self.repo, ".along", "ISSUES")
        self.done_dir = os.path.join(self.issues_dir, "done")
        self.milestones_dir = os.path.join(self.repo, ".along", "MILESTONES")
        os.makedirs(self.done_dir, exist_ok=True)
        os.makedirs(self.milestones_dir, exist_ok=True)

    def tearDown(self):
        shutil.rmtree(self.repo, ignore_errors=True)

    def _create_sample_milestone(self, slug: str, title: str, status: str = "open") -> str:
        fpath = os.path.join(self.milestones_dir, f"{slug}.md")
        fm = {
            "protocol": "along",
            "slug": slug,
            "title": title,
            "status": status,
            "due_date": "2026-12-31",
            "created": "2026-09-01",
            "target_issues": [],
            "progress_pct": 0,
        }
        content = frontmatter.render(fm, f"# Milestone: {title}\n\nMilestone description.")
        textio.write_text(fpath, content, newline="\n")
        return fpath

    def _create_sample_issue(self, itype: str, slug: str, status: str = "open", milestone: str = None, done: bool = False) -> str:
        target_dir = self.done_dir if done else self.issues_dir
        fpath = os.path.join(target_dir, f"{itype}--{slug}.md")
        fm = {
            "protocol": "along",
            "slug": slug,
            "type": itype,
            "status": status,
            "priority": "medium",
            "created": "2026-09-01",
            "updated": "2026-09-01",
            "agent": "antigravity",
            "tags": ["test"],
            "milestone": milestone,
            "blocked_by": [],
            "related": [],
        }
        if done or status == "done":
            fm["completed"] = "2026-09-02"
        content = frontmatter.render(fm, f"# {slug.replace('-', ' ').capitalize()}\n\nIssue requirements.")
        textio.write_text(fpath, content, newline="\n")
        return fpath

    def test_fuzzy_milestone_resolution(self):
        self._create_sample_milestone("v4.0.0-runtime-gates-and-worktree-isolation", "v4.0.0 Runtime Gates")
        self._create_sample_milestone("v3.2.0-core-refactor", "v3.2.0 Core Refactor")

        # Exact match
        m1 = entities.resolve_milestone_by_query(self.repo, "v4.0.0-runtime-gates-and-worktree-isolation")
        self.assertIsNotNone(m1)
        self.assertEqual(m1["slug"], "v4.0.0-runtime-gates-and-worktree-isolation")

        # Version prefix matching
        m2 = entities.resolve_milestone_by_query(self.repo, "4.0")
        self.assertIsNotNone(m2)
        self.assertEqual(m2["slug"], "v4.0.0-runtime-gates-and-worktree-isolation")

        m3 = entities.resolve_milestone_by_query(self.repo, "v4.0")
        self.assertIsNotNone(m3)
        self.assertEqual(m3["slug"], "v4.0.0-runtime-gates-and-worktree-isolation")

        m4 = entities.resolve_milestone_by_query(self.repo, "3.2")
        self.assertIsNotNone(m4)
        self.assertEqual(m4["slug"], "v3.2.0-core-refactor")

        # Substring match
        m5 = entities.resolve_milestone_by_query(self.repo, "runtime-gates")
        self.assertIsNotNone(m5)
        self.assertEqual(m5["slug"], "v4.0.0-runtime-gates-and-worktree-isolation")

        # Non-existent
        m_none = entities.resolve_milestone_by_query(self.repo, "non-existent-milestone")
        self.assertIsNone(m_none)

    def test_issue_update_cli(self):
        m_path = self._create_sample_milestone("v4.0.0-runtime-gates-and-worktree-isolation", "v4.0.0 Runtime Gates")
        i_path = self._create_sample_issue("feat", "token-refresh")

        # Run issue update with fuzzy milestone and priority
        res = proc.run_capture([
            sys.executable, self.along_exec, "issue", "update", "token-refresh",
            "--milestone", "4.0",
            "--priority", "high",
            "--status", "in-progress",
            "--tags", "auth,tokens,security",
            "--title", "JWT Token Refresh Flow"
        ], cwd=self.repo)
        self.assertTrue(res.ok, f"Command failed: {res.stderr}")

        # Check updated issue frontmatter
        iss = entities.find_issue_by_slug(self.repo, "token-refresh")
        self.assertIsNotNone(iss)
        fm = iss["frontmatter"]
        self.assertEqual(fm["milestone"], "v4.0.0-runtime-gates-and-worktree-isolation")
        self.assertEqual(fm["priority"], "high")
        self.assertEqual(fm["status"], "in-progress")
        self.assertEqual(fm["tags"], ["auth", "tokens", "security"])
        self.assertEqual(fm["title"], "JWT Token Refresh Flow")

        # Verify milestone was automatically synchronized
        m_content = textio.read_text(m_path)
        m_fm, _, _ = frontmatter.try_parse(m_content)
        self.assertIn("feat--token-refresh", m_fm.get("target_issues", []))
        self.assertEqual(m_fm.get("status"), "in-progress")
        self.assertEqual(m_fm.get("progress_pct"), 0)

    def test_issue_show_cli(self):
        self._create_sample_issue("feat", "query-search", status="open")

        # Text format
        res_text = proc.run_capture([
            sys.executable, self.along_exec, "issue", "show", "query-search"
        ], cwd=self.repo)
        self.assertTrue(res_text.ok)
        self.assertIn("Issue: query-search (feat)", res_text.stdout)
        self.assertIn("Status:    open", res_text.stdout)

        # JSON format
        res_json = proc.run_capture([
            sys.executable, self.along_exec, "issue", "show", "query-search", "--json"
        ], cwd=self.repo)
        self.assertTrue(res_json.ok)
        data = json.loads(res_json.stdout)
        self.assertEqual(data["slug"], "query-search")
        self.assertEqual(data["type"], "feat")
        self.assertEqual(data["status"], "open")

    def test_milestone_sync_and_progress_recalculation(self):
        m_slug = "v2.5.0-feature-pack"
        m_path = self._create_sample_milestone(m_slug, "v2.5.0 Feature Pack", status="open")

        # Create two issues targeting this milestone
        self._create_sample_issue("feat", "task-alpha", status="open", milestone=m_slug, done=False)
        self._create_sample_issue("bug", "task-beta", status="done", milestone=m_slug, done=True)

        # Run milestone sync
        res = proc.run_capture([
            sys.executable, self.along_exec, "milestone", "sync", m_slug
        ], cwd=self.repo)
        self.assertTrue(res.ok, f"milestone sync failed: {res.stderr}")
        self.assertIn("v2.5.0-feature-pack: in-progress (50%, 1/2 issues completed)", res.stdout)

        m_fm, _, _ = frontmatter.try_parse(textio.read_text(m_path))
        self.assertEqual(m_fm["progress_pct"], 50)
        self.assertEqual(m_fm["status"], "in-progress")
        self.assertEqual(sorted(m_fm["target_issues"]), ["bug--task-beta", "feat--task-alpha"])

        # Mark the remaining issue as done
        entities.update_issue_frontmatter(self.repo, "task-alpha", {"status": "done", "completed": "2026-09-03"})
        # Move to done dir
        src = os.path.join(self.issues_dir, "feat--task-alpha.md")
        dst = os.path.join(self.done_dir, "feat--task-alpha.md")
        os.rename(src, dst)

        # Re-sync
        res2 = proc.run_capture([
            sys.executable, self.along_exec, "milestone", "sync", m_slug
        ], cwd=self.repo)
        self.assertTrue(res2.ok)
        self.assertIn("v2.5.0-feature-pack: completed (100%, 2/2 issues completed)", res2.stdout)

        m_fm2, _, _ = frontmatter.try_parse(textio.read_text(m_path))
        self.assertEqual(m_fm2["progress_pct"], 100)
        self.assertEqual(m_fm2["status"], "completed")

    def test_milestone_list_and_show_cli(self):
        self._create_sample_milestone("v1.0.0-first", "First Milestone", status="completed")
        self._create_sample_milestone("v2.0.0-second", "Second Milestone", status="open")

        # List
        res_list = proc.run_capture([
            sys.executable, self.along_exec, "milestone", "list"
        ], cwd=self.repo)
        self.assertTrue(res_list.ok)
        self.assertIn("v1.0.0-first", res_list.stdout)
        self.assertIn("v2.0.0-second", res_list.stdout)

        # Show
        res_show = proc.run_capture([
            sys.executable, self.along_exec, "milestone", "show", "first"
        ], cwd=self.repo)
        self.assertTrue(res_show.ok)
        self.assertIn("Milestone: v1.0.0-first", res_show.stdout)
        self.assertIn("Status:       completed", res_show.stdout)

    def test_along_start_orchestrator(self):
        self._create_sample_issue("feat", "deploy-pipeline", status="open")

        # Run along start
        res = proc.run_capture([
            sys.executable, self.along_exec, "start", "deploy-pipeline"
        ], cwd=self.repo)
        self.assertTrue(res.ok, f"along start failed: {res.stderr}")
        self.assertIn("Marked issue in-progress", res.stdout)
        self.assertIn("Initialized session blackboard", res.stdout)

        # Check issue status is now in-progress
        iss = entities.find_issue_by_slug(self.repo, "deploy-pipeline")
        self.assertEqual(iss["status"], "in-progress")

        # Check session blackboard initialized
        session_state_file = os.path.join(self.repo, ".along", ".session", "deploy-pipeline", "state.json")
        self.assertTrue(os.path.isfile(session_state_file))

    def test_error_handling_invalid_inputs(self):
        # Update non-existent issue
        res_bad_iss = proc.run_capture([
            sys.executable, self.along_exec, "issue", "update", "does-not-exist", "--priority", "high"
        ], cwd=self.repo)
        self.assertFalse(res_bad_iss.ok)
        self.assertIn("not found", res_bad_iss.stderr)

        # Invalid priority
        self._create_sample_issue("feat", "simple-task")
        res_bad_prio = proc.run_capture([
            sys.executable, self.along_exec, "issue", "update", "simple-task", "--priority", "invalid-prio"
        ], cwd=self.repo)
        self.assertFalse(res_bad_prio.ok)
        self.assertIn("Invalid priority", res_bad_prio.stderr)

        # Invalid milestone query
        res_bad_m = proc.run_capture([
            sys.executable, self.along_exec, "issue", "update", "simple-task", "--milestone", "ghost-milestone"
        ], cwd=self.repo)
        self.assertFalse(res_bad_m.ok)
        self.assertIn("Milestone 'ghost-milestone' not found", res_bad_m.stderr)


if __name__ == "__main__":
    unittest.main()
