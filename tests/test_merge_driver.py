#!/usr/bin/env python3
"""
tests/test_merge_driver.py - Along custom git merge drivers and `along git setup`.

Covers [feat--git-merge-drivers-and-setup]: the front-matter 3-way merge rules, the
projection driver (keep ours + resync marker, safe fallback for foreign files), the
managed `.gitattributes` block, and an end-to-end merge of two concurrent branches in a
throwaway git repository. Nothing touches the live repository.
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

from alongkit import bootstrap
bootstrap.ensure_deps()

from alongkit import merge


def _issue(slug, status="open", tags="[git]", updated="2026-09-20", body="Body line.\n"):
    return (
        "---\n"
        "protocol: along\n"
        'protocol_version: "4.4.1"\n'
        f"slug: {slug}\n"
        "type: feat\n"
        f"status: {status}\n"
        "priority: medium\n"
        "created: 2026-09-20\n"
        f"updated: {updated}\n"
        f"tags: {tags}\n"
        "---\n\n"
        f"# {slug}\n\n"
        f"{body}"
    )


def _run_git(cwd, *args, check=True):
    return subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True,
                          encoding="utf-8", check=check)


def _write_file(path, text):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as handle:
        handle.write(text)


def _read_file(path):
    with open(path, "r", encoding="utf-8", newline="") as handle:
        return handle.read()


class TestFrontmatterValueMerge(unittest.TestCase):
    def test_one_side_change_wins(self):
        base = {"status": "open", "priority": "low"}
        merged, notes = merge.merge_frontmatter_values(base, {"status": "open", "priority": "high"},
                                                       {"status": "in-progress", "priority": "low"})
        self.assertEqual(merged, {"status": "in-progress", "priority": "high"})
        self.assertEqual(notes, [])

    def test_lists_three_way_set_merge(self):
        base = {"tags": ["a", "b"]}
        merged, _ = merge.merge_frontmatter_values(base, {"tags": ["a", "b", "ours"]},
                                                   {"tags": ["b", "theirs"]})
        # theirs removed "a", ours added "ours", theirs added "theirs"
        self.assertEqual(merged["tags"], ["b", "ours", "theirs"])

    def test_status_most_advanced(self):
        merged, notes = merge.merge_frontmatter_values(
            {"status": "open"}, {"status": "in-progress"}, {"status": "done"})
        self.assertEqual(merged["status"], "done")
        self.assertTrue(any("most advanced" in n for n in notes))

    def test_dates_take_latest(self):
        merged, _ = merge.merge_frontmatter_values(
            {"updated": "2026-09-01"}, {"updated": "2026-09-05"}, {"updated": "2026-09-03"})
        self.assertEqual(merged["updated"], "2026-09-05")

    def test_scalar_conflict_newer_updated_wins_tie_to_ours(self):
        base = {"title": "T", "updated": "2026-09-01"}
        merged, _ = merge.merge_frontmatter_values(
            base, {"title": "Ours", "updated": "2026-09-02"}, {"title": "Theirs", "updated": "2026-09-03"})
        self.assertEqual(merged["title"], "Theirs")
        merged, _ = merge.merge_frontmatter_values(
            base, {"title": "Ours", "updated": "2026-09-03"}, {"title": "Theirs", "updated": "2026-09-03"})
        self.assertEqual(merged["title"], "Ours")

    def test_delete_vs_modify_keeps_modification(self):
        merged, _ = merge.merge_frontmatter_values({"x": 1, "y": 1}, {"y": 1}, {"x": 2, "y": 1})
        self.assertEqual(merged["x"], 2)
        merged, _ = merge.merge_frontmatter_values({"x": 1, "y": 1}, {"y": 1}, {"x": 1, "y": 1})
        self.assertNotIn("x", merged)


class TestEntityTextMerge(unittest.TestCase):
    def test_concurrent_tags_and_status_merge_cleanly(self):
        base = _issue("feat--a")
        ours = _issue("feat--a", tags="[git, ours]", updated="2026-09-21")
        theirs = _issue("feat--a", status="in-progress", tags="[git, theirs]", updated="2026-09-22")
        text, clean, _ = merge.merge_entity_text(base, ours, theirs, ".along/ISSUES/feat--a.md")
        self.assertTrue(clean)
        self.assertIn("status: in-progress", text)
        self.assertIn("tags: [git, ours, theirs]", text)
        self.assertIn("updated: 2026-09-22", text)
        self.assertIn('protocol_version: "4.4.1"', text)
        self.assertNotIn("<<<<<<<", text)

    def test_non_overlapping_body_edits_merge(self):
        body = "one\n\ntwo\n\nthree\n\nfour\n\nfive\n"
        base = _issue("feat--a", body=body)
        ours = _issue("feat--a", body=body.replace("one", "ONE"))
        theirs = _issue("feat--a", body=body.replace("five", "FIVE"))
        text, clean, _ = merge.merge_entity_text(base, ours, theirs, "x.md")
        self.assertTrue(clean)
        self.assertIn("ONE", text)
        self.assertIn("FIVE", text)

    def test_overlapping_body_edits_report_conflict(self):
        base = _issue("feat--a", body="line\n")
        text, clean, _ = merge.merge_entity_text(
            base, _issue("feat--a", body="ours line\n"), _issue("feat--a", body="theirs line\n"), "x.md")
        self.assertFalse(clean)
        self.assertIn("<<<<<<<", text)

    def test_file_without_frontmatter_falls_back_to_text_merge(self):
        text, clean, notes = merge.merge_entity_text("a\n", "a\nb\n", "a\n", "x.md")
        self.assertTrue(clean)
        self.assertEqual(text, "a\nb\n")
        self.assertTrue(notes)


class TestProjectionDriverFiles(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="along-merge-test-")

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _paths(self, base, ours, theirs):
        paths = []
        for name, content in (("O", base), ("A", ours), ("B", theirs)):
            p = os.path.join(self.tmp, name)
            _write_file(p, content)
            paths.append(p)
        return paths

    def test_is_projection(self):
        self.assertTrue(merge.is_projection("# Active Issues\n\n## Active\n", ".along/ISSUES.md"))
        self.assertTrue(merge.is_projection(
            "<!-- Generated projection from .along/DECISIONS. Do not edit -->\n# X\n", ".along/CONSTRAINTS.md"))
        self.assertTrue(merge.is_projection(
            "---\nprotocol: along\nslug: INDEX\ntype: index\n---\n# I\n", "docs/INDEX.md"))
        self.assertFalse(merge.is_projection("# Some other index\n", "docs/INDEX.md"))
        self.assertFalse(merge.is_projection("# Decisions log\n", ".along/DECISIONS.md"))

    def test_foreign_file_is_text_merged_not_discarded(self):
        o, a, b = self._paths("# Index\n\nx\n", "# Index\n\nx\nours\n", "# Index\n\ntheirs\nx\n")
        code = merge.merge_projection(o, a, b, "packages/web/docs/INDEX.md")
        self.assertEqual(code, 0)
        merged = _read_file(a)
        self.assertIn("ours", merged)
        self.assertIn("theirs", merged)

    def test_driver_script_usage(self):
        script = os.path.join(SCRIPTS_DIR, merge.DRIVER_SCRIPT)
        res = subprocess.run([sys.executable, script], capture_output=True, text=True)
        self.assertEqual(res.returncode, 2)
        self.assertIn("usage", res.stderr)


class TestGitattributesBlock(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="along-merge-attrs-")

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_render_is_idempotent_and_reversible(self):
        user = "*.md text eol=lf\n.along/HISTORY.md merge=union\n.along/DECISIONS.md merge=union\n"
        once = merge.render_gitattributes(user, self.tmp)
        twice = merge.render_gitattributes(once, self.tmp)
        self.assertEqual(once, twice)
        self.assertEqual(once.count(merge.ATTR_BEGIN), 1)
        for line in ("**/.along/**/*.md -merge", "**/docs/**/*.md -merge",
                     "AGENTS.md -merge", "CLAUDE.md -merge"):
            self.assertIn(line, once)
        self.assertEqual(merge.render_gitattributes(once, self.tmp, uninstall=True), user)

    def test_committed_block_never_names_a_custom_driver(self):
        # An undefined driver name falls back to git's TEXT merge, so a committed
        # `merge=along-*` line would line-merge on every clone without `along git setup`.
        os.makedirs(os.path.join(self.tmp, ".along", "DECISIONS"))
        rendered = merge.render_gitattributes("", self.tmp)
        self.assertNotIn("merge=along-", rendered)

    def test_union_logs_come_after_the_protection_line(self):
        lines = merge.desired_attributes(self.tmp)
        protected = lines.index("**/.along/**/*.md -merge")
        self.assertGreater(lines.index("**/.along/HISTORY.md merge=union"), protected)
        self.assertGreater(lines.index(merge.DECISIONS_BOARD_PATTERN + " merge=union"), protected)

    def test_info_attributes_render_is_idempotent_and_reversible(self):
        user = "*.bin binary\n"
        once = merge.render_info_attributes(user, self.tmp)
        self.assertEqual(once, merge.render_info_attributes(once, self.tmp))
        self.assertIn("**/.along/ISSUES/**/*.md merge=along-frontmatter", once)
        self.assertEqual(merge.render_info_attributes(once, self.tmp, uninstall=True), user)

    def test_decisions_board_bound_only_with_modular_adrs(self):
        board = merge.DECISIONS_BOARD_PATTERN
        self.assertNotIn(board + " merge=along-projection", merge.desired_driver_attributes(self.tmp))
        self.assertIn(board + " merge=union", merge.desired_attributes(self.tmp))
        os.makedirs(os.path.join(self.tmp, ".along", "DECISIONS"))
        self.assertIn(board + " merge=along-projection", merge.desired_driver_attributes(self.tmp))
        self.assertNotIn(board + " merge=union", merge.desired_attributes(self.tmp))


@unittest.skipUnless(shutil.which("git"), "git not available")
class TestEndToEndMerge(unittest.TestCase):
    def setUp(self):
        self.repo = tempfile.mkdtemp(prefix="along-merge-e2e-")
        _run_git(self.repo, "init", "-q", "-b", "main")
        _run_git(self.repo, "config", "user.name", "Along Test")
        _run_git(self.repo, "config", "user.email", "test@example.invalid")
        _run_git(self.repo, "config", "commit.gpgsign", "false")
        _run_git(self.repo, "config", "core.autocrlf", "false")
        _write_file(os.path.join(self.repo, ".along", "ISSUES", "feat--a.md"), _issue("feat--a"))
        _write_file(os.path.join(self.repo, ".along", "ISSUES", "done", ".keep"), "keep\n")
        from alongkit import entities
        entities.sync_issues_board(self.repo)
        report = merge.setup(self.repo)
        self.assertTrue(report["git"])
        _run_git(self.repo, "add", "-A")
        _run_git(self.repo, "commit", "-q", "-m", "base")

    def tearDown(self):
        shutil.rmtree(self.repo, ignore_errors=True)

    def _issue_path(self, slug):
        return os.path.join(self.repo, ".along", "ISSUES", f"{slug}.md")

    def test_setup_is_idempotent_and_status_ok(self):
        again = merge.setup(self.repo)
        self.assertEqual(again["config_changed"], [])
        self.assertFalse(again["gitattributes_changed"])
        self.assertTrue(merge.is_configured(merge.status(self.repo)))
        self.assertEqual(_run_git(self.repo, "config", "--local", "--get", "push.followTags").stdout.strip(), "true")

    def test_concurrent_branches_merge_without_conflicts(self):
        from alongkit import entities

        _run_git(self.repo, "checkout", "-q", "-b", "feature")
        _write_file(self._issue_path("feat--a"),
               _issue("feat--a", status="in-progress", tags="[git, theirs]", updated="2026-09-22"))
        _write_file(self._issue_path("feat--b"), _issue("feat--b"))
        entities.sync_issues_board(self.repo)
        _run_git(self.repo, "add", "-A")
        _run_git(self.repo, "commit", "-q", "-m", "feature work")

        _run_git(self.repo, "checkout", "-q", "main")
        _write_file(self._issue_path("feat--a"), _issue("feat--a", tags="[git, ours]", updated="2026-09-21"))
        _write_file(self._issue_path("feat--c"), _issue("feat--c"))
        entities.sync_issues_board(self.repo)
        _run_git(self.repo, "add", "-A")
        _run_git(self.repo, "commit", "-q", "-m", "main work")

        res = _run_git(self.repo, "merge", "--no-edit", "feature", check=False)
        self.assertEqual(res.returncode, 0, res.stdout + res.stderr)
        unmerged = _run_git(self.repo, "diff", "--name-only", "--diff-filter=U").stdout.strip()
        self.assertEqual(unmerged, "")

        issue_a = _read_file(self._issue_path("feat--a"))
        self.assertIn("status: in-progress", issue_a)
        self.assertIn("tags: [git, ours, theirs]", issue_a)
        board = _read_file(os.path.join(self.repo, ".along", "ISSUES.md"))
        self.assertNotIn("<<<<<<<", board)

        self.assertEqual(merge.pending_resync(self.repo), [".along/ISSUES.md"])
        merge.resync(self.repo)
        self.assertEqual(merge.pending_resync(self.repo), [])
        board = _read_file(os.path.join(self.repo, ".along", "ISSUES.md"))
        for slug in ("feat--a", "feat--b", "feat--c"):
            self.assertIn(slug, board)

    def test_drivers_bound_per_clone_not_committed(self):
        info_path = merge.info_attributes_path(self.repo)
        self.assertIn(merge.INFO_ATTR_BEGIN, _read_file(info_path))
        self.assertNotIn("merge=along-", _read_file(os.path.join(self.repo, ".gitattributes")))
        attr = _run_git(self.repo, "check-attr", "merge", "--", ".along/ISSUES/feat--a.md").stdout
        self.assertIn("merge: along-frontmatter", attr)
        protection = merge.protection_status(self.repo)
        self.assertTrue(protection["active"], protection)

    def test_uninstall_removes_config_and_block(self):
        merge.setup(self.repo, uninstall=True)
        info = merge.status(self.repo)
        self.assertTrue(all(v == "missing" for v in info["config"].values()))
        self.assertNotIn(merge.ATTR_BEGIN, _read_file(os.path.join(self.repo, ".gitattributes")))
        info_path = merge.info_attributes_path(self.repo)
        if os.path.isfile(info_path):
            self.assertNotIn(merge.INFO_ATTR_BEGIN, _read_file(info_path))


@unittest.skipUnless(shutil.which("git"), "git not available")
class TestUnconfiguredCloneProtection(unittest.TestCase):
    """Only the committed `.gitattributes` baseline: no drivers, no info/attributes."""

    DOC = "# Topic\n\nIntro.\n\n## A\n\nalpha\n\n## B\n\nbeta\n\n## C\n\ngamma\n"

    def setUp(self):
        self.repo = tempfile.mkdtemp(prefix="along-merge-bare-")
        _run_git(self.repo, "init", "-q", "-b", "main")
        _run_git(self.repo, "config", "user.name", "Along Test")
        _run_git(self.repo, "config", "user.email", "test@example.invalid")
        _run_git(self.repo, "config", "commit.gpgsign", "false")
        _run_git(self.repo, "config", "core.autocrlf", "false")
        _write_file(os.path.join(self.repo, ".gitattributes"),
                    merge.render_gitattributes("*.md text eol=lf\n", self.repo))
        body = "one\n\ntwo\n\nthree\n\nfour\n\nfive\n"
        _write_file(self._p(".along/ISSUES/feat--a.md"), _issue("feat--a", body=body))
        _write_file(self._p("docs/topic--x.md"), self.DOC)
        _write_file(self._p(".along/HISTORY.md"), "# History\n\n- base\n")
        _run_git(self.repo, "add", "-A")
        _run_git(self.repo, "commit", "-q", "-m", "base")

        _run_git(self.repo, "checkout", "-q", "-b", "feature")
        _write_file(self._p(".along/ISSUES/feat--a.md"),
                    _issue("feat--a", status="in-progress", tags="[git, theirs]",
                           updated="2026-09-22", body=body.replace("five", "FIVE")))
        _write_file(self._p("docs/topic--x.md"), self.DOC.replace("gamma", "gamma theirs"))
        _write_file(self._p(".along/HISTORY.md"), "# History\n\n- base\n- theirs\n")
        _run_git(self.repo, "commit", "-q", "-am", "feature")

        _run_git(self.repo, "checkout", "-q", "main")
        _write_file(self._p(".along/ISSUES/feat--a.md"),
                    _issue("feat--a", tags="[git, ours]", updated="2026-09-21",
                           body=body.replace("one", "ONE")))
        _write_file(self._p("docs/topic--x.md"), self.DOC.replace("alpha", "alpha ours"))
        _write_file(self._p(".along/HISTORY.md"), "# History\n\n- base\n- ours\n")
        _run_git(self.repo, "commit", "-q", "-am", "main")

    def tearDown(self):
        shutil.rmtree(self.repo, ignore_errors=True)

    def _p(self, rel):
        return os.path.join(self.repo, *rel.split("/"))

    def _unmerged(self):
        out = _run_git(self.repo, "diff", "--name-only", "--diff-filter=U").stdout
        return sorted(line for line in out.splitlines() if line)

    def test_protection_is_active_without_drivers(self):
        self.assertTrue(merge.protection_status(self.repo)["active"])

    def test_non_overlapping_edits_stop_without_markers(self):
        res = _run_git(self.repo, "merge", "--no-edit", "feature", check=False)
        self.assertNotEqual(res.returncode, 0, res.stdout)
        self.assertEqual(self._unmerged(), [".along/ISSUES/feat--a.md", "docs/topic--x.md"])
        issue = _read_file(self._p(".along/ISSUES/feat--a.md"))
        self.assertNotIn("<<<<<<<", issue)
        self.assertIn("ONE", issue)
        self.assertNotIn("FIVE", issue)
        history = _read_file(self._p(".along/HISTORY.md"))
        self.assertIn("- ours", history)
        self.assertIn("- theirs", history)

    def test_stage_aware_resolve_and_sync(self):
        from alongkit import resolve
        from alongkit.commands import gates

        _run_git(self.repo, "merge", "--no-edit", "feature", check=False)
        self.assertEqual(resolve.get_unmerged_docs(self.repo),
                         [".along/ISSUES/feat--a.md", "docs/topic--x.md"])
        stages = resolve.get_unmerged_stages("docs/topic--x.md", self.repo)
        self.assertIsNotNone(stages)
        self.assertIn("gamma theirs", stages[2])

        rc = gates._git_sync(self.repo)
        self.assertEqual(self._unmerged(), [])
        issue = _read_file(self._p(".along/ISSUES/feat--a.md"))
        self.assertIn("status: in-progress", issue)
        self.assertIn("tags: [git, ours, theirs]", issue)
        self.assertIn("ONE", issue)
        self.assertIn("FIVE", issue)
        doc = _read_file(self._p("docs/topic--x.md"))
        self.assertIn("alpha ours", doc)
        self.assertIn("gamma theirs", doc)
        self.assertNotIn("<<<<<<<", doc)
        self.assertIn(rc, (0, 1))  # gate violations in the fixture are not under test

    def test_overlapping_prose_stays_unresolved(self):
        from alongkit import resolve

        _run_git(self.repo, "merge", "--abort", check=False)
        _run_git(self.repo, "checkout", "-q", "-b", "clash", "main~1")
        _write_file(self._p("docs/topic--x.md"), self.DOC.replace("alpha", "alpha CLASH"))
        _run_git(self.repo, "commit", "-q", "-am", "clash")
        _run_git(self.repo, "checkout", "-q", "main")
        _run_git(self.repo, "merge", "--no-edit", "clash", check=False)
        clean, _ = resolve.resolve_path(self._p("docs/topic--x.md"), self.repo)
        self.assertFalse(clean)
        self.assertIn("docs/topic--x.md", self._unmerged())


if __name__ == "__main__":
    unittest.main()
