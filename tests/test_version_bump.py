#!/usr/bin/env python3
"""
tests/test_version_bump.py - Unit tests for along_version_bump CLI behavior, error reporting, and rollback.
"""

from __future__ import annotations

import io
import os
import re
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import MagicMock, patch

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPTS_DIR = os.path.join(REPO_ROOT, "scripts")
if SCRIPTS_DIR not in sys.path:
    sys.path.insert(0, SCRIPTS_DIR)

from along_version_bump import (
    ReleaseAborted,
    _build_parser,
    _normalize_argv,
    deduplicate_log_entries,
    detect_and_bump_project,
    report_rollback,
)
from alongkit import transaction, version as along_version


class TestVersionBumpCli(unittest.TestCase):
    """Test CLI behavior and rollback reporting for along_version_bump."""

    def test_cli_help_exits_cleanly(self):
        script_path = os.path.join(SCRIPTS_DIR, "along_version_bump.py")
        res = subprocess.run(
            [sys.executable, script_path, "--help"],
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(res.returncode, 0)
        self.assertIn("usage: python along_version_bump.py", res.stdout.lower())

    def test_report_rollback_untouched_working_tree(self):
        mock_tx = MagicMock()
        mock_tx.rollback.return_value = []
        mock_tx.unrestorable = []

        buf = io.StringIO()
        with patch("sys.stderr", buf):
            report_rollback(mock_tx, "precondition failed")

        output = buf.getvalue()
        self.assertIn("[Abort] Release aborted: precondition failed", output)
        self.assertIn("Nothing was written; the working tree is untouched", output)

    def test_report_rollback_restores_mutated_files(self):
        mock_tx = MagicMock()
        mock_tx.rollback.return_value = ["package.json", ".along/VERSION"]
        mock_tx.unrestorable = []

        buf = io.StringIO()
        with patch("sys.stderr", buf):
            report_rollback(mock_tx, "gate error")

        output = buf.getvalue()
        self.assertIn("[Abort] Release aborted: gate error", output)
        self.assertIn("Rolled back 2 file(s):", output)
        self.assertIn("package.json", output)


class TestDeduplicateLogEntries(unittest.TestCase):
    """Test changelog log entry deduplication and prefix normalization."""

    def test_deduplicates_by_issue_reference_and_prefers_scope(self):
        entries = [
            "fix: Fix webdev session browser creation (refs #webdev-session-create-browser-helper)",
            "fix(webdev): session browser creation, thread affinity, and doctor checks (refs #webdev-session-create-browser-helper)",
            "feat: Standalone feature without refs",
            "fix: fix(opencode): guard undefined output in shell hooks (refs #opencode-shell-env-runner-fix)",
            "fix(opencode): guard undefined output in shell hooks and align runner CLI contract (refs #opencode-shell-env-runner-fix)",
        ]
        deduped = deduplicate_log_entries(entries)
        self.assertEqual(len(deduped), 3)
        self.assertEqual(
            deduped[0],
            "fix(webdev): session browser creation, thread affinity, and doctor checks (refs #webdev-session-create-browser-helper)",
        )
        self.assertEqual(deduped[1], "feat: Standalone feature without refs")
        self.assertEqual(
            deduped[2],
            "fix(opencode): guard undefined output in shell hooks and align runner CLI contract (refs #opencode-shell-env-runner-fix)",
        )

    def test_type_tier_beats_scoped_docs_or_chore(self):
        entries = [
            "docs(adr): record decision for per-clone merge driver (refs #merge-driver)",
            "feat: preventive git auto-merge protection (refs #merge-driver)",
            "fix: fix stop gate false positive (refs #stop-gate)",
            "chore(along): sync projections after stop gate fix (refs #stop-gate)",
            "test(unit): add extra tests for config (refs #config-refactor)",
            "refactor: simplify config loader (refs #config-refactor)",
            "chore(sync): update index after doc sweep (refs #doc-sweep)",
            "docs: align setup guide with current CLI (refs #doc-sweep)",
        ]
        deduped = deduplicate_log_entries(entries)
        self.assertEqual(
            deduped,
            [
                "feat: preventive git auto-merge protection (refs #merge-driver)",
                "fix: fix stop gate false positive (refs #stop-gate)",
                "refactor: simplify config loader (refs #config-refactor)",
                "docs: align setup guide with current CLI (refs #doc-sweep)",
            ],
        )

    def test_same_tier_prefers_scope_then_longer_subject(self):
        entries = [
            "feat: short feature (refs #perf-slug)",
            "perf(cache): fast (refs #perf-slug)",
            "feat(ui): short (refs #ui-slug)",
            "fix(ui): much longer descriptive summary (refs #ui-slug)",
            "chore: same len aaa (refs #tie-slug)",
            "test: same len bbb (refs #tie-slug)",
        ]
        deduped = deduplicate_log_entries(entries)
        self.assertEqual(
            deduped,
            [
                "perf(cache): fast (refs #perf-slug)",
                "fix(ui): much longer descriptive summary (refs #ui-slug)",
                "chore: same len aaa (refs #tie-slug)",
            ],
        )

    def test_normalizes_double_prefixes_across_types(self):
        entries = [
            "feat: feat: opencode runtime hooks integration (refs #opencode-runtime)",
            "chore: fix(hooks)!: strict guard (refs #strict-guard)",
        ]
        deduped = deduplicate_log_entries(entries)
        self.assertEqual(
            deduped,
            [
                "feat: opencode runtime hooks integration (refs #opencode-runtime)",
                "fix(hooks)!: strict guard (refs #strict-guard)",
            ],
        )

    def test_changelog_sections_have_no_duplicate_issue_refs(self):
        changelog_path = os.path.join(REPO_ROOT, "CHANGELOG.md")
        with open(changelog_path, "r", encoding="utf-8") as handle:
            content = handle.read()

        sections = re.split(r"(?m)^(?=## v\d+\.\d+\.\d+)", content)
        checked_v460_plus = []
        for section in sections[1:]:
            lines = section.splitlines()
            header = lines[0]
            ver_match = re.match(r"^## v(\d+)\.(\d+)\.(\d+)\b", header)
            self.assertIsNotNone(ver_match, f"Malformed section header: {header}")
            ver_tuple = tuple(int(p) for p in ver_match.groups())
            if ver_tuple >= (4, 6, 0):
                checked_v460_plus.append(header)

            seen_slugs = {}
            for line in lines[1:]:
                if not line.startswith("- "):
                    continue
                entry = line[2:]
                self.assertIsNone(
                    re.match(
                        r"^(?:feat|fix|perf|refactor|debt|docs|test|chore|style|ci|build|task):\s*"
                        r"(?:feat|fix|perf|refactor|debt|docs|test|chore|style|ci|build|task)(?:\([^)]+\))?!?:",
                        entry,
                        re.I,
                    ),
                    f"Double prefix remaining in {header}: {entry}",
                )
                ref_match = re.search(r"\((?:refs\s+)?#([a-z0-9\-]+)(?=[,\s)])", entry, re.I)
                if ref_match:
                    slug = ref_match.group(1).lower()
                    self.assertNotIn(
                        slug,
                        seen_slugs,
                        f"Duplicate (refs #{slug}) in {header}: {entry} vs {seen_slugs.get(slug)}",
                    )
                    seen_slugs[slug] = entry

        self.assertTrue(
            any(h.startswith("## v4.6.0 ") for h in checked_v460_plus),
            "Expected v4.6.0 section in CHANGELOG.md",
        )
        self.assertGreaterEqual(len(checked_v460_plus), 8)


def _write_fixture_file(root, rel_path, content):
    full = os.path.join(root, rel_path)
    os.makedirs(os.path.dirname(full), exist_ok=True)
    with open(full, "w", encoding="utf-8", newline="\n") as f:
        f.write(content)
    return full


def _read_fixture_file(root, rel_path):
    with open(os.path.join(root, rel_path), "r", encoding="utf-8") as f:
        return f.read()


class TestDecoupledDevRepoBump(unittest.TestCase):
    """Hermetic tests for decoupled toolchain vs protocol bumps in Along dev repos."""

    def _make_dev_repo(self, root, toolchain_v="5.1.0", protocol_v="4.9.1"):
        _write_fixture_file(root, "scripts/along_update.py", "# stub\n")
        _write_fixture_file(
            root,
            "scripts/alongkit/version.py",
            f'CURRENT_PROTOCOL_VERSION = "{protocol_v}"\nCURRENT_VERSION = "{toolchain_v}"\n',
        )
        _write_fixture_file(root, "skills/along-init/protocol.md", f"# ALONG-PROTOCOL v{protocol_v}\n")
        _write_fixture_file(root, "AGENTS.md", f"# ALONG-PROTOCOL v{protocol_v}\n")
        _write_fixture_file(
            root,
            "README.md",
            f"# ActDim Along (v{toolchain_v})\n\nUses `ALONG-PROTOCOL v{protocol_v}`.\n",
        )
        _write_fixture_file(
            root,
            "llms-full.txt",
            f"# ActDim Along (v{toolchain_v}) - Full\nALONG-PROTOCOL v{protocol_v}\n",
        )
        _write_fixture_file(root, "package.json", f'{{\n  "version": "{toolchain_v}"\n}}\n')
        _write_fixture_file(root, "packages/dashboard-ui/package.json", f'{{\n  "version": "{toolchain_v}"\n}}\n')
        _write_fixture_file(root, ".along/.protocol-version", f"{protocol_v}\n")
        _write_fixture_file(root, ".along/VISION.md", f'---\nprotocol_version: "{protocol_v}"\n---\n# Vision\n')
        _write_fixture_file(root, "docs/topic--workflow.md", f"# Workflow\nALONG-PROTOCOL v{protocol_v}\n")

    def test_toolchain_bump_does_not_mutate_protocol_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            self._make_dev_repo(tmp, toolchain_v="5.1.0", protocol_v="4.9.1")
            tx = transaction.FileTransaction(tmp, "test-toolchain")
            new_v = detect_and_bump_project(tmp, "patch", tx)
            tx.commit()

            self.assertEqual(new_v, "5.1.1")
            version_py = _read_fixture_file(tmp, "scripts/alongkit/version.py")
            self.assertIn('CURRENT_VERSION = "5.1.1"', version_py)
            self.assertIn('CURRENT_PROTOCOL_VERSION = "4.9.1"', version_py)
            self.assertIn('"version": "5.1.1"', _read_fixture_file(tmp, "package.json"))
            self.assertIn('"version": "5.1.1"', _read_fixture_file(tmp, "packages/dashboard-ui/package.json"))
            readme = _read_fixture_file(tmp, "README.md")
            self.assertIn("# ActDim Along (v5.1.1)", readme)
            self.assertIn("ALONG-PROTOCOL v4.9.1", readme)
            llms_full = _read_fixture_file(tmp, "llms-full.txt")
            self.assertIn("# ActDim Along (v5.1.1)", llms_full)
            self.assertIn("ALONG-PROTOCOL v4.9.1", llms_full)
            self.assertEqual(_read_fixture_file(tmp, ".along/.protocol-version").strip(), "4.9.1")
            self.assertIn("# ALONG-PROTOCOL v4.9.1", _read_fixture_file(tmp, "AGENTS.md"))
            self.assertIn('protocol_version: "4.9.1"', _read_fixture_file(tmp, ".along/VISION.md"))
            self.assertIn("ALONG-PROTOCOL v4.9.1", _read_fixture_file(tmp, "docs/topic--workflow.md"))

    def test_protocol_bump_does_not_mutate_toolchain_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            self._make_dev_repo(tmp, toolchain_v="5.1.0", protocol_v="4.9.1")
            tx = transaction.FileTransaction(tmp, "test-protocol")
            new_pv = detect_and_bump_project(tmp, None, tx, protocol_bump="minor")
            tx.commit()

            self.assertEqual(new_pv, "4.10.0")
            version_py = _read_fixture_file(tmp, "scripts/alongkit/version.py")
            self.assertIn('CURRENT_PROTOCOL_VERSION = "4.10.0"', version_py)
            self.assertIn('CURRENT_VERSION = "5.1.0"', version_py)
            self.assertIn('"version": "5.1.0"', _read_fixture_file(tmp, "package.json"))
            readme = _read_fixture_file(tmp, "README.md")
            self.assertIn("# ActDim Along (v5.1.0)", readme)
            self.assertIn("ALONG-PROTOCOL v4.10.0", readme)
            llms_full = _read_fixture_file(tmp, "llms-full.txt")
            self.assertIn("# ActDim Along (v5.1.0)", llms_full)
            self.assertIn("ALONG-PROTOCOL v4.10.0", llms_full)
            self.assertEqual(_read_fixture_file(tmp, ".along/.protocol-version").strip(), "4.10.0")
            self.assertIn("# ALONG-PROTOCOL v4.10.0", _read_fixture_file(tmp, "AGENTS.md"))
            self.assertIn("# ALONG-PROTOCOL v4.10.0", _read_fixture_file(tmp, "skills/along-init/protocol.md"))
            self.assertIn('protocol_version: "4.10.0"', _read_fixture_file(tmp, ".along/VISION.md"))
            self.assertIn("ALONG-PROTOCOL v4.10.0", _read_fixture_file(tmp, "docs/topic--workflow.md"))

    def test_argparse_preserves_combined_flags_and_protocol(self):
        parser = _build_parser()
        args = parser.parse_args(_normalize_argv(["minor", "--protocol", "patch", "-cp", "--carry-over", "m1"]))
        self.assertEqual(args.bump_arg, "minor")
        self.assertEqual(args.protocol_bump, "patch")
        self.assertTrue(args.commit)
        self.assertTrue(args.push)
        self.assertEqual(args.carry_over, "m1")

    def test_is_protocol_supported_range(self):
        self.assertTrue(along_version.is_protocol_supported(along_version.MIN_SUPPORTED_PROTOCOL_VERSION))
        self.assertTrue(along_version.is_protocol_supported(along_version.CURRENT_PROTOCOL_VERSION))
        self.assertFalse(along_version.is_protocol_supported("4.7.9"))
        self.assertFalse(along_version.is_protocol_supported("99.0.0"))
        self.assertFalse(along_version.is_protocol_supported(""))
        self.assertFalse(along_version.is_protocol_supported("invalid"))


if __name__ == "__main__":
    unittest.main()
