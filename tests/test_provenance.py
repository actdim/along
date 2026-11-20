#!/usr/bin/env python3
"""
tests/test_provenance.py - Doc provenance drift CLI and commit/CI gates.

Covers REQ-1 through REQ-8 of feat--provenance-drift-gate:
- SHA-256 LF-normalized content hashing.
- Source-to-topic mapping with subproject context awareness.
- along kb-sync --accept-drift <topic> [<source>...] with mandatory review flags.
- along kb-sync --drift-diff <topic>.
- Commit-time and CI provenance_drift gates.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
import unittest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPTS_DIR = os.path.join(REPO_ROOT, "scripts")
if SCRIPTS_DIR not in sys.path:
    sys.path.insert(0, SCRIPTS_DIR)

from alongkit import bootstrap, gitgates, provenance, textio
bootstrap.ensure_deps()


class TestProvenanceCore(unittest.TestCase):
    def test_compute_content_hash_normalizes_crlf(self):
        crlf = "line 1\r\nline 2\r\n"
        lf = "line 1\nline 2\n"
        self.assertEqual(provenance.compute_content_hash(crlf), provenance.compute_content_hash(lf))

    def test_accept_round_trip(self):
        tmp = tempfile.mkdtemp(prefix="along-prov-accept-")
        try:
            docs_dir = os.path.join(tmp, "docs")
            os.makedirs(docs_dir, exist_ok=True)
            src_file = os.path.join(tmp, "src.py")
            textio.write_text(src_file, "print('hello v2')\n")
            new_hash = provenance.compute_content_hash("print('hello v2')\n")

            topic_file = os.path.join(docs_dir, "topic--sample.md")
            original_content = (
                "---\n"
                "title: Sample Topic\n"
                "# Key comment\n"
                "sources:\n"
                "  - path: src.py\n"
                "    hash: 0000000000000000000000000000000000000000000000000000000000000000\n"
                "tags: [alpha, beta]\n"
                "---\n\n"
                "# Sample Body\n\n"
                "Unchanged body paragraph.\n"
            )
            textio.write_text(topic_file, original_content)

            topic_rel, accepted = provenance.accept(tmp, "topic--sample.md", ["src.py"])
            self.assertEqual(topic_rel, "docs/topic--sample.md")
            self.assertEqual(len(accepted), 1)
            self.assertEqual(accepted[0][0], "src.py")
            self.assertEqual(accepted[0][2], new_hash)

            updated = textio.read_text(topic_file, strict=False)
            self.assertIn(new_hash, updated)
            self.assertIn("# Key comment", updated)
            self.assertIn("tags: [alpha, beta]", updated)
            self.assertIn("Unchanged body paragraph.", updated)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)


class TestProvenanceGitGates(unittest.TestCase):
    def setUp(self):
        self.root = tempfile.mkdtemp(prefix="along-prov-git-")
        self.git = lambda *a: subprocess.run(
            ["git", *a], cwd=self.root, capture_output=True, text=True,
            encoding="utf-8", check=True
        )
        self.git("init", "-q")
        self.git("config", "user.email", "test@example.com")
        self.git("config", "user.name", "Test")

        # Create basic directory structure
        os.makedirs(os.path.join(self.root, "docs"), exist_ok=True)
        os.makedirs(os.path.join(self.root, "src"), exist_ok=True)
        os.makedirs(os.path.join(self.root, ".along"), exist_ok=True)

        self.src_file = os.path.join(self.root, "src", "app.py")
        textio.write_text(self.src_file, "def app(): return 1\n")
        initial_hash = provenance.compute_content_hash("def app(): return 1\n")

        self.topic_file = os.path.join(self.root, "docs", "topic--app.md")
        topic_text = (
            "---\n"
            "title: Application\n"
            "sources:\n"
            "  - path: src/app.py\n"
            f"    hash: {initial_hash}\n"
            "---\n\n"
            "# Application\n"
        )
        textio.write_text(self.topic_file, topic_text)

        # Baseline commit
        self.git("add", "-A")
        self.git("commit", "-q", "-m", "chore: initial commit")

    def tearDown(self):
        shutil.rmtree(self.root, ignore_errors=True)

    def test_staged_source_edit_without_topic_update_fails_pre_commit(self):
        # Modify src/app.py and stage it
        textio.write_text(self.src_file, "def app(): return 2\n")
        self.git("add", "src/app.py")

        violations = gitgates.check_pre_commit(self.root)
        prov_violations = [v for v in violations if v.gate == "provenance_drift"]
        self.assertEqual(len(prov_violations), 1)
        self.assertEqual(prov_violations[0].location, "docs/topic--app.md")
        self.assertIn("src/app.py", prov_violations[0].message)

    def test_staged_source_edit_with_accepted_topic_passes_pre_commit(self):
        # Modify src/app.py and stage it
        textio.write_text(self.src_file, "def app(): return 2\n")
        self.git("add", "src/app.py")

        # Accept drift into topic
        provenance.accept(self.root, "docs/topic--app.md", ["src/app.py"])
        self.git("add", "docs/topic--app.md")

        violations = gitgates.check_pre_commit(self.root)
        prov_violations = [v for v in violations if v.gate == "provenance_drift"]
        self.assertEqual(prov_violations, [])

    def test_untracked_source_edit_passes_gate(self):
        # Modify an untracked file (not listed in any topic's sources)
        untracked = os.path.join(self.root, "src", "other.py")
        textio.write_text(untracked, "print('other')\n")
        self.git("add", "src/other.py")

        violations = gitgates.check_pre_commit(self.root)
        prov_violations = [v for v in violations if v.gate == "provenance_drift"]
        self.assertEqual(prov_violations, [])

    def test_preexisting_drift_ignored_when_source_untouched(self):
        # Modify src/app.py on disk WITHOUT staging it
        textio.write_text(self.src_file, "def app(): return 99\n")

        # Edit an unrelated file and stage it
        unrelated = os.path.join(self.root, "README.md")
        textio.write_text(unrelated, "# Readme\n")
        self.git("add", "README.md")

        violations = gitgates.check_pre_commit(self.root)
        prov_violations = [v for v in violations if v.gate == "provenance_drift"]
        self.assertEqual(prov_violations, [])

    def test_deleting_tracked_source_fails_gate(self):
        self.git("rm", "src/app.py")
        violations = gitgates.check_pre_commit(self.root)
        prov_violations = [v for v in violations if v.gate == "provenance_drift"]
        self.assertEqual(len(prov_violations), 1)
        self.assertIn("deleted", prov_violations[0].message)

    def test_ci_range_detects_drift(self):
        # Commit a change to src/app.py without updating topic
        textio.write_text(self.src_file, "def app(): return 3\n")
        self.git("add", "src/app.py")
        self.git("commit", "-q", "-m", "feat: app change (refs #my-issue)")

        violations = gitgates.check_ci(self.root, "HEAD^..HEAD")
        prov_violations = [v for v in violations if v.gate == "provenance_drift"]
        self.assertEqual(len(prov_violations), 1)


class TestProvenanceCli(unittest.TestCase):
    def setUp(self):
        self.root = tempfile.mkdtemp(prefix="along-prov-cli-")
        self.git = lambda *a: subprocess.run(
            ["git", *a], cwd=self.root, capture_output=True, text=True,
            encoding="utf-8", check=True
        )
        self.git("init", "-q")
        self.git("config", "user.email", "test@example.com")
        self.git("config", "user.name", "Test")

        os.makedirs(os.path.join(self.root, "docs"), exist_ok=True)
        os.makedirs(os.path.join(self.root, "src"), exist_ok=True)

        self.src_file = os.path.join(self.root, "src", "mod.py")
        textio.write_text(self.src_file, "# initial code\n")
        initial_hash = provenance.compute_content_hash("# initial code\n")

        self.topic_file = os.path.join(self.root, "docs", "topic--mod.md")
        topic_text = (
            "---\n"
            "title: Module Documentation\n"
            "sources:\n"
            "  - path: src/mod.py\n"
            f"    hash: {initial_hash}\n"
            "---\n\n"
            "# Module Documentation\n"
        )
        textio.write_text(self.topic_file, topic_text)
        self.git("add", "-A")
        self.git("commit", "-q", "-m", "chore: initial")

    def tearDown(self):
        shutil.rmtree(self.root, ignore_errors=True)

    def run_kb_sync(self, args: list[str]) -> subprocess.CompletedProcess:
        cmd = [sys.executable, os.path.join(SCRIPTS_DIR, "along_kb_sync.py"), self.root, *args]
        return subprocess.run(cmd, cwd=self.root, capture_output=True, text=True, encoding="utf-8")

    def test_accept_drift_flag_validation(self):
        # Neither --reviewed nor --no-doc-impact
        res = self.run_kb_sync(["--accept-drift", "topic--mod"])
        self.assertEqual(res.returncode, 2)
        self.assertIn("requires exactly one", res.stderr)

        # Both --reviewed and --no-doc-impact
        res = self.run_kb_sync(["--accept-drift", "topic--mod", "--reviewed", "--no-doc-impact", "no reason"])
        self.assertEqual(res.returncode, 2)
        self.assertIn("requires exactly one", res.stderr)

    def test_accept_drift_reviewed_flow(self):
        # Drift the source
        textio.write_text(self.src_file, "# updated code\n")

        res = self.run_kb_sync(["--accept-drift", "topic--mod", "--reviewed"])
        self.assertEqual(res.returncode, 0)
        self.assertIn("Doc-Provenance: docs/topic--mod.md; src/mod.py; reviewed", res.stdout)

        # Assert hash in topic is updated
        updated_topic = textio.read_text(self.topic_file, strict=False)
        new_hash = provenance.compute_content_hash("# updated code\n")
        self.assertIn(new_hash, updated_topic)

    def test_accept_drift_no_doc_impact_flow(self):
        textio.write_text(self.src_file, "# refactored code\n")

        res = self.run_kb_sync(["--accept-drift", "topic--mod", "--no-doc-impact", "Internal refactor only"])
        self.assertEqual(res.returncode, 0)
        self.assertIn("Doc-Provenance: docs/topic--mod.md; src/mod.py; no-doc-impact: Internal refactor only", res.stdout)

    def test_drift_diff_flow(self):
        textio.write_text(self.src_file, "# modified code\n")

        res = self.run_kb_sync(["--drift-diff", "topic--mod"])
        self.assertEqual(res.returncode, 0)
        self.assertIn("=== Source: src/mod.py ===", res.stdout)
        self.assertIn("Recording commit:", res.stdout)
        self.assertIn("+", res.stdout)


if __name__ == "__main__":
    unittest.main()
