#!/usr/bin/env python3
"""
tests/test_sanitizer.py - the typography sanitizer must not destroy what it reads.

Every case here corresponds to a way the previous implementation lost content, from
`[bug--typography-sanitizer-destroys-non-utf8-files]`:

- it read with `errors="ignore"` and then overwrote, so a cp1251 file lost its
  undecodable bytes permanently;
- it wrote with `newline="\\n"`, so a `.ps1` file that `.gitattributes` declares
  `eol=crlf` came back as LF;
- it rewrote `.json` / `.yaml` / `.toml` unconditionally, so a localized resource
  bundle was corrupted as a side effect of a commit;
- it had no mode but "rewrite now", and ran that way before every commit and release;
- it used `glob`, which never matches a leading dot, so a byte order mark inside
  `.along/**` was invisible to the only tool meant to remove it.

Banned characters are built with `chr()` on purpose: this file is itself scanned by
the sanitizer it tests, and a literal glyph here would be a finding.

Fixtures are throwaway temporary trees. Nothing here points a writing engine at the
repository that contains it - see `tests/hermetic.py`.
"""

from __future__ import annotations

import io
import json
import os
import shutil
import sys
import tempfile
import unittest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPTS_DIR = os.path.join(REPO_ROOT, "scripts")
if SCRIPTS_DIR not in sys.path:
    sys.path.insert(0, SCRIPTS_DIR)

from alongkit import gates, proc, sanitizer

EM_DASH = chr(0x2014)
NBSP = chr(0x00A0)
BOM = chr(0xFEFF)
LEFT_GUILLEMET = chr(0x00AB)
RIGHT_GUILLEMET = chr(0x00BB)

SANITIZER_ENGINE = os.path.join(SCRIPTS_DIR, "sanitize_typography.py")


def write_bytes(root, rel, payload):
    """Create `<root>/<rel>` with exactly `payload`, creating parents as needed."""
    path = os.path.join(root, *rel.split("/"))
    parent = os.path.dirname(path)
    if parent:
        os.makedirs(parent, exist_ok=True)
    with io.open(path, "wb") as handle:
        handle.write(payload)
    return path


def read_bytes(path):
    with io.open(path, "rb") as handle:
        return handle.read()


class SanitizerFixtureCase(unittest.TestCase):
    """A temporary tree carrying one instance of every hazard."""

    def setUp(self):
        self.root = tempfile.mkdtemp(prefix="along-sanitize-")
        self.addCleanup(shutil.rmtree, self.root, True)

        # Valid UTF-8 markdown with a banned character on line 3: the only kind of
        # file a default run should ever rewrite.
        self.prose = write_bytes(
            self.root, "docs/topic--sample.md",
            ("# Sample\n\nA note" + EM_DASH + "with a dash.\n").encode("utf-8"))

        # Not valid UTF-8: cp1251 Cyrillic. The old tool decoded this with
        # errors="ignore" and wrote the remains back.
        self.legacy = write_bytes(self.root, "legacy/notes.md",
                                  b"# \xcf\xf0\xe8\xec\xe5\xf7\xe0\xed\xe8\xe5\n")
        self.legacy_bytes = read_bytes(self.legacy)

        # CRLF PowerShell, which .gitattributes declares eol=crlf.
        self.script = write_bytes(
            self.root, "install.ps1",
            ("# Installer" + EM_DASH + "notes\r\nWrite-Host 'hi'\r\n").encode("utf-8"))

        # Localized resource bundle: guillemets here are content, not typography.
        self.locale = write_bytes(
            self.root, "locales/fr.json",
            json.dumps({"quote": LEFT_GUILLEMET + "bonjour" + RIGHT_GUILLEMET},
                       ensure_ascii=False).encode("utf-8"))
        self.locale_bytes = read_bytes(self.locale)

        # An ordinary data file: in scope only when data files are opted into.
        self.data = write_bytes(self.root, "config.json",
                                ('{"label": "a' + EM_DASH + 'b"}\n').encode("utf-8"))
        self.data_bytes = read_bytes(self.data)

        # A byte order mark inside a hidden directory: unreachable by glob.
        self.hidden = write_bytes(self.root, ".along/ISSUES/task--x.md",
                                  (BOM + "# Task\n").encode("utf-8"))

    def finding_paths(self, report):
        return {finding.path for finding in report.findings}


