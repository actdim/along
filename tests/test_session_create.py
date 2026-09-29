#!/usr/bin/env python3
"""
tests/test_session_create.py - `along session create` emits safe YAML and no false claims.

Regression suite for [bug--session-create-unsafe-yaml]: the front-matter was built with
f-strings (an unquoted `summary` broke on `:` or `#`), `branch: main` was hard-coded, and the
body asserted "Automated tests verified and passing" without any evidence.
All runs target throwaway fixtures.
"""

from __future__ import annotations

import glob
import os
import sys
import unittest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPTS_DIR = os.path.join(REPO_ROOT, "scripts")
if SCRIPTS_DIR not in sys.path:
    sys.path.insert(0, SCRIPTS_DIR)

from alongkit import bootstrap
bootstrap.ensure_deps()

from alongkit import frontmatter, proc, textio
import hermetic

ALONG_EXEC = os.path.join(SCRIPTS_DIR, "along_exec.py")

ADVERSARIAL_SUMMARIES = (
    "Fixed: the parser # and comments",
    "- starts with a dash",
    "* starts with a star",
    "[not a list] {not a map}",
    "quotes \" and ' inside",
    "non-ASCII " + chr(0x0438) + chr(0x043C) + chr(0x044F) + " text",
    "yes",
    "3.10",
)


def _create(fixture, slug, summary, *extra):
    return proc.run_capture(
        [sys.executable, ALONG_EXEC, "session", "create", slug, "--summary", summary,
         "--agent", "test-suite", *extra],
        cwd=fixture, env=hermetic.isolated_home_env(), trip_on_anomaly=False,
    )


def _read_session(fixture, slug):
    matches = glob.glob(os.path.join(fixture, ".along", "SESSIONS", "*", f"*--{slug}.md"))
    if len(matches) != 1:
        raise AssertionError(f"expected one session file for {slug}, found {matches}")
    return frontmatter.parse(textio.read_text(matches[0]))


class TestSessionCreate(unittest.TestCase):
    def test_adversarial_summaries_round_trip(self):
        with hermetic.repo_fixture(prefix="along-session-yaml-") as fixture:
            for idx, summary in enumerate(ADVERSARIAL_SUMMARIES):
                slug = f"yaml-case-{idx}"
                with self.subTest(summary=summary):
                    res = _create(fixture, slug, summary, "--decisions", "ADR-2026-09-01--x,ADR-2026-09-02--y")
                    self.assertEqual(res.returncode, 0, res.stderr)
                    fm, _ = _read_session(fixture, slug)
                    self.assertEqual(fm["summary"], summary)
                    self.assertEqual(fm["decisions"], ["ADR-2026-09-01--x", "ADR-2026-09-02--y"])
                    self.assertEqual(fm["protocol_version"].count("."), 2)

    def test_no_unverified_test_claim_and_no_hardcoded_branch(self):
        with hermetic.repo_fixture(prefix="along-session-claims-") as fixture:
            res = _create(fixture, "no-claims", "plain summary")
            self.assertEqual(res.returncode, 0, res.stderr)
            fm, body = _read_session(fixture, "no-claims")
            self.assertNotIn("verified and passing", body)
            self.assertIn("Tests:", body)
            # The fixture is not a git repository: no branch or commit may be invented.
            self.assertNotIn("branch", fm)
            self.assertNotIn("commit", fm)

    def test_branch_and_commit_come_from_git(self):
        with hermetic.repo_fixture(prefix="along-session-git-") as fixture:
            git = ["git", "-c", "user.email=t@example.com", "-c", "user.name=t"]
            for args in (["init", "-q", "-b", "feature-x"], ["add", "-A"], ["commit", "-q", "-m", "init"]):
                r = proc.run_capture(git + args, cwd=fixture, trip_on_anomaly=False)
                self.assertEqual(r.returncode, 0, r.stderr)
            head = proc.run_capture(["git", "rev-parse", "--short", "HEAD"], cwd=fixture,
                                    trip_on_anomaly=False).stdout.strip()
            res = _create(fixture, "git-facts", "summary")
            self.assertEqual(res.returncode, 0, res.stderr)
            fm, _ = _read_session(fixture, "git-facts")
            self.assertEqual(fm["branch"], "feature-x")
            self.assertEqual(fm["commit"], head)

            res = _create(fixture, "explicit-commit", "summary", "--commit", "abc1234")
            self.assertEqual(res.returncode, 0, res.stderr)
            fm, _ = _read_session(fixture, "explicit-commit")
            self.assertEqual(fm["commit"], "abc1234")


if __name__ == "__main__":
    unittest.main(verbosity=2)
