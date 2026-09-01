#!/usr/bin/env python3
"""
tests/test_issue_lifecycle.py - Regression tests for entity front-matter mutation.

Background: `along_exec.py issue done` used `re.sub(r'status:\\s*\\w+', 'status: done')`
over the WHOLE file. Two defects compounded:

1. `\\w+` does not match a hyphen, so the documented normal path
   `status: in-progress` produced the invalid value `status: done-progress`.
2. The mandatory `completed:` field was inserted only if `status:\\s*done\\n` matched
   afterwards, which it never did once the value became `done-progress`. So closing an
   in-progress issue silently dropped a field the protocol declares mandatory.

The substitution was also unanchored, so prose or code samples in the markdown body
containing `status:` were rewritten too.

These tests pin the full lifecycle (open -> in-progress -> done) and body immutability.
"""

import os
import sys
import unittest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPTS_DIR = os.path.join(REPO_ROOT, "scripts")
if SCRIPTS_DIR not in sys.path:
    sys.path.insert(0, SCRIPTS_DIR)

import along_exec as ax

VALID_STATUSES = {"open", "in-progress", "blocked", "done"}

IN_PROGRESS_ISSUE = """---
protocol: along
protocol_version: "2.2.8"
slug: sample-issue
type: bug
status: in-progress
priority: critical
created: 2026-09-01
updated: 2026-09-01
tags: [a, b]
---

# Sample issue

The reviewer must set `status: open` in the body example and it must survive untouched.

- updated: never-touch-this-body-line
"""


class TestFrontmatterFieldUpdate(unittest.TestCase):

    def _fm(self, content):
        block = content.split("---", 2)[1]
        fields = {}
        for line in block.strip().splitlines():
            if ":" in line:
                k, v = line.split(":", 1)
                fields[k.strip()] = v.strip()
        return fields

    def test_01_in_progress_closes_to_valid_status(self):
        """The hyphenated value must not be partially replaced (regression: done-progress)."""
        out = ax.update_frontmatter_fields(
            IN_PROGRESS_ISSUE,
            {"status": "done", "updated": "2026-09-02", "completed": "2026-09-02"},
            place_after={"completed": "status"},
        )
        fields = self._fm(out)

        self.assertEqual(fields["status"], "done")
        self.assertIn(fields["status"], VALID_STATUSES)
        self.assertNotIn("done-progress", out)

    def test_02_mandatory_completed_field_is_inserted_after_status(self):
        out = ax.update_frontmatter_fields(
            IN_PROGRESS_ISSUE,
            {"status": "done", "updated": "2026-09-02", "completed": "2026-09-02"},
            place_after={"completed": "status"},
        )
        fm_lines = [l for l in out.split("---")[1].strip().splitlines() if ":" in l]
        keys = [l.split(":", 1)[0].strip() for l in fm_lines]

        self.assertIn("completed", keys, "protocol requires 'completed' when status is done")
        self.assertEqual(keys[keys.index("status") + 1], "completed")
        self.assertEqual(self._fm(out)["completed"], "2026-09-02")

    def test_03_markdown_body_is_never_rewritten(self):
        out = ax.update_frontmatter_fields(
            IN_PROGRESS_ISSUE,
            {"status": "done", "updated": "2026-09-02", "completed": "2026-09-02"},
            place_after={"completed": "status"},
        )
        body = out.split("---", 2)[2]

        self.assertIn("`status: open` in the body example", body)
        self.assertIn("- updated: never-touch-this-body-line", body)

    def test_04_existing_completed_value_is_replaced_not_duplicated(self):
        closed_once = ax.update_frontmatter_fields(
            IN_PROGRESS_ISSUE,
            {"status": "done", "updated": "2026-09-02", "completed": "2026-09-02"},
            place_after={"completed": "status"},
        )
        closed_twice = ax.update_frontmatter_fields(
            closed_once,
            {"status": "done", "updated": "2026-09-03", "completed": "2026-09-03"},
            place_after={"completed": "status"},
        )
        fm_block = closed_twice.split("---")[1]

        self.assertEqual(fm_block.count("completed:"), 1)
        self.assertEqual(self._fm(closed_twice)["completed"], "2026-09-03")
        self.assertEqual(self._fm(closed_twice)["updated"], "2026-09-03")

    def test_05_other_statuses_close_cleanly(self):
        for status in ("open", "blocked", "in-progress"):
            src = IN_PROGRESS_ISSUE.replace("status: in-progress", f"status: {status}")
            out = ax.update_frontmatter_fields(
                src, {"status": "done", "completed": "2026-09-02"},
                place_after={"completed": "status"},
            )
            self.assertEqual(self._fm(out)["status"], "done", f"failed closing from '{status}'")

    def test_06_crlf_line_endings_are_preserved(self):
        crlf = IN_PROGRESS_ISSUE.replace("\n", "\r\n")
        out = ax.update_frontmatter_fields(
            crlf, {"status": "done", "completed": "2026-09-02"},
            place_after={"completed": "status"},
        )
        fm_block = out.split("---")[1]

        self.assertIn("status: done\r\n", out)
        self.assertIn("completed: 2026-09-02\r\n", out)
        # No bare LF may survive inside the front-matter block.
        self.assertNotIn("\n", fm_block.replace("\r\n", ""))
        self.assertEqual(self._fm(out)["status"], "done")

    def test_06b_utf8_bom_prefixed_entity_still_updates(self):
        """PowerShell redirects and Windows editors emit a BOM; updates must not become a no-op."""
        bom = "\ufeff" + IN_PROGRESS_ISSUE

        self.assertTrue(ax.has_frontmatter(bom), "BOM-prefixed front-matter must be detected")

        out = ax.update_frontmatter_fields(
            bom, {"status": "done", "completed": "2026-09-02"},
            place_after={"completed": "status"},
        )
        self.assertEqual(self._fm(out)["status"], "done")
        self.assertNotIn("\ufeff", out, "BOM must be normalized away (protocol requires BOM-free UTF-8)")

    def test_06c_has_frontmatter_rejects_bodies_without_a_header(self):
        self.assertFalse(ax.has_frontmatter("# Heading\n\nstatus: open\n"))
        self.assertFalse(ax.has_frontmatter("---not a fence\n"))
        self.assertTrue(ax.has_frontmatter("---\nslug: x\n---\n"))

    def test_07_content_without_frontmatter_is_returned_unchanged(self):
        plain = "# Just a heading\n\nstatus: open\n"
        self.assertEqual(ax.update_frontmatter_fields(plain, {"status": "done"}), plain)

    def test_08_unquoted_and_quoted_values_both_update(self):
        src = IN_PROGRESS_ISSUE.replace('protocol_version: "2.2.8"', "protocol_version: 2.2.8")
        out = ax.update_frontmatter_fields(src, {"protocol_version": '"2.2.9"'})
        self.assertEqual(self._fm(out)["protocol_version"], '"2.2.9"')


