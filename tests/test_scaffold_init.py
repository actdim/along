#!/usr/bin/env python3
"""
tests/test_scaffold_init.py - one VISION per context, FULL/REF protocol blocks, and the
deterministic `along init` [bug--init-onboarding-regressions].

The regressions under test:
- `/along-init` on a repository with a root `VISION.md` created `.along/VISION.md` next
  to it, leaving two visions;
- the FULL vs REF protocol block choice and the adoption of a hand-written `AGENTS.md`
  existed only in `along update`, undocumented and without `## Project specifics`;
- there was no deterministic init engine, so agents skipped steps.

All fixtures are throwaway directories; nothing here touches the live repository.
"""

from __future__ import annotations

import json
import os
import shutil
import sys
import tempfile
import unittest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPTS_DIR = os.path.join(REPO_ROOT, "scripts")
TESTS_DIR = os.path.dirname(os.path.abspath(__file__))
for _path in (SCRIPTS_DIR, TESTS_DIR):
    if _path not in sys.path:
        sys.path.insert(0, _path)

import hermetic
from alongkit import migration, proc, scaffold, textio

INIT_ENGINE = os.path.join(SCRIPTS_DIR, "along_init.py")
MIGRATE_ENGINE = os.path.join(SCRIPTS_DIR, "migrate_protocol.py")
FAST_FLAGS = ("--no-hooks", "--no-rules", "--no-git", "--no-migrate")


def write_fixture(path, text):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    textio.write_text(path, text)


def read_fixture(path):
    return textio.read_text(path)


class _TempRepo(unittest.TestCase):
    def setUp(self):
        self.root = tempfile.mkdtemp(prefix="along-scaffold-")
        self.addCleanup(shutil.rmtree, self.root, True)

    def path(self, *parts):
        return os.path.join(self.root, *parts)

    def reconcile(self, dry_run=False):
        mig = migration.Migration(self.root, dry_run=dry_run, printer=lambda _m: None)
        return scaffold.reconcile_root_vision(self.root, mig), mig


class TestReconcileRootVision(_TempRepo):
    def setUp(self):
        super().setUp()
        os.makedirs(self.path(".along"))

    def test_moves_when_state_vision_is_missing(self):
        write_fixture(self.path("VISION.md"), "# Vision\n\n## Scope\nA tool, see [arch](docs/arch.md).\n")
        result, _ = self.reconcile()
        self.assertEqual(result["action"], "moved")
        self.assertFalse(os.path.exists(self.path("VISION.md")))
        moved = read_fixture(self.path(".along", "VISION.md"))
        self.assertIn("A tool", moved)
        self.assertIn("(../docs/arch.md)", moved, "relative links must be rebased")

    def test_replaces_skeleton(self):
        write_fixture(self.path(".along", "VISION.md"), scaffold.vision_template())
        write_fixture(self.path("VISION.md"), "# Vision\n\n## Scope\nReal scope.\n")
        result, _ = self.reconcile()
        self.assertEqual(result["action"], "replaced-skeleton")
        self.assertIn("Real scope.", read_fixture(self.path(".along", "VISION.md")))
        self.assertFalse(os.path.exists(self.path("VISION.md")))

    def test_identical_root_copy_is_removed(self):
        text = "# Vision\n\n## Scope\nSame.\n"
        write_fixture(self.path(".along", "VISION.md"), text)
        write_fixture(self.path("VISION.md"), text.replace("\n", "\r\n"))
        result, _ = self.reconcile()
        self.assertEqual(result["action"], "removed-duplicate")
        self.assertEqual(read_fixture(self.path(".along", "VISION.md")), text)
        self.assertFalse(os.path.exists(self.path("VISION.md")))

    def test_divergent_content_is_merged_under_marker_and_root_backed_up(self):
        write_fixture(self.path(".along", "VISION.md"), "# Vision\n\n## Scope\nState scope.\n")
        write_fixture(self.path("VISION.md"), "# Vision\n\n## Roadmap\n- ship v1\n")
        result, mig = self.reconcile()
        self.assertEqual(result["action"], "merged-needs-restructure")
        merged = read_fixture(self.path(".along", "VISION.md"))
        self.assertIn("State scope.", merged)
        self.assertIn("- ship v1", merged)
        self.assertIn(scaffold.IMPORTED_VISION_BEGIN, merged)
        self.assertIn(scaffold.IMPORTED_VISION_END, merged)
        self.assertIn("### Roadmap", merged, "imported headings are demoted under the import heading")
        self.assertFalse(os.path.exists(self.path("VISION.md")))
        self.assertTrue(os.path.isfile(os.path.join(mig.backup_dir, "root", "VISION.md")))
        self.assertEqual(scaffold.find_imported_vision_markers(self.root),
                         [self.path(".along", "VISION.md")])

    def test_links_are_repointed_public_to_index_and_state_to_new_vision(self):
        write_fixture(self.path("VISION.md"), "# Vision\n\nScope.\n")
        write_fixture(self.path("README.md"), "Read the [vision](VISION.md#scope).\n")
        write_fixture(self.path("docs", "guide.md"), "See [vision](../VISION.md).\n")
        write_fixture(self.path(".along", "ISSUES", "feat--a.md"), "See [v](../../VISION.md).\n")
        result, _ = self.reconcile()
        self.assertEqual(read_fixture(self.path("README.md")), "Read the [vision](docs/INDEX.md).\n")
        self.assertEqual(read_fixture(self.path("docs", "guide.md")), "See [vision](INDEX.md).\n")
        self.assertEqual(read_fixture(self.path(".along", "ISSUES", "feat--a.md")), "See [v](../VISION.md).\n")
        self.assertTrue(os.path.isfile(self.path("docs", "INDEX.md")))
        self.assertEqual(len(result["links"]), 3)

    def test_subfolder_vision_is_never_touched(self):
        write_fixture(self.path("packages", "lib", "VISION.md"), "# Lib vision\n")
        result, _ = self.reconcile()
        self.assertEqual(result["action"], "none")
        self.assertTrue(os.path.isfile(self.path("packages", "lib", "VISION.md")))

    def test_dry_run_writes_nothing(self):
        write_fixture(self.path("VISION.md"), "# Vision\n\nScope.\n")
        write_fixture(self.path("README.md"), "[v](VISION.md)\n")
        result, _ = self.reconcile(dry_run=True)
        self.assertEqual(result["action"], "moved")
        self.assertTrue(os.path.isfile(self.path("VISION.md")))
        self.assertFalse(os.path.exists(self.path(".along", "VISION.md")))
        self.assertEqual(read_fixture(self.path("README.md")), "[v](VISION.md)\n")

    def test_skeleton_detection_is_structural(self):
        self.assertTrue(scaffold.is_vision_skeleton(scaffold.vision_template()))
        self.assertTrue(scaffold.is_vision_skeleton("---\nprotocol: along\n---\n# Vision\n<!-- x -->\n"))
        self.assertFalse(scaffold.is_vision_skeleton("# Vision\n\n## Scope\nA real sentence.\n"))


