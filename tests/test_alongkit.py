#!/usr/bin/env python3
"""
tests/test_alongkit.py - Unit tests for the shared implementation in scripts/alongkit/.

Before this package the engines were twelve standalone programs: `find_repo_root` existed
in five divergent copies, front-matter parsing in four, and `subprocess.run` was called at
25+ sites with no shared convention. Coverage was concentrated in end-to-end engine tests,
so the primitives themselves were never exercised directly and a defect in one copy was
invisible until an engine misbehaved.

These tests pin the primitives, plus three structural guarantees that keep the duplication
from coming back: no helper name is defined twice, the dependency list has one home, and an
engine still runs from a flat directory copy with no package install.
"""

import ast
import io
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

from alongkit import bootstrap, entities, markdown, proc, repo, semver, textio, typography
from alongkit import frontmatter as fm

NL = "\n"
CRLF = "\r\n"

BLOCK_LIST_ENTITY = NL.join([
    "---",
    "protocol: along",
    "protocol_version: \"2.2.8\"",
    "slug: sample",
    "# a comment that carries intent",
    "tags:",
    "  - protocol",
    "  - retrieval",
    "status: open",
    "custom_field_no_engine_knows: keep me",
    "---",
    "",
    "# Body",
    "",
    "Prose that mentions `status: done` must survive untouched.",
    "",
])


class TestFrontmatterReading(unittest.TestCase):
    def test_block_sequence_is_read_not_dropped(self):
        """The defect that motivated the module: a block list parsed to an empty string."""
        fields, _ = fm.parse(BLOCK_LIST_ENTITY)
        self.assertEqual(fields["tags"], ["protocol", "retrieval"])

    def test_flow_sequence_and_nested_mapping(self):
        source = NL.join([
            "---",
            "items: [{ id: 1, text: hello, verified: false }, { id: 2, text: 'a, b' }]",
            "nested:",
            "  a: 1",
            "  b: [x, y]",
            "---",
            "",
            "# Body",
        ])
        fields, _ = fm.parse(source)
        self.assertEqual(fields["items"][0], {"id": 1, "text": "hello", "verified": False})
        self.assertEqual(fields["items"][1]["text"], "a, b")
        self.assertEqual(fields["nested"], {"a": 1, "b": ["x", "y"]})

    def test_documented_checklist_schema_is_representable(self):
        """AGENTS.md documents `items: [{ id, text, verified: bool }]` for CHECKLISTS."""
        payload = {"protocol": "along", "slug": "pre-commit",
                   "items": [{"id": 1, "text": "tests pass", "verified": False}]}
        document = fm.render(payload, "# Pre-commit")
        fields, _ = fm.parse(document)
        self.assertEqual(fields["items"], payload["items"])

    def test_iso_date_stays_a_string(self):
        fields, _ = fm.parse("---\ncreated: 2026-09-01\n---\n\n# B\n")
        self.assertEqual(fields["created"], "2026-09-01")
        self.assertIsInstance(fields["created"], str)

    def test_invalid_yaml_raises_with_a_line_number(self):
        broken = "---\ntitle: v1.0.0: Initial Protocol\n---\n\n# B\n"
        with self.assertRaises(fm.FrontmatterError) as caught:
            fm.parse(broken, path="milestone.md")
        self.assertEqual(caught.exception.line, 2)
        self.assertIn("milestone.md:2", str(caught.exception))

    def test_try_parse_reports_instead_of_raising(self):
        fields, body, error = fm.try_parse("---\ntitle: a: b\n---\n\n# B\n")
        self.assertEqual(fields, {})
        self.assertIsNotNone(error)
        self.assertIn("# B", body)

    def test_document_without_frontmatter_is_not_an_error(self):
        fields, body = fm.parse("# Just a heading\n\nstatus: open\n")
        self.assertEqual(fields, {})
        self.assertTrue(body.startswith("# Just a heading"))
        self.assertFalse(fm.has_frontmatter(body))

    def test_lint_reports_a_block_no_strict_reader_accepts(self):
        self.assertEqual(fm.lint(BLOCK_LIST_ENTITY), [])
        self.assertEqual(len(fm.lint("---\nsummary: a: b\n---\n\n# B\n")), 1)


