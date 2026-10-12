#!/usr/bin/env python3
"""
tests/test_vision.py - Unit tests for .along/VISION.md integrity.

Verifies:
1. .along/VISION.md contains valid YAML frontmatter with a sources list.
2. No banned stale pre-v2 names appear in .along/VISION.md.
3. Every skill name referenced in .along/VISION.md exists in the skills/ directory.
"""

from __future__ import annotations

import io
import os
import re
import sys
import unittest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPTS_DIR = os.path.join(REPO_ROOT, "scripts")
if SCRIPTS_DIR not in sys.path:
    sys.path.insert(0, SCRIPTS_DIR)

from alongkit import frontmatter

BANNED_STALE_NAMES = [
    ".along/KB/",
    "CONTEXT.md",
    "init-agents",
    "wrap-session",
    "sync-context",
    "sync-issues",
    "sync-decisions",
    "/along-init-kb",
    "/along-search-kb",
    "/along-sync-kb",
    "/along-check-graph",
]


class TestVisionIntegrity(unittest.TestCase):
    """Test suite verifying .along/VISION.md adheres to v4.x requirements."""

    def setUp(self):
        self.vision_path = os.path.join(REPO_ROOT, ".along", "VISION.md")
        self.skills_dir = os.path.join(REPO_ROOT, "skills")
        self.assertTrue(os.path.isfile(self.vision_path), "VISION.md must exist at .along/VISION.md")
        with io.open(self.vision_path, "r", encoding="utf-8") as handle:
            self.vision_text = handle.read()

    def test_vision_frontmatter_and_sources(self):
        """Verify .along/VISION.md contains valid YAML frontmatter with sources list."""
        fm, body = frontmatter.parse(self.vision_text, path=self.vision_path)
        self.assertIsInstance(fm, dict, "Frontmatter must parse to a dictionary")
        self.assertIn("sources", fm, "Frontmatter must contain 'sources' key")
        sources = fm.get("sources")
        self.assertIsInstance(sources, list, "'sources' must be a list")
        self.assertGreater(len(sources), 0, "'sources' list must not be empty")

        for item in sources:
            if isinstance(item, dict):
                src_path = item.get("path")
            elif isinstance(item, str):
                src_path = item
            else:
                self.fail(f"Invalid source entry type: {type(item)}")

            self.assertTrue(bool(src_path), "Source path must be non-empty")
            target_file = os.path.normpath(os.path.join(REPO_ROOT, src_path))
            self.assertTrue(
                os.path.isfile(target_file),
                f"Source file '{src_path}' listed in VISION.md does not exist on disk"
            )

        self.assertGreater(len(body.strip()), 0, "VISION.md body must not be empty")

    def test_no_banned_stale_names(self):
        """Verify no banned stale pre-v2 names appear anywhere in .along/VISION.md."""
        found_banned = []
        for banned in BANNED_STALE_NAMES:
            if banned in self.vision_text:
                found_banned.append(banned)

        self.assertEqual(
            found_banned,
            [],
            f"Banned stale names found in .along/VISION.md: {found_banned}"
        )

    def test_skills_referenced_exist_in_skills_dir(self):
        """Verify every skill name referenced in .along/VISION.md exists in skills/."""
        self.assertTrue(os.path.isdir(self.skills_dir), "skills/ directory must exist")
        actual_skills = {
            name
            for name in os.listdir(self.skills_dir)
            if os.path.isdir(os.path.join(self.skills_dir, name))
        }
        self.assertGreater(len(actual_skills), 0, "skills/ directory must not be empty")

        matches = re.findall(r"(?:/)?(along-[a-z0-9-]+)", self.vision_text)
        referenced_skills = set(matches)
        self.assertGreater(
            len(referenced_skills),
            0,
            "Expected at least one skill referenced in .along/VISION.md"
        )

        unknown_skills = referenced_skills - actual_skills
        self.assertEqual(
            unknown_skills,
            set(),
            f"Skill names referenced in .along/VISION.md do not exist in skills/: {unknown_skills}"
        )


if __name__ == "__main__":
    unittest.main()