class TestRepositoryEntityIntegrity(unittest.TestCase):
    """No committed issue may carry a status outside the protocol enum."""

    def test_09_all_issue_statuses_are_valid(self):
        issues_dir = os.path.join(REPO_ROOT, ".along", "ISSUES")
        if not os.path.isdir(issues_dir):
            self.skipTest("No .along/ISSUES/ in this repository")

        violations = []
        for root, _, files in os.walk(issues_dir):
            for f in files:
                if not f.endswith(".md"):
                    continue
                path = os.path.join(root, f)
                with open(path, "r", encoding="utf-8") as fh:
                    text = fh.read()
                if not text.startswith("---"):
                    continue
                for line in text.split("---", 2)[1].strip().splitlines():
                    if line.startswith("status:"):
                        value = line.split(":", 1)[1].strip()
                        if value not in VALID_STATUSES:
                            violations.append(f"{os.path.relpath(path, REPO_ROOT)}: '{value}'")

        self.assertEqual(
            violations, [],
            "Issues carry statuses outside {open, in-progress, blocked, done}:\n" + "\n".join(violations)
        )

    def test_10_done_issues_declare_completed_date(self):
        done_dir = os.path.join(REPO_ROOT, ".along", "ISSUES", "done")
        if not os.path.isdir(done_dir):
            self.skipTest("No .along/ISSUES/done/ in this repository")

        missing = []
        for f in sorted(os.listdir(done_dir)):
            if not f.endswith(".md"):
                continue
            path = os.path.join(done_dir, f)
            with open(path, "r", encoding="utf-8") as fh:
                text = fh.read()
            if not text.startswith("---"):
                continue
            fm = text.split("---", 2)[1]
            if "completed:" not in fm:
                missing.append(f)

        self.assertEqual(
            missing, [],
            "Protocol requires 'completed: YYYY-MM-DD' on issues moved to done/:\n" + "\n".join(missing)
        )


if __name__ == "__main__":
    unittest.main()