class TestFrontmatterWriting(unittest.TestCase):
    def test_editing_one_key_preserves_everything_else(self):
        out = fm.update(BLOCK_LIST_ENTITY, {"status": "done"})
        self.assertIn("# a comment that carries intent", out)
        self.assertIn("  - protocol", out, "block style must survive")
        self.assertIn("custom_field_no_engine_knows: keep me", out)
        self.assertIn("`status: done` must survive untouched", out)
        fields, _ = fm.parse(out)
        self.assertEqual(fields["status"], "done")
        self.assertEqual(fields["tags"], ["protocol", "retrieval"])

    def test_key_order_is_preserved(self):
        before = list(fm.parse(BLOCK_LIST_ENTITY)[0].keys())
        after = list(fm.parse(fm.update(BLOCK_LIST_ENTITY, {"status": "done"}))[0].keys())
        self.assertEqual(before, after)

    def test_insertion_honours_the_anchor(self):
        out = fm.update(BLOCK_LIST_ENTITY, {"completed": "2026-09-02"},
                        place_after={"completed": "status"})
        keys = list(fm.parse(out)[0].keys())
        self.assertEqual(keys[keys.index("status") + 1], "completed")

    def test_removal_deletes_only_the_named_key(self):
        seeded = fm.update(BLOCK_LIST_ENTITY, {"completed": "2026-09-02"})
        out = fm.update(seeded, {}, remove=["completed"])
        self.assertNotIn("completed", fm.parse(out)[0])
        self.assertEqual(fm.parse(out)[0]["tags"], ["protocol", "retrieval"])

    def test_a_noop_edit_is_byte_identical(self):
        """The load-bearing safety property: reading and writing back changes nothing."""
        self.assertEqual(fm.update(BLOCK_LIST_ENTITY, {}), BLOCK_LIST_ENTITY)

    def test_crlf_line_endings_are_preserved(self):
        source = BLOCK_LIST_ENTITY.replace(NL, CRLF)
        out = fm.update(source, {"status": "done"})
        block = fm.split(out).raw
        self.assertIn("status: done", out)
        self.assertNotIn(NL, block.replace(CRLF, ""), "no bare LF may survive in the block")

    def test_bom_is_removed_and_the_edit_still_applies(self):
        out = fm.update(fm.BOM + BLOCK_LIST_ENTITY, {"status": "done"})
        self.assertFalse(out.startswith(fm.BOM))
        self.assertEqual(fm.parse(out)[0]["status"], "done")

    def test_content_without_frontmatter_is_returned_unchanged(self):
        plain = "# Heading\n\nstatus: open\n"
        self.assertEqual(fm.update(plain, {"status": "done"}), plain)

    def test_quoting_is_applied_where_yaml_requires_it(self):
        out = fm.update(BLOCK_LIST_ENTITY, {"title": "v3.0.0: Global Quality Revision"})
        self.assertEqual(fm.parse(out)[0]["title"], "v3.0.0: Global Quality Revision")
        self.assertEqual(fm.lint(out), [])

    def test_dates_are_emitted_unquoted(self):
        out = fm.update(BLOCK_LIST_ENTITY, {"completed": "2026-09-02"})
        self.assertIn("completed: 2026-09-02", out)

    def test_quoted_helper_forces_quotes(self):
        out = fm.update(BLOCK_LIST_ENTITY, {"protocol_version": fm.quoted("3.0")})
        self.assertIn('protocol_version: "3.0"', out)
        self.assertEqual(fm.parse(out)[0]["protocol_version"], "3.0")

    def test_writing_refuses_an_unparseable_block(self):
        with self.assertRaises(fm.FrontmatterError):
            fm.update("---\nsummary: a: b\n---\n\n# B\n", {"status": "done"})

    def test_render_output_reparses_to_the_input(self):
        payload = {"protocol": "along", "title": "A: B", "tags": ["x", "y"],
                   "count": 3, "flag": True, "empty": ""}
        document = fm.render(payload, "# Body")
        fields, body = fm.parse(document)
        self.assertEqual(fields["title"], "A: B")
        self.assertEqual(fields["tags"], ["x", "y"])
        self.assertEqual(fields["count"], 3)
        self.assertIs(fields["flag"], True)
        self.assertEqual(body.strip(), "# Body")