class TestProtocolBlock(_TempRepo):
    def test_nested_folder_gets_ref_inside_one_git_tree(self):
        os.makedirs(self.path(".git"))
        write_fixture(self.path("AGENTS.md"), scaffold.render_protocol_block("PROTO") + "\n")
        nested = self.path("packages", "lib")
        os.makedirs(nested)
        info = scaffold.protocol_block_for(nested, "PROTO")
        self.assertEqual(info["variant"], "REF")
        self.assertEqual(info["ref"], "../../AGENTS.md")

    def test_submodule_root_gets_full(self):
        os.makedirs(self.path(".git"))
        write_fixture(self.path("AGENTS.md"), scaffold.render_protocol_block("PROTO") + "\n")
        submodule = self.path("vendor-libs", "sub")
        os.makedirs(submodule)
        write_fixture(os.path.join(submodule, ".git"), "gitdir: ../../.git/modules/sub\n")
        self.assertEqual(scaffold.protocol_block_for(submodule, "PROTO")["variant"], "FULL")

    def test_walk_stops_at_git_boundary(self):
        write_fixture(self.path("AGENTS.md"), scaffold.render_protocol_block("PROTO") + "\n")
        inner = self.path("inner")
        os.makedirs(os.path.join(inner, ".git"))
        nested = os.path.join(inner, "pkg")
        os.makedirs(nested)
        self.assertEqual(scaffold.protocol_block_for(nested, "PROTO")["variant"], "FULL")

    def test_handwritten_agents_md_keeps_text_under_project_specifics(self):
        original = "# Team rules\n\nAlways use tabs.\n"
        merged = scaffold.merge_protocol_block(original, "<BLOCK>")
        self.assertTrue(merged.startswith("<BLOCK>\n\n## Project specifics\n\n"))
        self.assertTrue(merged.endswith(original))

    def test_existing_specifics_heading_is_not_duplicated(self):
        original = "## Project specifics\n\n- keep\n"
        merged = scaffold.merge_protocol_block(original, "<BLOCK>")
        self.assertEqual(merged.count("Project specifics"), 1)

    def test_managed_block_is_replaced_in_place(self):
        existing = ("Intro.\n<!-- BEGIN ACTDIM-AGENTS-PROTOCOL root -->\nold\n"
                    "<!-- END ACTDIM-AGENTS-PROTOCOL -->\n\n## Project specifics\n\n- keep\n")
        merged = scaffold.merge_protocol_block(existing, "<BLOCK>")
        self.assertEqual(merged, "Intro.\n<BLOCK>\n\n## Project specifics\n\n- keep\n")


