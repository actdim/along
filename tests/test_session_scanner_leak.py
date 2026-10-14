#!/usr/bin/env python3
"""
tests/test_session_scanner_leak.py - Unit tests for reserved session directories exclusion.

Regression suite for [bug--session-scanner-prompts-dir-leak]:
Internal directories under `.along/.session/` (such as `bindings/` and `prompts/`)
must never leak into session scanners, closeout readiness reports, active blackboards,
or orphan blackboard checks.
"""

from __future__ import annotations

import json
import os
import shutil
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

from alongkit import closeout, lifecycle, repo, session, textio
import along_exec

CLEAN_ENV = {k: v for k, v in os.environ.items() if k not in session.SESSION_ENV_VARS}


class TestSessionScannerLeak(unittest.TestCase):
    """Hermetic unit tests verifying exclusion of reserved internal session directories."""

    def setUp(self):
        self.env = mock.patch.dict(os.environ, CLEAN_ENV, clear=True)
        self.env.start()
        self.root = tempfile.mkdtemp(prefix="along-scanner-leak-")
        os.makedirs(os.path.join(self.root, ".git"), exist_ok=True)
        os.makedirs(os.path.join(self.root, ".along", "ISSUES"), exist_ok=True)
        self.session_dir = os.path.join(self.root, ".along", ".session")
        os.makedirs(os.path.join(self.session_dir, session.BINDINGS_DIRNAME), exist_ok=True)
        os.makedirs(os.path.join(self.session_dir, session.PROMPTS_DIRNAME), exist_ok=True)

    def tearDown(self):
        self.env.stop()
        shutil.rmtree(self.root, ignore_errors=True)

    def test_reserved_session_dirs_constant(self):
        """REQ-1: RESERVED_SESSION_DIRS contains BINDINGS_DIRNAME and PROMPTS_DIRNAME."""
        self.assertIsInstance(session.RESERVED_SESSION_DIRS, frozenset)
        self.assertIn(session.BINDINGS_DIRNAME, session.RESERVED_SESSION_DIRS)
        self.assertIn(session.PROMPTS_DIRNAME, session.RESERVED_SESSION_DIRS)
        self.assertIn("bindings", session.RESERVED_SESSION_DIRS)
        self.assertIn("prompts", session.RESERVED_SESSION_DIRS)

    def test_blackboard_slugs_ignores_reserved_dirs(self):
        """REQ-2: closeout._blackboard_slugs ignores reserved directories."""
        dummy_prompt_file = os.path.join(self.session_dir, session.PROMPTS_DIRNAME, "test--sess.json")
        textio.write_text(dummy_prompt_file, '{"timestamp": "2026-10-14T10:00:00Z"}\n')

        dummy_binding_file = os.path.join(self.session_dir, session.BINDINGS_DIRNAME, "test--sess.json")
        textio.write_text(dummy_binding_file, '{"slug": "test-task"}\n')

        # Only reserved directories exist
        self.assertEqual(closeout._blackboard_slugs(self.root), [])

        # Add a real blackboard directory
        real_bb = os.path.join(self.session_dir, "real-task")
        os.makedirs(real_bb, exist_ok=True)
        self.assertEqual(closeout._blackboard_slugs(self.root), ["real-task"])

    def test_in_progress_slugs_ignores_reserved_dirs(self):
        """REQ-3: session.in_progress_slugs ignores reserved directories."""
        # Even if someone accidentally creates a state.json inside prompts/
        fake_state = os.path.join(self.session_dir, session.PROMPTS_DIRNAME, "state.json")
        textio.write_text(fake_state, '{"status": "in-progress"}\n')

        self.assertEqual(session.in_progress_slugs(self.root), [])

        # Add an actual in-progress blackboard
        session.init_session(self.root, "task-active")
        self.assertEqual(session.in_progress_slugs(self.root), ["task-active"])

    def test_orphan_blackboards_ignores_reserved_dirs(self):
        """REQ-4: lifecycle.orphan_blackboards ignores reserved directories."""
        dummy_prompt = os.path.join(self.session_dir, session.PROMPTS_DIRNAME, "claude--s1.json")
        textio.write_text(dummy_prompt, '{"ts": "2026-10-14T10:00:00Z"}\n')

        orphans = lifecycle.orphan_blackboards(self.root)
        self.assertEqual(orphans, [])

        # Add an unbound blackboard with no issue file
        ghost_bb = os.path.join(self.session_dir, "ghost-task")
        os.makedirs(ghost_bb, exist_ok=True)
        orphans = lifecycle.orphan_blackboards(self.root)
        self.assertEqual(len(orphans), 1)
        self.assertEqual(orphans[0][0], "ghost-task")
        self.assertIn("issue missing", orphans[0][1])

    def test_closeout_status_outputs_zero_entries_when_only_reserved_dirs_exist(self):
        """Acceptance Criteria: along session list has 0 items with only bindings/ and prompts/."""
        status = closeout.closeout_status(self.root)
        self.assertEqual(status["items"], [])

        formatted = closeout.format_closeout_status(status)
        self.assertNotIn("prompts [blocked]", formatted)
        self.assertNotIn("bindings [blocked]", formatted)


if __name__ == "__main__":
    unittest.main(verbosity=2)
