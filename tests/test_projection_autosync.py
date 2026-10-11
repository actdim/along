#!/usr/bin/env python3
"""
tests/test_projection_autosync.py - The Stop gate refreshes a stale ISSUES.md itself.

Regression suite for [feat--gate-friction-and-bypass-accountability] REQ-2: the gate used to
reject the turn on an mtime comparison and ask the agent to run `along issue sync`, which
deadlocked when plan mode (or the plan gate) forbade that write.
"""

from __future__ import annotations

import contextlib
import io
import os
import shutil
import sys
import time
import unittest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPTS_DIR = os.path.join(REPO_ROOT, "scripts")
if SCRIPTS_DIR not in sys.path:
    sys.path.insert(0, SCRIPTS_DIR)

from alongkit import bootstrap
bootstrap.ensure_deps()

from alongkit import entities, textio
from alongkit.hooks.predicates import check_projection_sync_before_stop
from hermetic import make_repo_fixture

ISSUE = """---
protocol: along
slug: {slug}
type: bug
status: open
priority: low
created: 2026-10-11
updated: 2026-10-11
---

# {slug}
"""


class TestProjectionAutoSync(unittest.TestCase):
    def setUp(self):
        self.root = make_repo_fixture(prefix="along-autosync-")
        self.board = os.path.join(self.root, ".along", "ISSUES.md")
        entities.sync_issues_board(self.root)

    def tearDown(self):
        shutil.rmtree(self.root, ignore_errors=True)

    def _stop(self):
        err = io.StringIO()
        with contextlib.redirect_stderr(err):
            result = check_projection_sync_before_stop(None, self.root)
        return result, err.getvalue()

    def test_stale_board_is_rewritten_and_the_stop_is_not_blocked(self):
        textio.write_text(os.path.join(self.root, ".along", "ISSUES", "bug--new-one.md"),
                          ISSUE.format(slug="new-one"))
        result, err = self._stop()
        self.assertIsNone(result)
        self.assertIn("bug--new-one", textio.read_text(self.board))
        self.assertIn("Auto-synced", err)

    def test_newer_mtime_with_equal_content_is_not_stale(self):
        issue = os.path.join(self.root, ".along", "ISSUES", "task--fixture-sample-task.md")
        future = time.time() + 60
        os.utime(issue, (future, future))
        before = textio.read_text(self.board)
        result, err = self._stop()
        self.assertIsNone(result)
        self.assertEqual(textio.read_text(self.board), before)
        self.assertEqual(err, "")

    def test_nested_context_board_is_refreshed(self):
        sub = os.path.join(self.root, "sub")
        os.makedirs(os.path.join(sub, ".along", "ISSUES", "done"))
        textio.write_text(os.path.join(sub, ".along", "ISSUES", "bug--child.md"),
                          ISSUE.format(slug="child"))
        result, _err = self._stop()
        self.assertIsNone(result)
        self.assertIn("bug--child", textio.read_text(os.path.join(sub, ".along", "ISSUES.md")))


if __name__ == "__main__":
    unittest.main(verbosity=2)