class TestRepositoryPaths(unittest.TestCase):
    def test_root_markers_are_found_walking_upwards(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = os.path.realpath(tmp)
            os.makedirs(os.path.join(root, ".along"))
            deep = os.path.join(root, "a", "b", "c")
            os.makedirs(deep)
            self.assertEqual(os.path.realpath(repo.find_repo_root(deep)), root)

    def test_nearest_state_directory_wins(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = os.path.realpath(tmp)
            os.makedirs(os.path.join(root, ".along"))
            sub = os.path.join(root, "packages", "auth")
            os.makedirs(os.path.join(sub, ".along"))
            self.assertEqual(os.path.realpath(repo.find_state_dir(sub)),
                             os.path.join(sub, ".along"))

    def test_root_falls_back_to_the_start_directory(self):
        with tempfile.TemporaryDirectory() as tmp:
            deep = os.path.join(tmp, "x")
            os.makedirs(deep)
            self.assertTrue(os.path.isabs(repo.find_repo_root(deep)))

    def test_engine_resolution(self):
        self.assertTrue(repo.resolve_tool_script("along_exec.py", REPO_ROOT))
        self.assertIsNone(repo.resolve_tool_script("no_such_engine.py", REPO_ROOT))

    def test_safe_relpath_survives_a_cross_drive_path(self):
        other = "Z:\\elsewhere\\pkg" if sys.platform == "win32" else "/elsewhere/pkg"
        self.assertIsInstance(repo.safe_relpath(other, REPO_ROOT), str)

    def test_walker_skips_ignored_directories(self):
        with tempfile.TemporaryDirectory() as tmp:
            os.makedirs(os.path.join(tmp, "node_modules"))
            os.makedirs(os.path.join(tmp, ".hidden"))
            for rel in ("keep.md", os.path.join("node_modules", "skip.md"),
                        os.path.join(".hidden", "hidden.md")):
                with io.open(os.path.join(tmp, rel), "w", encoding="utf-8") as handle:
                    handle.write("# x\n")
            visible = [os.path.basename(p) for p in repo.iter_markdown_files(tmp)]
            everything = [os.path.basename(p)
                          for p in repo.iter_markdown_files(tmp, include_hidden=True)]
            self.assertEqual(visible, ["keep.md"])
            self.assertIn("hidden.md", everything)
            self.assertNotIn("skip.md", everything, "dependency trees are never scanned")


class TestSubprocessConventions(unittest.TestCase):
    NON_ASCII = "\u0442\u0435\u0441\u0442 \u2014 \u00e9\u00e8 \u4e2d\u6587"

    def test_non_ascii_child_output_decodes_on_any_host_locale(self):
        """
        The regression this module exists for.

        With `text=True` and no `encoding=`, Python decodes child output using
        `locale.getpreferredencoding()`: cp1251 on a Russian Windows install, cp936 on a
        Chinese one. A single non-ASCII byte then raised UnicodeDecodeError inside the
        stdout reader thread, `subprocess.run` returned `stdout=None` rather than failing,
        and the caller crashed later on a confusing secondary error.
        """
        res = proc.run_python(["-c", f"print({self.NON_ASCII!r})"])
        self.assertTrue(res.ok, res.stderr)
        self.assertEqual(res.out, self.NON_ASCII)

    def test_stdout_is_always_a_string(self):
        res = proc.run_capture([sys.executable, "-c", "pass"])
        self.assertIsInstance(res.stdout, str)
        self.assertIsInstance(res.stderr, str)

    def test_missing_executable_is_a_result_not_an_exception(self):
        res = proc.run_capture(["definitely-not-a-real-binary-xyz"])
        self.assertFalse(res.ok)
        self.assertEqual(res.returncode, 127)
        self.assertTrue(res.stderr)

    def test_check_raises_with_the_command_and_reason(self):
        with self.assertRaises(proc.ProcessError) as caught:
            proc.run_capture([sys.executable, "-c", "import sys; sys.exit(3)"], check=True)
        self.assertEqual(caught.exception.result.returncode, 3)

    def test_child_environment_forces_utf8_stdio(self):
        env = proc.child_env()
        self.assertEqual(env["PYTHONIOENCODING"], "utf-8")
        self.assertEqual(env["PYTHONUTF8"], "1")

    def test_timeout_is_reported_not_raised(self):
        res = proc.run_capture([sys.executable, "-c", "import time; time.sleep(5)"], timeout=0.5)
        self.assertFalse(res.ok)
        self.assertIn("timed out", res.stderr)


class TestTextIO(unittest.TestCase):
    def test_a_non_utf8_file_raises_and_is_left_untouched(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "cp1251.md")
            original = "\u043f\u0440\u0438\u0432\u0435\u0442".encode("cp1251")
            with io.open(path, "wb") as handle:
                handle.write(original)
            with self.assertRaises(UnicodeDecodeError):
                textio.read_text(path)
            with io.open(path, "rb") as handle:
                self.assertEqual(handle.read(), original)

    def test_line_endings_are_preserved_by_default(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "script.ps1")
            with io.open(path, "wb") as handle:
                handle.write(b"one\r\ntwo\r\n")
            probe = textio.read_text_file(path)
            self.assertEqual(probe.newline, CRLF)
            textio.write_text(path, probe.text.replace("two", "three"))
            with io.open(path, "rb") as handle:
                self.assertEqual(handle.read(), b"one\r\nthree\r\n")

    def test_write_is_atomic_and_leaves_no_temporary_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "a.md")
            textio.write_text(path, "content\n")
            self.assertEqual(os.listdir(tmp), ["a.md"])

    def test_no_bom_is_written(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "a.md")
            textio.write_text(path, "x\n")
            with io.open(path, "rb") as handle:
                self.assertFalse(handle.read().startswith(b"\xef\xbb\xbf"))


class TestEntities(unittest.TestCase):
    CURRENT_ADR = ("## ADR-2026-09-01--frontmatter-on-ruamel-yaml - Front-matter on ruamel.yaml\n"
                   "- Date: 2026-09-01\n- Status: accepted\n- Context: c\n")
    LEGACY_ADR = "## 007 - Legacy numeric decision\n- Date: 2026-08-27\n- Status: accepted\n"
    TEMPLATE = "## ADR-YYYY-MM-DD--<slug> - <Title>\n- Date: YYYY-MM-DD\n"

    def test_both_adr_header_formats_are_found(self):
        raw = "# Decisions\n\n" + self.CURRENT_ADR + "\n" + self.LEGACY_ADR
        keys = [entry["title"].split(" - ")[0]
                for entry in entities.parse_decision_entries(raw)]
        self.assertIn("ADR-2026-09-01--frontmatter-on-ruamel-yaml", keys)
        self.assertIn("ADR-007", keys)

    def test_the_schema_template_is_not_a_decision(self):
        entries = entities.parse_decision_entries("# Decisions\n\n" + self.TEMPLATE)
        self.assertEqual(entries, [])

    def test_a_bare_iso_date_heading_is_not_a_decision(self):
        entries = entities.parse_decision_entries("# Log\n\n## 2026-08-15 session notes\n")
        self.assertEqual(entries, [])

    def test_superseded_status_is_detected(self):
        raw = self.CURRENT_ADR.replace("- Status: accepted",
                                       "- Status: superseded by ADR-2026-09-02--x")
        self.assertEqual(entities.parse_decision_entries(raw)[0]["status"], "superseded")

    def test_a_written_adr_is_readable_by_the_reader(self):
        """The v2.2.0 header change was applied to the writer and missed in the reader."""
        entry = entities.format_adr("shared-python-library", "Extract a shared package",
                                    "c", "d", "q", day="2026-09-01")
        parsed = entities.parse_decision_entries("# Decisions\n" + entry)
        self.assertEqual(len(parsed), 1)
        self.assertIn("Extract a shared package", parsed[0]["title"])

    def test_canonical_keys_round_trip(self):
        self.assertEqual(entities.canonical_key("bug", "a-b"), "bug--a-b")
        self.assertEqual(entities.canonical_key("bug", "bug--a-b"), "bug--a-b")
        self.assertEqual(entities.parse_key("bug--a-b"), ("bug", "a-b"))
        self.assertEqual(entities.parse_key("[debt--x]"), ("debt", "x"))
        self.assertEqual(entities.parse_key("plain-slug"), (None, "plain-slug"))

    def test_slugify(self):
        self.assertEqual(entities.slugify("Extract a Shared Python Library!"),
                         "extract-a-shared-python-library")
        self.assertEqual(entities.slugify("", max_words=0), "untitled")

    def test_today_is_windows_safe_and_sortable(self):
        self.assertTrue(entities.is_iso_date(entities.today_iso()))
        self.assertNotIn(":", entities.today_iso())


class TestMarkdown(unittest.TestCase):
    DOC = "\n".join([
        "See [real](./topic--a.md) and [external](https://example.com).",
        "",
        "```markdown",
        "[documented example](./does-not-exist.md)",
        "```",
        "",
        "~~~text",
        "```",
        "[still inside a fence](./nope.md)",
        "~~~",
        "",
        "Final [link](../docs/topic--b.md#anchor).",
    ])

    def test_links_inside_fenced_code_are_ignored(self):
        targets = [link.target for link in markdown.find_links(self.DOC)]
        self.assertIn("./topic--a.md", targets)
        self.assertIn("../docs/topic--b.md#anchor", targets)
        self.assertNotIn("./does-not-exist.md", targets)
        self.assertNotIn("./nope.md", targets)

    def test_external_and_placeholder_targets_are_classified(self):
        self.assertTrue(markdown.is_external("https://example.com"))
        self.assertTrue(markdown.is_external("#section"))
        self.assertFalse(markdown.is_external("./topic--a.md"))
        self.assertTrue(markdown.is_placeholder("./topic--<slug>.md"))

    def test_rewrite_leaves_fenced_code_alone(self):
        out, count = markdown.rewrite_links(
            self.DOC, lambda link: "./renamed.md" if link.target == "./topic--a.md" else None)
        self.assertEqual(count, 1)
        self.assertIn("[real](./renamed.md)", out)
        self.assertIn("[documented example](./does-not-exist.md)", out)

    def test_anchor_matches_the_github_algorithm(self):
        self.assertEqual(
            markdown.github_heading_anchor("## ADR-2026-09-01--x - Title, With Punctuation"),
            "adr-2026-09-01--x---title-with-punctuation")

    def test_file_uri_targets_resolve(self):
        resolved = markdown.resolve_target("file://docs/topic--a.md",
                                           os.path.join(REPO_ROOT, "README.md"), REPO_ROOT)
        self.assertEqual(os.path.normpath(resolved),
                         os.path.normpath(os.path.join(REPO_ROOT, "docs", "topic--a.md")))
        self.assertIsNone(markdown.resolve_target("https://x.dev", "README.md", REPO_ROOT))


class TestTypography(unittest.TestCase):
    def test_every_banned_character_has_a_name(self):
        self.assertEqual(sorted(typography.REPLACEMENTS), sorted(typography.NAMES))

    def test_the_table_holds_no_literal_ascii_keys(self):
        for char in typography.REPLACEMENTS:
            self.assertGreater(ord(char), 127, f"{char!r} is ASCII and cannot be banned")

    def test_clean_replaces_and_reports(self):
        source = f"a{chr(0x2014)}b {chr(0x2014)} c{chr(0x201C)}q{chr(0x201D)}{chr(0x200B)}"
        cleaned, changed = typography.clean(source)
        self.assertTrue(changed)
        self.assertEqual(cleaned, 'a-b - c"q"')
        self.assertTrue(all(ord(c) < 128 for c in cleaned))

    def test_clean_is_a_noop_on_ascii(self):
        cleaned, changed = typography.clean("plain - ascii ... text")
        self.assertFalse(changed)
        self.assertEqual(cleaned, "plain - ascii ... text")

    def test_findings_locate_the_violation(self):
        hits = typography.findings("ok\nbad" + chr(0x00A0) + "here")
        self.assertEqual(hits[0][0], 2)
        self.assertEqual(hits[0][2], chr(0x00A0))


class TestSemver(unittest.TestCase):
    def test_parse_tolerates_prefixes_and_prereleases(self):
        self.assertEqual(semver.parse("v2.2.8"), (2, 2, 8))
        self.assertEqual(semver.parse("2.2.8-rc1"), (2, 2, 8))
        self.assertEqual(semver.parse("2.2"), (2, 2, 0))
        self.assertEqual(semver.parse("garbage"), (0, 0, 0))
        self.assertEqual(semver.parse(""), (0, 0, 0))

    def test_increments(self):
        self.assertEqual(semver.calculate_next("2.2.8", "patch"), "2.2.9")
        self.assertEqual(semver.calculate_next("2.2.8", "minor"), "2.3.0")
        self.assertEqual(semver.calculate_next("2.2.8", "major"), "3.0.0")
        self.assertEqual(semver.calculate_next("2.2.8", "v3.1.4"), "3.1.4")

    def test_an_invalid_bump_is_an_error_the_caller_handles(self):
        with self.assertRaises(ValueError):
            semver.calculate_next("2.2.8", "sideways")

    def test_comparison(self):
        self.assertTrue(semver.is_newer("2.3.0", "2.2.8"))
        self.assertFalse(semver.is_newer("2.2.8", "2.2.8"))


class TestNoDuplicateHelpers(unittest.TestCase):
    """The guard that keeps the duplication from growing back.

    Two rules, both about the engines rather than the package:

    1. No name may be defined at module level in two different engines. That is what
       `find_repo_root` (five copies) and `parse_frontmatter` (four) looked like.
    2. No engine may redefine a name the shared package already owns. It must import
       or alias it, so there is exactly one implementation to fix.

    Inside `scripts/alongkit/` the same short name may appear in different modules
    (`frontmatter.parse`, `semver.parse`): the module qualifies it, and the call sites
    read better for it.
    """

    #: Entry points and framework hooks that are legitimately per-module.
    ALLOWED = {"main", "get_collector"}

    PACKAGE_DIR = os.path.join(SCRIPTS_DIR, "alongkit")

    def _definitions(self, inside_package):
        found = {}
        roots = ([self.PACKAGE_DIR] if inside_package
                 else [SCRIPTS_DIR, os.path.join(REPO_ROOT, "dashboard"),
                       os.path.join(REPO_ROOT, "tests")])
        for base in roots:
            for current, dirs, files in os.walk(base):
                dirs[:] = [d for d in dirs if d != "__pycache__"]
                if not inside_package and os.path.abspath(current).startswith(
                        os.path.abspath(self.PACKAGE_DIR)):
                    continue
                for name in sorted(files):
                    if not name.endswith(".py"):
                        continue
                    path = os.path.join(current, name)
                    with io.open(path, "r", encoding="utf-8") as handle:
                        tree = ast.parse(handle.read(), filename=path)
                    for node in tree.body:
                        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef,
                                                 ast.ClassDef)):
                            continue
                        if node.name in self.ALLOWED:
                            continue
                        found.setdefault(node.name, []).append(
                            f"{os.path.relpath(path, REPO_ROOT)}:{node.lineno}")
        return found

    def test_no_name_is_defined_in_two_engines(self):
        duplicates = {name: places for name, places in self._definitions(False).items()
                      if len(places) > 1}
        self.assertEqual(
            duplicates, {},
            "these names are defined more than once; move them into scripts/alongkit/:\n"
            + "\n".join(f"  {name}: {', '.join(places)}"
                        for name, places in sorted(duplicates.items())))

    def test_no_engine_redefines_a_shared_helper(self):
        package = self._definitions(True)
        engines = self._definitions(False)
        shadowed = {name: places for name, places in engines.items() if name in package}
        self.assertEqual(
            shadowed, {},
            "these names already exist in scripts/alongkit/ and must be imported:\n"
            + "\n".join(f"  {name}: {', '.join(places)}"
                        for name, places in sorted(shadowed.items())))