class TestAlongInit(_TempRepo):
    def run_init(self, target=None, *flags):
        return proc.run_capture([sys.executable, INIT_ENGINE, target or self.root, *flags],
                                env=hermetic.isolated_home_env())

    def test_first_run_scaffolds_and_moves_vision(self):
        write_fixture(self.path("AGENTS.md"), "# Team rules\n\nAlways use tabs.\n")
        write_fixture(self.path("VISION.md"), "# Vision\n\n## Scope\nA tool.\n")
        write_fixture(self.path("ROADMAP.md"), "- q1\n")
        res = self.run_init(None, *FAST_FLAGS, "--json")
        self.assertEqual(res.returncode, 0, res.stderr)
        report = json.loads(res.stdout)
        self.assertEqual(report["protocol_variant"], "FULL")
        self.assertTrue(report["adopted_handwritten_agents_md"])
        self.assertEqual(report["vision"]["action"], "moved")
        self.assertEqual(report["root_notes"], ["ROADMAP.md"])
        self.assertFalse(report["rerun"])
        self.assertFalse(os.path.exists(self.path("VISION.md")))
        self.assertIn("A tool.", read_fixture(self.path(".along", "VISION.md")))
        agents = read_fixture(self.path("AGENTS.md"))
        self.assertIn("<!-- BEGIN ALONG-PROTOCOL root", agents)
        self.assertTrue(agents.endswith("## Project specifics\n\n# Team rules\n\nAlways use tabs.\n"))
        self.assertIn("@AGENTS.md", read_fixture(self.path("CLAUDE.md")))
        self.assertIn(".along/HISTORY.md merge=union", read_fixture(self.path(".gitattributes")))
        for rel in ("ISSUES.md", "GLOSSARY.md", "HISTORY.md", os.path.join("ISSUES", "done")):
            self.assertTrue(os.path.exists(self.path(".along", rel)), rel)
        self.assertTrue(os.path.isfile(self.path("docs", "INDEX.md")))

    def test_second_run_is_idempotent_and_asks_rerun_questions(self):
        self.assertEqual(self.run_init(None, *FAST_FLAGS).returncode, 0)
        snapshot = {rel: read_fixture(self.path(rel)) for rel in ("AGENTS.md", "CLAUDE.md", ".gitattributes",
                                                          os.path.join(".along", "VISION.md"))}
        res = self.run_init(None, *FAST_FLAGS)
        self.assertEqual(res.returncode, 0, res.stderr)
        self.assertIn("RE-RUN QUESTIONS", res.stdout)
        for rel, text in snapshot.items():
            self.assertEqual(read_fixture(self.path(rel)), text, rel)

    def test_dry_run_writes_nothing(self):
        write_fixture(self.path("VISION.md"), "# Vision\n")
        res = self.run_init(None, "--dry-run", "--no-hooks")
        self.assertEqual(res.returncode, 0, res.stderr)
        self.assertIn("would run", res.stdout)
        self.assertEqual(sorted(os.listdir(self.root)), ["VISION.md"])

    def test_nested_folder_gets_ref_block(self):
        os.makedirs(self.path(".git"))
        self.assertEqual(self.run_init(None, *FAST_FLAGS).returncode, 0)
        nested = self.path("packages", "lib")
        os.makedirs(nested)
        res = self.run_init(nested, *FAST_FLAGS)
        self.assertEqual(res.returncode, 0, res.stderr)
        self.assertIn("ref=../../AGENTS.md", read_fixture(os.path.join(nested, "AGENTS.md")))


class TestMigrationStandalonePass(unittest.TestCase):
    """A root VISION.md added after the repository is current is still reconciled."""

    def test_already_migrated_repo_heals_root_vision(self):
        with hermetic.repo_fixture() as root:
            env = hermetic.isolated_home_env()
            first = proc.run_capture([sys.executable, MIGRATE_ENGINE, root, "--apply"], env=env)
            self.assertEqual(first.returncode, 0, first.stdout + first.stderr)
            write_fixture(os.path.join(root, "VISION.md"), "# Vision\n\n## Roadmap\n- later\n")
            second = proc.run_capture([sys.executable, MIGRATE_ENGINE, root, "--apply"], env=env)
            self.assertEqual(second.returncode, 0, second.stdout + second.stderr)
            self.assertIn("Step 13", second.stdout)
            self.assertFalse(os.path.exists(os.path.join(root, "VISION.md")))
            merged = read_fixture(os.path.join(root, ".along", "VISION.md"))
            self.assertIn("Fixture.", merged)
            self.assertIn("- later", merged)
            self.assertIn(scaffold.IMPORTED_VISION_BEGIN, merged)


if __name__ == "__main__":
    unittest.main()
