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
from alongkit import entities, frontmatter as fm, proc

VALID_STATUSES = {"open", "in-progress", "blocked", "done", "superseded", "cancelled", "duplicate"}

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
            "Issues carry statuses outside declared enum:\n" + "\n".join(violations)
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

    def test_13_issue_sync_emits_portable_relative_links(self):
        self._write("feat--first.md", IN_PROGRESS_ISSUE)
        self._write(os.path.join("done", "bug--second.md"), IN_PROGRESS_ISSUE.replace("status: in-progress", "status: done"))

        res = proc.run_capture([sys.executable, self.EXEC, "issue", "sync"], cwd=self.repo)
        self.assertEqual(res.returncode, 0, f"{res.stdout}{res.stderr}")

        board_path = os.path.join(self.repo, ".along", "ISSUES.md")
        self.assertTrue(os.path.isfile(board_path))
        with open(board_path, "r", encoding="utf-8") as f:
            board = f.read()

        self.assertIn("- [ ] `(feat)` [first](ISSUES/feat--first.md)", board)
        self.assertIn("- [x] `(bug)` [second](ISSUES/done/bug--second.md)", board)
        self.assertNotIn("file://", board)

    def test_14_issue_done_updates_sibling_relative_links(self):
        body_with_links = (
            "---\n"
            "protocol: along\n"
            "slug: sample-issue\n"
            "type: feat\n"
            "status: in-progress\n"
            "---\n\n"
            "# Sample\n\n"
            "See [Other](feat--other.md) and [Dot](./bug--dot.md) and [Already](../task--pre.md).\n"
        )
        self._write("feat--sample-issue.md", body_with_links)

        res = self._run_done("sample-issue")
        self.assertEqual(res.returncode, 0, f"{res.stdout}{res.stderr}")

        moved = os.path.join(self.done, "feat--sample-issue.md")
        self.assertTrue(os.path.isfile(moved))
        with open(moved, "r", encoding="utf-8") as f:
            content = f.read()

        self.assertIn("[Other](../feat--other.md)", content)
        self.assertIn("[Dot](../bug--dot.md)", content)
        self.assertIn("[Already](../task--pre.md)", content)
        self.assertNotIn("[Other](feat--other.md)", content)
        self.assertNotIn("[Dot](./bug--dot.md)", content)

    def test_14b_issue_done_with_status_and_references(self):
        self._write("feat--sample-issue.md", IN_PROGRESS_ISSUE)
        res = proc.run_capture([
            sys.executable, self.EXEC, "issue", "done", "sample-issue",
            "--status", "superseded",
            "--superseded-by", "feat--new-design",
        ], cwd=self.repo)
        self.assertEqual(res.returncode, 0, f"failed: {res.stdout}\n{res.stderr}")
        moved = os.path.join(self.done, "feat--sample-issue.md")
        self.assertTrue(os.path.exists(moved))
        with open(moved, "r", encoding="utf-8") as f:
            data, _ = fm.parse(f.read())
        self.assertEqual(data["status"], "superseded")
        self.assertEqual(data["superseded_by"], "feat--new-design")
        self.assertIsNotNone(data.get("completed"))