class TestPackagingContract(unittest.TestCase):
    def _pyproject(self):
        with io.open(os.path.join(REPO_ROOT, "pyproject.toml"), "r", encoding="utf-8") as handle:
            return handle.read()

    def test_runtime_dependencies_have_one_home(self):
        """`pyproject.toml` is authoritative; the bootstrap list must not drift from it."""
        text = self._pyproject()
        for spec in bootstrap.RUNTIME_DEPENDENCIES:
            self.assertIn(f'"{spec}"', text,
                          f"{spec} is declared in alongkit.bootstrap but not in pyproject.toml")

    def test_engine_manifest_matches_scripts_dir(self):
        text = self._pyproject()
        engines = sorted(name for name in os.listdir(SCRIPTS_DIR) if name.endswith(".py"))
        missing = [name for name in engines
                   if f'"scripts/{name}" = "alongkit/engines/{name}"' not in text]
        self.assertEqual(missing, [],
                         "these engines would be absent from an installed wheel: "
                         f"{missing}")

    def test_console_entry_point_is_declared_and_importable(self):
        self.assertIn('along = "alongkit.cli:main"', self._pyproject())
        from alongkit import cli

        self.assertTrue(callable(cli.main))


class TestInstallersCarryThePackage(unittest.TestCase):
    """A global install is a file copy. If it misses `alongkit/`, every engine dies
    on ModuleNotFoundError, and the failure only appears outside this repository.
    """

    def test_bash_installer_copies_the_package(self):
        with io.open(os.path.join(REPO_ROOT, "install.sh"), "r", encoding="utf-8") as handle:
            text = handle.read()
        self.assertIn('cp -r "$scripts_src/alongkit"', text)

    def test_powershell_installer_copies_recursively(self):
        with io.open(os.path.join(REPO_ROOT, "install.ps1"), "r", encoding="utf-8") as handle:
            text = handle.read()
        self.assertIn("Copy-Item -Path", text)
        self.assertIn("-Recurse", text)
        self.assertIn("__pycache__", text,
                      "compiled caches must be pruned from the install")