class TestScopePolicy(SanitizerFixtureCase):

    def test_default_scope_is_prose_and_source_only(self):
        report = sanitizer.run(self.root, mode=sanitizer.Mode.CHECK)
        paths = self.finding_paths(report)
        self.assertIn("docs/topic--sample.md", paths)
        self.assertIn("install.ps1", paths)
        self.assertNotIn("config.json", paths)
        self.assertNotIn("locales/fr.json", paths)

    def test_data_files_are_opt_in(self):
        report = sanitizer.run(self.root, mode=sanitizer.Mode.CHECK, include_data=True)
        self.assertIn("config.json", self.finding_paths(report))

    def test_a_data_file_is_untouched_by_a_default_write(self):
        sanitizer.run(self.root, mode=sanitizer.Mode.WRITE)
        self.assertEqual(read_bytes(self.data), self.data_bytes)

    def test_localized_directories_are_never_scanned(self):
        report = sanitizer.run(self.root, mode=sanitizer.Mode.WRITE, include_data=True)
        self.assertNotIn("locales/fr.json", self.finding_paths(report))
        self.assertEqual(read_bytes(self.locale), self.locale_bytes,
                         "a translated string is content, not typography to repair")

    def test_hidden_directories_are_scanned(self):
        report = sanitizer.run(self.root, mode=sanitizer.Mode.CHECK)
        self.assertIn(".along/ISSUES/task--x.md", self.finding_paths(report))

    def test_an_extra_suffix_can_be_added(self):
        write_bytes(self.root, "notes.txt", ("x" + EM_DASH + "y\n").encode("utf-8"))
        default = sanitizer.run(self.root, mode=sanitizer.Mode.CHECK)
        self.assertNotIn("notes.txt", self.finding_paths(default))
        widened = sanitizer.run(self.root, mode=sanitizer.Mode.CHECK,
                                extra_suffixes=["txt"])
        self.assertIn("notes.txt", self.finding_paths(widened))

    def test_an_unknown_mode_is_rejected(self):
        with self.assertRaises(ValueError):
            sanitizer.run(self.root, mode="rewrite-everything")


class TestNonDestructiveReads(SanitizerFixtureCase):

    def test_a_non_utf8_file_is_skipped_and_left_byte_identical(self):
        report = sanitizer.run(self.root, mode=sanitizer.Mode.WRITE)
        skipped = {s.path: s.reason for s in report.skipped}
        self.assertIn("legacy/notes.md", skipped)
        self.assertIn("UTF-8", skipped["legacy/notes.md"])
        self.assertEqual(read_bytes(self.legacy), self.legacy_bytes)

    def test_a_skipped_file_never_appears_as_a_finding(self):
        report = sanitizer.run(self.root, mode=sanitizer.Mode.CHECK)
        self.assertNotIn("legacy/notes.md", self.finding_paths(report))


class TestLineEndingsSurvive(SanitizerFixtureCase):

    def test_crlf_stays_crlf_after_a_rewrite(self):
        sanitizer.run(self.root, mode=sanitizer.Mode.WRITE)
        payload = read_bytes(self.script)
        self.assertEqual(payload.count(b"\n"), payload.count(b"\r\n"),
                         "every newline must still be preceded by a carriage return")
        self.assertEqual(payload.count(b"\r\n"), 2)
        self.assertNotIn(EM_DASH.encode("utf-8"), payload)

    def test_lf_stays_lf(self):
        sanitizer.run(self.root, mode=sanitizer.Mode.WRITE)
        self.assertNotIn(b"\r", read_bytes(self.prose))