class TestIssueCreateCommand(unittest.TestCase):
    """
    End-to-end tests for `along_exec.py issue create`.

    Verifies runtime agent detection, milestone validation, enum validation,
    slug shape enforcement, duplicate rejection, and protocol_version stamping.
    Hermetic: runs against a temporary repository.
    """

    EXEC = os.path.join(REPO_ROOT, "scripts", "along_exec.py")

    def setUp(self):
        self.repo = tempfile.mkdtemp(prefix="along-issue-create-")
        self.along_dir = os.path.join(self.repo, ".along")
        self.issues = os.path.join(self.along_dir, "ISSUES")
        self.done = os.path.join(self.issues, "done")
        self.milestones = os.path.join(self.along_dir, "MILESTONES")
        os.makedirs(self.done, exist_ok=True)
        os.makedirs(self.milestones, exist_ok=True)
        with open(os.path.join(self.along_dir, "ISSUES.md"), "w", encoding="utf-8") as f:
            f.write("# Active Issues\n\n## Active\n\n## Backlog\n\n## Done (recent)\n")

    def tearDown(self):
        import shutil
        shutil.rmtree(self.repo, ignore_errors=True)

    def _run_create(self, *args, env_override=None):
        env = os.environ.copy()
        if env_override:
            for k, v in env_override.items():
                if v is None:
                    env.pop(k, None)
                else:
                    env[k] = v
        cmd = [sys.executable, self.EXEC, "issue", "create"] + list(args)
        return proc.run_capture(cmd, cwd=self.repo, env=env)

    def _read_issue(self, filename):
        path = os.path.join(self.issues, filename)
        with open(path, "r", encoding="utf-8") as f:
            content = f.read()
        fm_parsed, _ = fm.parse(content, path=path)
        return fm_parsed, content

    def test_15_create_explicit_agent(self):
        res = self._run_create("feat", "my-feature", "--title", "My Feature", "--agent", "claude-code")
        self.assertEqual(res.returncode, 0, f"{res.stdout}\n{res.stderr}")
        data, _ = self._read_issue("feat--my-feature.md")
        self.assertEqual(data.get("agent"), "claude-code")

    def test_16_create_inferred_agent_from_env(self):
        clean_env = {
            "ANTIGRAVITY_AGENT": None,
            "ANTIGRAVITY_CONVERSATION_ID": None,
            "ANTIGRAVITY_PROJECT_ID": None,
            "CLAUDE_CODE": None,
            "CLAUDE_PROJECT_DIR": None,
            "CLAUDE_CONVERSATION_ID": None,
            "ANTHROPIC_CLI": None,
            "CODEX_CLI": None,
            "OPENAI_CODEX": None,
            "OPENCODE_CLI": None,
            "OPENCODE_AGENT": None,
            "AGENT": None,
            "ALONG_AGENT": "test-agent",
        }
        res = self._run_create("bug", "fix-thing", env_override=clean_env)
        self.assertEqual(res.returncode, 0, f"{res.stdout}\n{res.stderr}")
        data, _ = self._read_issue("bug--fix-thing.md")
        self.assertEqual(data.get("agent"), "test-agent")

    def test_17_create_fallback_agent_unknown(self):
        clean_env = {
            k: None for k in os.environ if any(x in k for x in ("ANTIGRAVITY", "CLAUDE", "ANTHROPIC", "CODEX", "OPENCODE", "AGENT"))
        }
        res = self._run_create("task", "clean-task", env_override=clean_env)
        self.assertEqual(res.returncode, 0, f"{res.stdout}\n{res.stderr}")
        data, _ = self._read_issue("task--clean-task.md")
        self.assertEqual(data.get("agent"), "unknown")

    def test_18_create_stamps_protocol_version(self):
        res = self._run_create("feat", "new-feature")
        self.assertEqual(res.returncode, 0, f"{res.stdout}\n{res.stderr}")
        data, content = self._read_issue("feat--new-feature.md")
        self.assertEqual(data.get("protocol"), "along")
        self.assertIn("protocol_version:", content)
        self.assertTrue(bool(data.get("protocol_version")))

    def test_19_create_invalid_type_rejected(self):
        res = self._run_create("feature", "invalid-type")
        self.assertEqual(res.returncode, 1)
        self.assertIn("invalid issue type", res.stderr.lower())
        self.assertIn("feat", res.stderr)

    def test_20_create_invalid_priority_rejected(self):
        res = self._run_create("feat", "bad-priority", "--priority", "hihg")
        self.assertEqual(res.returncode, 1)
        self.assertIn("invalid priority", res.stderr.lower())
        self.assertIn("critical", res.stderr)

    def test_21_create_invalid_slug_shape_rejected(self):
        for bad_slug in ("single", "UpperCase", "under_score", "double--hyphen", "one-two-three-four-five-six"):
            res = self._run_create("feat", bad_slug)
            self.assertEqual(res.returncode, 1, f"Expected rejection for '{bad_slug}'")
            self.assertIn("invalid issue slug", res.stderr.lower())

    def test_22_create_duplicate_slug_rejected(self):
        res1 = self._run_create("feat", "duplicate-test")
        self.assertEqual(res1.returncode, 0)
        res2 = self._run_create("bug", "duplicate-test")
        self.assertEqual(res2.returncode, 1)
        self.assertIn("already exists", res2.stderr.lower())

    def test_23_create_explicit_dangling_milestone_refused(self):
        res = self._run_create("feat", "milestone-test", "--milestone", "non-existent-milestone")
        self.assertEqual(res.returncode, 1)
        self.assertIn("does not exist", res.stderr.lower())

    def test_24_create_auto_stamps_single_in_progress_milestone(self):
        # 0 in-progress milestones: milestone should not be stamped
        res = self._run_create("feat", "zero-milestones")
        self.assertEqual(res.returncode, 0)
        data, content = self._read_issue("feat--zero-milestones.md")
        self.assertNotIn("milestone:", content)

        # Create 1 in-progress milestone
        m_file = os.path.join(self.milestones, "v1.0.0-release.md")
        with open(m_file, "w", encoding="utf-8") as f:
            f.write("---\nprotocol: along\nslug: v1.0.0-release\ntitle: v1.0.0\nstatus: in-progress\n---\n# M\n")

        res2 = self._run_create("feat", "one-milestone")
        self.assertEqual(res2.returncode, 0)
        data2, content2 = self._read_issue("feat--one-milestone.md")
        self.assertEqual(data2.get("milestone"), "v1.0.0-release")

    def test_24b_type_inference_notice(self):
        res = self._run_create("feat", "fix-login-crash", "--title", "Fix login crash bug")
        self.assertEqual(res.returncode, 0)
        self.assertIn("matches bug keywords", res.stdout)