class TestFlatInstallInvocation(unittest.TestCase):
    """
    The global install is a flat file copy into `~/.along/bin/`, not a package install.

    Python puts the running script's directory on `sys.path`, and the package is copied
    next to the engines, so `from alongkit import ...` has to resolve with no path
    manipulation and no `pip install`. This is the scenario REQ-4 of
    `[debt--extract-shared-python-library]` asks to cover.
    """

    def test_an_engine_runs_from_a_flat_directory_copy(self):
        with tempfile.TemporaryDirectory() as tmp:
            fake_bin = os.path.join(tmp, "bin")
            os.makedirs(fake_bin)
            for name in os.listdir(SCRIPTS_DIR):
                source = os.path.join(SCRIPTS_DIR, name)
                if name.endswith(".py"):
                    shutil.copy2(source, os.path.join(fake_bin, name))
            shutil.copytree(os.path.join(SCRIPTS_DIR, "alongkit"),
                            os.path.join(fake_bin, "alongkit"),
                            ignore=shutil.ignore_patterns("__pycache__"))

            consumer = os.path.join(tmp, "consumer")
            os.makedirs(os.path.join(consumer, ".along", "ISSUES"))
            with io.open(os.path.join(consumer, "AGENTS.md"), "w", encoding="utf-8") as handle:
                handle.write("# AGENTS\n")

            res = proc.run_python([os.path.join(fake_bin, "along_exec.py"), "status"],
                                  cwd=consumer)
            self.assertTrue(res.ok, f"exit {res.returncode}\n{res.stdout}\n{res.stderr}")
            self.assertIn("Along Repository Status", res.stdout)

    def test_the_engine_resolver_finds_siblings_in_the_flat_copy(self):
        self.assertTrue(repo.resolve_tool_script("sanitize_typography.py", REPO_ROOT))
        self.assertIn(repo.engines_dir(), repo.tool_search_path(REPO_ROOT))


if __name__ == "__main__":
    unittest.main()