class TestModes(SanitizerFixtureCase):

    def test_check_writes_nothing_and_fails(self):
        before = read_bytes(self.prose)
        report = sanitizer.run(self.root, mode=sanitizer.Mode.CHECK)
        self.assertFalse(report.clean)
        self.assertEqual(report.exit_code, 1)
        self.assertEqual(report.files_written, [])
        self.assertEqual(read_bytes(self.prose), before)

    def test_dry_run_writes_nothing_and_succeeds(self):
        before = read_bytes(self.prose)
        report = sanitizer.run(self.root, mode=sanitizer.Mode.DRY_RUN)
        self.assertFalse(report.clean)
        self.assertEqual(report.exit_code, 0)
        self.assertEqual(read_bytes(self.prose), before)

    def test_write_applies_and_then_the_tree_is_clean(self):
        first = sanitizer.run(self.root, mode=sanitizer.Mode.WRITE)
        self.assertIn("docs/topic--sample.md", first.files_written)
        second = sanitizer.run(self.root, mode=sanitizer.Mode.CHECK)
        self.assertTrue(second.clean, sanitizer.format_report(second))
        with io.open(self.prose, encoding="utf-8") as handle:
            self.assertNotIn(EM_DASH, handle.read())


class TestBomReporting(SanitizerFixtureCase):

    def test_a_bom_is_reported_by_path(self):
        report = sanitizer.run(self.root, mode=sanitizer.Mode.CHECK)
        self.assertIn(".along/ISSUES/task--x.md", report.boms_removed)

    def test_a_bom_is_removed_on_write_and_named_in_the_output(self):
        report = sanitizer.run(self.root, mode=sanitizer.Mode.WRITE)
        self.assertFalse(read_bytes(self.hidden).startswith(b"\xef\xbb\xbf"))
        self.assertIn("byte order mark", sanitizer.format_report(report))


class TestExclusions(SanitizerFixtureCase):

    def test_an_explicit_exclude_pattern_is_honored(self):
        report = sanitizer.run(self.root, mode=sanitizer.Mode.CHECK,
                               excludes=["docs/*.md"])
        self.assertNotIn("docs/topic--sample.md", self.finding_paths(report))

    def test_a_directory_pattern_excludes_its_contents(self):
        report = sanitizer.run(self.root, mode=sanitizer.Mode.CHECK, excludes=["docs/"])
        self.assertNotIn("docs/topic--sample.md", self.finding_paths(report))

    def test_the_ignore_file_is_read(self):
        write_bytes(self.root, sanitizer.IGNORE_FILE,
                    b"# fixtures are not ours to rewrite\ndocs/\n")
        report = sanitizer.run(self.root, mode=sanitizer.Mode.CHECK)
        self.assertNotIn("docs/topic--sample.md", self.finding_paths(report))

    def test_the_ignore_file_can_be_disabled(self):
        write_bytes(self.root, sanitizer.IGNORE_FILE, b"docs/\n")
        report = sanitizer.run(self.root, mode=sanitizer.Mode.CHECK,
                               use_ignore_file=False)
        self.assertIn("docs/topic--sample.md", self.finding_paths(report))


class TestMachineReadableSummary(SanitizerFixtureCase):

    def test_the_report_carries_file_line_and_replacement_counts(self):
        report = sanitizer.run(self.root, mode=sanitizer.Mode.CHECK)
        payload = report.as_dict()
        self.assertEqual(payload["mode"], "check")
        self.assertGreater(payload["files_scanned"], 0)
        self.assertEqual(payload["total_replacements"],
                         sum(f["replacements"] for f in payload["findings"]))
        sample = next(f for f in payload["findings"]
                      if f["path"] == "docs/topic--sample.md")
        self.assertEqual(sample["lines"], [3])
        self.assertEqual(sample["counts"], {"em dash": 1})
        self.assertTrue(json.dumps(payload), "the summary must be JSON-serializable")

    def test_line_numbers_point_at_the_offending_line(self):
        write_bytes(self.root, "notes.md",
                    ("one\ntwo\nthree" + NBSP + "here\n").encode("utf-8"))
        report = sanitizer.run(self.root, mode=sanitizer.Mode.CHECK)
        finding = next(f for f in report.findings if f.path == "notes.md")
        self.assertEqual(finding.lines, [3])
        self.assertEqual(finding.counts, {"non-breaking space": 1})


