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

The load-bearing invariant is in `TestIssueDoneCommand`: a lifecycle command must never
report success while changing nothing. Unparseable front-matter has to fail loudly.

A leading UTF-8 BOM (`test_06b`) is one specific historical instance of that class, not an
expected input: this repository contains zero BOM-prefixed files, and the engines never
write one. It is covered because Windows PowerShell 5.1 emits a BOM from `Set-Content -Encoding utf8`,
`Out-File -Encoding utf8`, and plain `>` redirection, so a BOM can arrive from tooling even
though the protocol forbids it in committed text. Detecting and rejecting BOMs is the
gate's job, not each engine's; see `[bug--quality-gates-skip-hidden-directories]`.
"""

import os
import sys
import tempfile
import unittest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPTS_DIR = os.path.join(REPO_ROOT, "scripts")
if SCRIPTS_DIR not in sys.path:
    sys.path.insert(0, SCRIPTS_DIR)

import along_exec as ax
from alongkit import frontmatter as fm, proc

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
        """
        A BOM must not silently turn an update into a no-op.

        Not an expected input: the protocol forbids BOMs and this repository has none.
        Covered because Windows PowerShell 5.1 emits one from `Set-Content -Encoding utf8`,
        `Out-File -Encoding utf8`, and `>` redirection, which is how the original defect was
        found. The general guarantee is in `TestIssueDoneCommand`.
        """
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

    def test_08_quoting_is_the_writers_job_not_the_callers(self):
        """
        Callers pass plain values; the writer decides quoting.

        Before the shared front-matter module, the writer emitted `f"{key}: {value}"`
        verbatim, so a caller had to pre-quote anything ambiguous and a title containing
        a colon produced a block no strict YAML reader accepts. Six such files existed in
        this repository. The value now round-trips as the string it was passed.
        """
        src = IN_PROGRESS_ISSUE.replace('protocol_version: "2.2.8"', "protocol_version: 2.2.8")
        out = ax.update_frontmatter_fields(src, {"protocol_version": "2.2.9"})
        self.assertEqual(fm.parse(out)[0]["protocol_version"], "2.2.9")

        # A value that would break the block unquoted is quoted automatically.
        titled = ax.update_frontmatter_fields(src, {"title": "v3.0.0: Global Quality Revision"})
        self.assertEqual(fm.parse(titled)[0]["title"], "v3.0.0: Global Quality Revision")
        self.assertEqual(fm.lint(titled), [], "the emitted block must be valid YAML")


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


class TestIssueDoneCommand(unittest.TestCase):
    """
    End-to-end guarantee: `issue done` must never report success while changing nothing.

    Runs against a temporary repository, never REPO_ROOT, so the suite cannot mutate the
    working tree (see [bug--tests-mutate-working-tree]).
    """

    EXEC = os.path.join(REPO_ROOT, "scripts", "along_exec.py")

    def setUp(self):
        self.repo = tempfile.mkdtemp(prefix="along-lifecycle-")
        self.issues = os.path.join(self.repo, ".along", "ISSUES")
        self.done = os.path.join(self.issues, "done")
        os.makedirs(self.done, exist_ok=True)

    def tearDown(self):
        import shutil
        shutil.rmtree(self.repo, ignore_errors=True)

    def _write(self, name, text, bom=False):
        path = os.path.join(self.issues, name)
        with open(path, "w", encoding="utf-8", newline="") as fh:
            fh.write(("\ufeff" if bom else "") + text)
        return path

    def _run_done(self, slug):
        return proc.run_capture(
            [sys.executable, self.EXEC, "issue", "done", slug], cwd=self.repo)

    def test_11_unparseable_frontmatter_fails_loudly_and_moves_nothing(self):
        src = self._write("task--broken-header.md", "# No front-matter here\n\nstatus: open\n")

        res = self._run_done("broken-header")

        self.assertEqual(res.returncode, 1, f"expected exit 1, got {res.returncode}\n{res.stdout}{res.stderr}")
        self.assertIn("front-matter", (res.stderr or "").lower())
        self.assertTrue(os.path.exists(src), "the issue file must stay where it was")
        self.assertFalse(
            os.path.exists(os.path.join(self.done, "task--broken-header.md")),
            "a file with unparseable front-matter must not be moved to done/",
        )

    def test_12_bom_prefixed_entity_closes_and_reports_normalization(self):
        self._write("task--bom-entity.md", IN_PROGRESS_ISSUE, bom=True)

        res = self._run_done("bom-entity")
        self.assertEqual(res.returncode, 0, f"{res.stdout}{res.stderr}")

        combined = (res.stdout or "") + (res.stderr or "")
        self.assertIn("BOM", combined, "normalizing a BOM is a byte-level change and must be reported")

        moved = os.path.join(self.done, "task--bom-entity.md")
        self.assertTrue(os.path.exists(moved))
        with open(moved, "rb") as fh:
            raw = fh.read()
        self.assertFalse(raw.startswith(b"\xef\xbb\xbf"), "output must be BOM-free")

        text = raw.decode("utf-8")
        fm = text.split("---", 2)[1]
        self.assertIn("status: done", fm)
        self.assertIn("completed:", fm)


if __name__ == "__main__":
    unittest.main()