class TestDoctorEntitiesCommand(unittest.TestCase):
    """
    End-to-end tests for `along_exec.py doctor --entities`.

    Verifies detection of dangling references, invalid enums, and clean reports.
    """

    EXEC = os.path.join(REPO_ROOT, "scripts", "along_exec.py")

    def setUp(self):
        self.repo = tempfile.mkdtemp(prefix="along-doctor-")
        self.along_dir = os.path.join(self.repo, ".along")
        self.issues = os.path.join(self.along_dir, "ISSUES")
        self.milestones = os.path.join(self.along_dir, "MILESTONES")
        os.makedirs(self.issues, exist_ok=True)
        os.makedirs(self.milestones, exist_ok=True)

    def tearDown(self):
        import shutil
        shutil.rmtree(self.repo, ignore_errors=True)

    def _run_doctor(self):
        cmd = [sys.executable, self.EXEC, "doctor", "--entities"]
        return proc.run_capture(cmd, cwd=self.repo)

    def test_25_doctor_detects_dangling_parent(self):
        issue_path = os.path.join(self.issues, "bug--child-issue.md")
        with open(issue_path, "w", encoding="utf-8") as f:
            f.write(
                "---\n"
                "protocol: along\n"
                "slug: child-issue\n"
                "type: bug\n"
                "status: open\n"
                "priority: high\n"
                "created: 2026-09-01\n"
                "updated: 2026-09-01\n"
                "parent: feat--non-existent-parent\n"
                "---\n"
                "# Child\n"
            )
        res = self._run_doctor()
        self.assertEqual(res.returncode, 1)
        self.assertIn("dangling parent", res.stdout.lower() + res.stderr.lower())

    def test_26_doctor_detects_invalid_enum(self):
        issue_path = os.path.join(self.issues, "bug--bad-enum.md")
        with open(issue_path, "w", encoding="utf-8") as f:
            f.write(
                "---\n"
                "protocol: along\n"
                "slug: bad-enum\n"
                "type: bug\n"
                "status: invalid-status\n"
                "priority: high\n"
                "created: 2026-09-01\n"
                "updated: 2026-09-01\n"
                "---\n"
                "# Bad enum\n"
            )
        res = self._run_doctor()
        self.assertEqual(res.returncode, 1)
        self.assertIn("invalid status", res.stdout.lower() + res.stderr.lower())

    def test_27_doctor_clean_fixture_passes(self):
        issue_path = os.path.join(self.issues, "feat--good-issue.md")
        with open(issue_path, "w", encoding="utf-8") as f:
            f.write(
                "---\n"
                "protocol: along\n"
                "slug: good-issue\n"
                "type: feat\n"
                "status: open\n"
                "priority: medium\n"
                "created: 2026-09-01\n"
                "updated: 2026-09-01\n"
                "---\n"
                "# Good\n"
            )
        res = self._run_doctor()
        self.assertEqual(res.returncode, 0)
        self.assertIn("0 errors, 0 warnings", res.stdout)

    def test_28_doctor_detects_dangling_superseded_by(self):
        issue_path = os.path.join(self.issues, "feat--old-one.md")
        with open(issue_path, "w", encoding="utf-8") as f:
            f.write(
                "---\n"
                "protocol: along\n"
                "slug: old-one\n"
                "type: feat\n"
                "status: superseded\n"
                "priority: low\n"
                "created: 2026-09-01\n"
                "updated: 2026-09-01\n"
                "completed: 2026-09-01\n"
                "superseded_by: feat--ghost-replacement\n"
                "---\n"
                "# Old One\n"
            )
        res = self._run_doctor()
        self.assertEqual(res.returncode, 1)
        self.assertIn("dangling superseded_by", res.stdout.lower() + res.stderr.lower())

    def test_29_doctor_detects_dangling_duplicate_of(self):
        issue_path = os.path.join(self.issues, "feat--dup-one.md")
        with open(issue_path, "w", encoding="utf-8") as f:
            f.write(
                "---\n"
                "protocol: along\n"
                "slug: dup-one\n"
                "type: feat\n"
                "status: duplicate\n"
                "priority: low\n"
                "created: 2026-09-01\n"
                "updated: 2026-09-01\n"
                "completed: 2026-09-01\n"
                "duplicate_of: feat--ghost-primary\n"
                "---\n"
                "# Duplicate One\n"
            )
        res = self._run_doctor()
        self.assertEqual(res.returncode, 1)
        self.assertIn("dangling duplicate_of", res.stdout.lower() + res.stderr.lower())


if __name__ == "__main__":
    unittest.main()