class TestEngineCommandLine(SanitizerFixtureCase):
    """The CLI contract: check by default, JSON on stdout, logs on stderr."""

    def _run(self, *args):
        return proc.run_capture([sys.executable, SANITIZER_ENGINE, self.root, *args])

    def test_default_is_check_and_exits_non_zero_without_writing(self):
        before = read_bytes(self.prose)
        result = self._run()
        self.assertEqual(result.returncode, 1, result.stderr)
        self.assertEqual(read_bytes(self.prose), before)

    def test_dry_run_exits_zero_without_writing(self):
        before = read_bytes(self.prose)
        result = self._run("--dry-run")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(read_bytes(self.prose), before)

    def test_write_applies_and_reports_the_skipped_file(self):
        result = self._run("--write")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("legacy/notes.md", result.stderr)
        self.assertEqual(read_bytes(self.legacy), self.legacy_bytes)

    def test_json_goes_to_stdout_and_prose_to_stderr(self):
        result = self._run("--json")
        payload = json.loads(result.stdout)
        self.assertEqual(payload["mode"], "check")
        self.assertIn("docs/topic--sample.md",
                      [f["path"] for f in payload["findings"]])
        self.assertNotIn("{", result.stderr)

    def test_an_unknown_option_is_a_usage_error(self):
        self.assertEqual(self._run("--rewrite-everything").returncode, 2)

    def test_a_flag_missing_its_value_is_a_usage_error(self):
        self.assertEqual(self._run("--exclude").returncode, 2)

    def test_help_exits_zero(self):
        result = proc.run_capture([sys.executable, SANITIZER_ENGINE, "--help"])
        self.assertEqual(result.returncode, 0)
        self.assertIn("--write", result.stdout)


class TestGateBehaviour(SanitizerFixtureCase):
    """REQ-6: an automated path verifies; it does not rewrite without being told to."""

    def test_the_gate_fails_and_writes_nothing(self):
        before = read_bytes(self.prose)
        self.assertFalse(gates.typography_gate(self.root, "Test Gate"))
        self.assertEqual(read_bytes(self.prose), before)

    def test_the_gate_repairs_only_with_allow_fix(self):
        self.assertTrue(gates.typography_gate(self.root, "Test Gate", allow_fix=True))
        self.assertTrue(gates.typography_gate(self.root, "Test Gate"))

    def test_run_sanitizer_defaults_to_check(self):
        before = read_bytes(self.prose)
        report = gates.run_sanitizer(self.root, verbose=False)
        self.assertEqual(report.mode, sanitizer.Mode.CHECK)
        self.assertEqual(read_bytes(self.prose), before)


class TestCallersDoNotParseStdout(unittest.TestCase):
    """REQ-5: the count line the commit engine grepped for is gone and must stay gone."""

    def test_no_engine_greps_the_sanitizer_output(self):
        offenders = []
        for name in sorted(os.listdir(SCRIPTS_DIR)):
            if not name.endswith(".py"):
                continue
            with io.open(os.path.join(SCRIPTS_DIR, name), encoding="utf-8") as handle:
                if "Total files sanitized" in handle.read():
                    offenders.append(name)
        self.assertEqual(offenders, [],
                         "consume alongkit.sanitizer.Report, not printed text")

    def test_the_automated_paths_use_the_gate(self):
        for name in ("along_commit.py", "along_version_bump.py"):
            with io.open(os.path.join(SCRIPTS_DIR, name), encoding="utf-8") as handle:
                body = handle.read()
            self.assertIn("gates.typography_gate", body, name)
            self.assertIn("--fix-typography", body, name)


if __name__ == "__main__":
    unittest.main()
