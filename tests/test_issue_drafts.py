#!/usr/bin/env python3
"""tests/test_issue_drafts.py - First-class untracked issue drafts with promotion.

[feat--issue-drafts-lifecycle]
"""

from __future__ import annotations

import contextlib
import io
import os
import shutil
import sys
import time
import unittest
from unittest import mock

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPTS_DIR = os.path.join(REPO_ROOT, "scripts")
if SCRIPTS_DIR not in sys.path:
    sys.path.insert(0, SCRIPTS_DIR)

from alongkit import bootstrap
bootstrap.ensure_deps()

import along_exec
from alongkit import drafts, entities, proc, session, textio
from alongkit.exceptions import CommandError, ValidationError
import hermetic

CLEAN_ENV = {
    k: v for k, v in os.environ.items()
    if k not in session.SESSION_ENV_VARS and k not in ("ALONG_PROFILE", "ALONG_AUTONOMOUS")
}
SID = "sess-drafts"
KEY = session.session_key("claude", SID)


class TestIssueDrafts(unittest.TestCase):
    def setUp(self):
        self.env = mock.patch.dict(os.environ, CLEAN_ENV, clear=True)
        self.env.start()
        self.root = hermetic.make_repo_fixture(prefix="along-drafts-")
        proc.git(["init"], cwd=self.root)
        proc.git(["config", "user.name", "Tester"], cwd=self.root)
        proc.git(["config", "user.email", "tester@example.com"], cwd=self.root)
        proc.git(["config", "commit.gpgSign", "false"], cwd=self.root)
        proc.git(["add", "."], cwd=self.root)
        proc.git(["commit", "-m", "init"], cwd=self.root)

    def tearDown(self):
        self.env.stop()
        shutil.rmtree(self.root, ignore_errors=True)

    def run_cli(self, handler, args):
        out, err = io.StringIO(), io.StringIO()
        with mock.patch.dict(os.environ, {"ALONG_SESSION_ID": SID, "ALONG_SESSION_RUNTIME": "claude"}), \
                contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            try:
                ret = handler(self.root, args)
                code = ret if isinstance(ret, int) else 0
            except SystemExit as exc:
                code = int(exc.code or 0)
            except CommandError as exc:
                code = exc.exit_code
                err.write(str(exc))
        return code, out.getvalue(), err.getvalue()

    def test_create_draft_is_untracked_and_unlisted_on_board(self):
        code, out, err = self.run_cli(along_exec.handle_issue_command, [
            "create", "feat", "untracked-idea", "--draft", "--title", "Untracked Idea",
        ])
        self.assertEqual(code, 0, out + err)
        draft_file = os.path.join(self.root, ".along", ".drafts", "feat--untracked-idea.md")
        self.assertTrue(os.path.isfile(draft_file))

        gi_file = os.path.join(self.root, ".along", ".drafts", ".gitignore")
        self.assertTrue(os.path.isfile(gi_file))
        self.assertEqual(textio.read_text(gi_file).strip(), "*")

        board_txt = textio.read_text(os.path.join(self.root, ".along", "ISSUES.md"))
        self.assertNotIn("untracked-idea", board_txt)

        status_res = proc.git(["status", "--porcelain"], cwd=self.root)
        self.assertEqual([l for l in status_res.lines() if l.strip()], [])

    def test_promote_moves_draft_and_syncs_board_and_rejects_stub(self):
        # 1. Create a draft containing scaffold placeholder
        code, out, err = self.run_cli(along_exec.handle_issue_command, [
            "create", "feat", "stub-idea", "--draft", "--title", "Stub Idea",
        ])
        self.assertEqual(code, 0)
        draft_file = drafts.find_draft(self.root, "stub-idea")
        self.assertIsNotNone(draft_file)

        # Attempt promote with scaffold placeholder -> exits 2
        code, out, err = self.run_cli(along_exec.handle_issue_command, ["promote", "stub-idea"])
        self.assertEqual(code, 2, "Promoting placeholder stub must fail with code 2")
        self.assertIn("placeholder content", err + out)

        # 2. Update draft with non-stub real requirements and criteria
        real_content = """---
protocol: along
protocol_version: "4.8.0"
slug: stub-idea
type: feat
status: open
priority: medium
created: 2026-11-10
updated: 2026-11-10
agent: test
tags: []
blocked_by: []
related: []
---

# Stub Idea

A well-specified feature description.

## Requirements
- REQ-1: System MUST implement feature X.

## Acceptance Criteria
- [ ] Feature X implementation complete
- [ ] Automated tests passing
"""
        textio.write_text(draft_file, real_content)

        # Promote again -> succeeds
        code, out, err = self.run_cli(along_exec.handle_issue_command, ["promote", "stub-idea"])
        self.assertEqual(code, 0, out + err)
        self.assertIn("Promoted draft to", out)

        # Old draft gone, new issue in .along/ISSUES/
        self.assertIsNone(drafts.find_draft(self.root, "stub-idea"))
        promoted_issue = entities.find_issue_by_slug(self.root, "stub-idea")
        self.assertIsNotNone(promoted_issue)
        self.assertTrue(os.path.isfile(promoted_issue["file_path"]))

        # Board is updated
        board_txt = textio.read_text(os.path.join(self.root, ".along", "ISSUES.md"))
        self.assertIn("stub-idea", board_txt)

    def test_along_start_promotes_draft_and_binds(self):
        code, out, err = self.run_cli(along_exec.handle_issue_command, [
            "create", "feat", "start-promote", "--draft", "--title", "Start Promote",
        ])
        self.assertEqual(code, 0)
        draft_file = drafts.find_draft(self.root, "start-promote")
        valid_content = """---
protocol: along
protocol_version: "4.8.0"
slug: start-promote
type: feat
status: open
priority: high
created: 2026-11-10
updated: 2026-11-10
agent: test
tags: []
blocked_by: []
related: []
---

# Start Promote

Detailed description.

## Requirements
- REQ-1: Implementation detail.

## Acceptance Criteria
- [ ] Implementation completed
"""
        textio.write_text(draft_file, valid_content)

        # Start using slug
        code, out, err = self.run_cli(along_exec.handle_start_command, ["start-promote", "--approved"])
        self.assertEqual(code, 0, out + err)
        self.assertIn("Promoted draft to", out)

        issue = entities.find_issue_by_slug(self.root, "start-promote")
        self.assertIsNotNone(issue)
        self.assertEqual(issue["status"], "in-progress")
        self.assertEqual(session.resolve_active_session(self.root, KEY)[0], "start-promote")

    def test_create_refuses_slug_existing_in_drafts(self):
        code, out, err = self.run_cli(along_exec.handle_issue_command, [
            "create", "feat", "existing-draft", "--draft", "--title", "First Draft",
        ])
        self.assertEqual(code, 0)

        # Trying to create a normal issue with same slug
        code, out, err = self.run_cli(along_exec.handle_issue_command, [
            "create", "feat", "existing-draft", "--title", "Normal Issue",
        ])
        self.assertNotEqual(code, 0)
        self.assertIn("already exists", err)

    def test_doctor_reports_stale_draft(self):
        code, out, err = self.run_cli(along_exec.handle_issue_command, [
            "create", "feat", "stale-idea", "--draft", "--title", "Stale Idea",
        ])
        self.assertEqual(code, 0)
        dpath = drafts.find_draft(self.root, "stale-idea")
        # Set mtime to 10 days ago
        ten_days_ago = time.time() - (10 * 86400)
        os.utime(dpath, (ten_days_ago, ten_days_ago))

        code, out, err = self.run_cli(along_exec.handle_doctor_command, [])
        combined = out + err
        self.assertIn("draft(s) older than 7 days in .along/.drafts/: stale-idea", combined)
        self.assertIn("Promote ('along issue promote <slug>') or delete", combined)
