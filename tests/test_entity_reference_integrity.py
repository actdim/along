#!/usr/bin/env python3
"""
tests/test_entity_reference_integrity.py - [gate: entity-reference-integrity].

Covers [feat--entity-reference-integrity-gate]: the shared validator (ancestor contexts),
the wrap / issue-sync gate in enforce and shadow mode, the Stop predicate, the commit-time
check that blocks only newly introduced problems, `along issue rename` / `supersede`
reference rewriting, milestone `target_issues` sync on `issue create`, the migration graph
reusing the validator, and `along bump` refusing to complete a milestone with open issues.
Every test runs in a throwaway git repository; nothing touches the live repository.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPTS_DIR = os.path.join(REPO_ROOT, "scripts")
if SCRIPTS_DIR not in sys.path:
    sys.path.insert(0, SCRIPTS_DIR)

from alongkit import bootstrap
bootstrap.ensure_deps()

from alongkit import entities, frontmatter, gates, gitgates, textio, transaction
from alongkit.hooks import predicates
from alongkit.hooks.models import HookEvent, HookEventType

EXEC = os.path.join(SCRIPTS_DIR, "along_exec.py")
MILESTONE = "v9.1.0-fixture-release"


def _er_git(cwd, *args):
    return subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True,
                          encoding="utf-8", check=True)


def _er_write(root, rel, text):
    path = os.path.join(root, *rel.split("/"))
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as handle:
        handle.write(text)
    return path


def _er_issue(slug, itype="feat", status="open", related=(), blocked_by=(), milestone=MILESTONE,
              extra=""):
    done = "completed: 2026-09-30\n" if status in entities.CLOSED_ISSUE_STATUSES else ""
    return (
        "---\nprotocol: along\n"
        f"slug: {slug}\ntype: {itype}\nstatus: {status}\npriority: medium\n"
        f"created: 2026-09-30\nupdated: 2026-09-30\n{done}"
        f"milestone: {milestone}\n"
        f"blocked_by: [{', '.join(blocked_by)}]\nrelated: [{', '.join(related)}]\n{extra}"
        f"---\n\n# {slug}\n"
    )


def _er_milestone(targets=(), status="in-progress", slug=MILESTONE):
    return (
        "---\nprotocol: along\n"
        f"slug: {slug}\ntitle: Fixture release\nstatus: {status}\n"
        f"target_issues: [{', '.join(targets)}]\nprogress_pct: 0\n"
        f"---\n\n# {slug}\n"
    )


def _er_session(issues):
    return (
        "---\nprotocol: along\nslug: fixture-session\ndate: 2026-09-30\n"
        f"issues_advanced: []\nissues_completed: [{', '.join(issues)}]\n"
        "---\n\n# Session\n"
    )


def _er_fm(path):
    fields, _ = frontmatter.parse(textio.read_text(path), path=path)
    return fields


class _ErRepo(unittest.TestCase):
    """A git repository with two linked issues, a milestone and a session log."""

    def setUp(self):
        self.root = tempfile.mkdtemp(prefix="along_entity_refs_")
        _er_git(self.root, "init", "-q")
        _er_git(self.root, "config", "user.email", "t@example.com")
        _er_git(self.root, "config", "user.name", "t")
        _er_git(self.root, "config", "core.autocrlf", "false")
        self.a = _er_write(self.root, ".along/ISSUES/feat--alpha-task.md", _er_issue("alpha-task"))
        self.b = _er_write(self.root, ".along/ISSUES/feat--beta-task.md",
                           _er_issue("beta-task", related=["feat--alpha-task"],
                                     blocked_by=["alpha-task"]))
        self.m = _er_write(self.root, f".along/MILESTONES/{MILESTONE}.md",
                           _er_milestone(["feat--alpha-task", "feat--beta-task"]))
        self.s = _er_write(self.root, ".along/SESSIONS/2026/2026-09-30--fixture-session.md",
                           _er_session(["feat--alpha-task"]))
        os.makedirs(os.path.join(self.root, ".along", "ISSUES", "done"), exist_ok=True)

    def tearDown(self):
        shutil.rmtree(self.root, ignore_errors=True)

    def commit_all(self):
        _er_git(self.root, "add", "-A")
        _er_git(self.root, "commit", "-q", "--no-verify", "-m", "fixture")

    def errors(self):
        return entities.validate_entities(self.root)["errors"]


class TestValidatorAndGate(_ErRepo):

    def test_fixture_is_clean_and_deletion_dangles(self):
        self.assertEqual(self.errors(), [])
        os.remove(self.a)
        messages = [msg for _, msg in self.errors()]
        self.assertIn("dangling related reference: 'feat--alpha-task'", messages)
        self.assertIn("dangling blocked_by reference: 'alpha-task'", messages)
        self.assertIn("dangling target_issues reference: 'feat--alpha-task'", messages)

    def test_ancestor_context_resolves_and_stops_at_git(self):
        sub = os.path.join(self.root, "packages", "sub")
        _er_write(sub, ".along/ISSUES/feat--sub-task.md",
                  _er_issue("sub-task", related=["feat--beta-task"], milestone=MILESTONE))
        self.assertEqual(entities.validate_entities(sub)["errors"], [])
        self.assertTrue(entities.validate_entities(sub, ancestors=False)["errors"])
        self.assertEqual(entities.ancestor_entity_keys(self.root), set())

    def test_gate_blocks_in_enforce_and_warns_in_shadow(self):
        self.assertTrue(gates.entity_integrity_gate(self.root, "T"))
        os.remove(self.a)
        with mock.patch.dict(os.environ, {"ALONG_HOOK_MODE": "enforce"}):
            self.assertFalse(gates.entity_integrity_gate(self.root, "T"))
        with mock.patch.dict(os.environ, {"ALONG_HOOK_MODE": "shadow"}):
            self.assertTrue(gates.entity_integrity_gate(self.root, "T"))

    def test_stop_predicate_runs_only_after_entity_changes(self):
        event = HookEvent(event_type=HookEventType.STOP)
        self.commit_all()
        self.assertIsNone(predicates.check_entity_reference_integrity(event, self.root))
        os.remove(self.a)
        message = predicates.check_entity_reference_integrity(event, self.root)
        self.assertIn("[gate: entity-reference-integrity]", message)
        self.assertIn("feat--alpha-task", message)

    def test_issue_sync_exits_nonzero_on_dangling_reference(self):
        os.remove(self.a)
        env = dict(os.environ, ALONG_HOOK_MODE="enforce")
        result = subprocess.run([sys.executable, EXEC, "issue", "sync"], cwd=self.root, env=env,
                                capture_output=True, text=True, encoding="utf-8")
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn("entity-reference-integrity", result.stderr)


class TestNestedContexts(_ErRepo):
    """[bug--entity-refs-ignore-nested-contexts]: root entities reference subproject ones."""

    def setUp(self):
        super().setUp()
        self.sub = os.path.join(self.root, "apps", "a")
        _er_write(self.sub, ".along/ISSUES/feat--sub-feature.md",
                  _er_issue("sub-feature", milestone="v9.3.0-sub-release"))
        _er_write(self.sub, ".along/ISSUES/done/bug--sub-fix.md",
                  _er_issue("sub-fix", itype="bug", status="done", milestone="v9.3.0-sub-release"))
        _er_write(self.sub, ".along/MILESTONES/v9.3.0-sub-release.md",
                  _er_milestone(["feat--sub-feature"], slug="v9.3.0-sub-release"))
        _er_write(self.root, ".along/ISSUES/feat--root-epic.md",
                  _er_issue("root-epic", related=["feat--sub-feature"], blocked_by=["bug--sub-fix"]))
        _er_write(self.root, ".along/SESSIONS/2026/2026-09-30--root-release.md",
                  _er_session(["bug--sub-fix", "feat--alpha-task"]))

    def test_downward_references_resolve(self):
        self.assertEqual(self.errors(), [])
        self.assertIn("feat--sub-feature", entities.descendant_entity_keys(self.root))
        self.assertEqual(entities.validate_entities(self.sub)["errors"], [])

    def test_real_dangling_reference_is_still_reported(self):
        _er_write(self.root, ".along/ISSUES/feat--root-epic.md",
                  _er_issue("root-epic", related=["feat--sub-feature", "feat--nowhere-task"]))
        messages = [msg for _, msg in self.errors()]
        self.assertEqual(messages, ["dangling related reference: 'feat--nowhere-task'"])

    def test_descendants_false_restores_old_behavior(self):
        messages = [msg for _, msg in entities.validate_entities(self.root, descendants=False)["errors"]]
        self.assertIn("dangling related reference: 'feat--sub-feature'", messages)
        self.assertIn("dangling issues_completed reference: 'bug--sub-fix'", messages)

    def test_nested_git_repository_and_ignored_dirs_are_not_entered(self):
        nested = os.path.join(self.root, "vendor-repo")
        os.makedirs(os.path.join(nested, ".git"))
        _er_write(nested, ".along/ISSUES/feat--nested-repo-task.md", _er_issue("nested-repo-task"))
        _er_write(self.root, "node_modules/pkg/.along/ISSUES/feat--dependency-task.md",
                  _er_issue("dependency-task"))
        keys = entities.descendant_entity_keys(self.root)
        self.assertNotIn("feat--nested-repo-task", keys)
        self.assertNotIn("feat--dependency-task", keys)


class TestPreexistingProblemsDoNotBlock(_ErRepo):
    """[bug--entity-gate-blocks-preexisting-problems]."""

    def setUp(self):
        super().setUp()
        _er_write(self.root, ".along/ISSUES/feat--gamma-task.md",
                  _er_issue("gamma-task", related=["feat--long-gone-task"]))
        self.commit_all()

    def test_baseline_holds_the_committed_problem(self):
        self.assertEqual(gitgates.baseline_entity_problems(self.root),
                         {(".along/ISSUES/feat--gamma-task.md",
                           "dangling related reference: 'feat--long-gone-task'")})

    def test_unrelated_entity_change_passes_stop_gate_and_issue_sync(self):
        event = HookEvent(event_type=HookEventType.STOP)
        _er_write(self.root, ".along/ISSUES/feat--delta-task.md", _er_issue("delta-task"))
        self.assertIsNone(predicates.check_entity_reference_integrity(event, self.root))
        new, old = gates.split_entity_integrity_errors(self.root)
        self.assertEqual(new, [])
        self.assertEqual(len(old), 1)
        env = dict(os.environ, ALONG_HOOK_MODE="enforce")
        result = subprocess.run([sys.executable, EXEC, "issue", "sync"], cwd=self.root, env=env,
                                capture_output=True, text=True, encoding="utf-8")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("pre-existing", result.stderr)
        self.assertIn("feat--long-gone-task", result.stderr)

    def test_new_problem_still_blocks(self):
        event = HookEvent(event_type=HookEventType.STOP)
        os.remove(self.a)
        message = predicates.check_entity_reference_integrity(event, self.root)
        self.assertIn("feat--alpha-task", message)
        self.assertNotIn("long-gone", message)
        with mock.patch.dict(os.environ, {"ALONG_HOOK_MODE": "enforce"}):
            self.assertFalse(gates.entity_integrity_gate(self.root, "T"))

    def test_baseline_of_a_subproject_context(self):
        sub = os.path.join(self.root, "apps", "b")
        _er_write(sub, ".along/ISSUES/feat--sub-task.md",
                  _er_issue("sub-task", related=["feat--sub-missing"]))
        self.commit_all()
        self.assertEqual(gitgates.baseline_entity_problems(sub),
                         {(".along/ISSUES/feat--sub-task.md",
                           "dangling related reference: 'feat--sub-missing'")})


class TestDoctorFixDanglingMilestones(_ErRepo):
    """[bug--migration-dangling-template-milestones] REQ-4."""

    def test_fix_removes_only_dangling_milestones(self):
        stray = _er_write(self.root, ".along/ISSUES/done/feat--old-task.md",
                          _er_issue("old-task", status="done", milestone="v0.9.0-never-existed"))
        _er_write(self.root, ".along/SESSIONS/2026/2026-09-29--old-session.md",
                  "---\nprotocol: along\nslug: old-session\ndate: 2026-09-29\n"
                  "milestone: v0.9.0-never-existed\nissues_advanced: []\nissues_completed: []\n"
                  "---\n\n# Session\n")
        self.assertEqual(entities.drop_dangling_milestones(self.root, dry_run=True),
                         [".along/ISSUES/done/feat--old-task.md",
                          ".along/SESSIONS/2026/2026-09-29--old-session.md"])
        self.assertEqual(_er_fm(stray)["milestone"], "v0.9.0-never-existed")
        result = subprocess.run([sys.executable, EXEC, "doctor", "--entities", "--fix"], cwd=self.root,
                                capture_output=True, text=True, encoding="utf-8")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("Removed 2 dangling milestone field(s)", result.stdout)
        self.assertNotIn("milestone", _er_fm(stray))
        self.assertEqual(_er_fm(self.a)["milestone"], MILESTONE)
        self.assertEqual(self.errors(), [])


class TestCommitTimeCheck(_ErRepo):

    def test_blocks_only_problems_the_staged_change_introduces(self):
        # A pre-existing dangling reference is committed first.
        old = _er_write(self.root, ".along/ISSUES/feat--gamma-task.md",
                        _er_issue("gamma-task", related=["feat--long-gone-task"]))
        self.commit_all()
        _er_git(self.root, "rm", "-q", os.path.relpath(self.a, self.root).replace("\\", "/"))
        staged = _er_git(self.root, "diff", "--cached", "--name-only").stdout.splitlines()
        violations = gitgates.check_entity_references(self.root, staged, "git", "index", "HEAD")
        locations = sorted({v.location for v in violations})
        self.assertEqual(locations, [".along/ISSUES/feat--beta-task.md",
                                     f".along/MILESTONES/{MILESTONE}.md",
                                     ".along/SESSIONS/2026/2026-09-30--fixture-session.md"])
        self.assertTrue(all(v.gate == "entity_reference_integrity" for v in violations))
        self.assertFalse(any("long-gone" in v.message for v in violations), old)

    def test_pre_commit_includes_the_check_and_skips_unrelated_changes(self):
        self.commit_all()
        _er_write(self.root, "src/app.py", "print('x')\n")
        _er_git(self.root, "add", "-A")
        self.assertEqual([v for v in gitgates.check_pre_commit(self.root)
                          if v.gate == "entity_reference_integrity"], [])
        _er_write(self.root, self.b[len(self.root) + 1:].replace("\\", "/"),
                  _er_issue("beta-task", related=["feat--missing-task"]))
        _er_git(self.root, "add", "-A")
        found = [v for v in gitgates.check_pre_commit(self.root)
                 if v.gate == "entity_reference_integrity"]
        self.assertEqual(len(found), 1)
        self.assertIn("feat--missing-task", found[0].message)


class TestRenameAndSupersede(_ErRepo):

    def test_rename_rewrites_every_inbound_reference(self):
        result = entities.rename_issue(self.root, "feat--alpha-task", "bug--alpha-renamed")
        new_path = os.path.join(self.root, ".along", "ISSUES", "bug--alpha-renamed.md")
        self.assertFalse(os.path.exists(self.a))
        self.assertEqual(os.path.abspath(result["file_path"]), os.path.abspath(new_path))
        self.assertEqual(_er_fm(new_path)["slug"], "alpha-renamed")
        self.assertEqual(_er_fm(new_path)["type"], "bug")
        beta = _er_fm(self.b)
        self.assertEqual(list(beta["related"]), ["bug--alpha-renamed"])
        self.assertEqual(list(beta["blocked_by"]), ["bug--alpha-renamed"])
        self.assertIn("bug--alpha-renamed", list(_er_fm(self.m)["target_issues"]))
        self.assertEqual(list(_er_fm(self.s)["issues_completed"]), ["bug--alpha-renamed"])
        self.assertEqual(self.errors(), [])

    def test_rename_refuses_an_existing_key(self):
        with self.assertRaises(ValueError):
            entities.rename_issue(self.root, "alpha-task", "feat--beta-task")

    def test_supersede_keeps_the_file_and_moves_live_references(self):
        _er_write(self.root, ".along/ISSUES/feat--delta-task.md", _er_issue("delta-task"))
        entities.supersede_issue(self.root, "feat--alpha-task", "feat--delta-task")
        done = os.path.join(self.root, ".along", "ISSUES", "done", "feat--alpha-task.md")
        self.assertFalse(os.path.exists(self.a))
        old = _er_fm(done)
        self.assertEqual(old["status"], "superseded")
        self.assertEqual(old["superseded_by"], "feat--delta-task")
        beta = _er_fm(self.b)
        self.assertEqual(list(beta["related"]), ["feat--delta-task"])
        self.assertEqual(list(beta["blocked_by"]), ["feat--delta-task"])
        # History still names the old issue, which still exists.
        self.assertEqual(list(_er_fm(self.s)["issues_completed"]), ["feat--alpha-task"])
        self.assertEqual(self.errors(), [])

    def test_cli_rename_and_supersede(self):
        run = lambda *a: subprocess.run([sys.executable, EXEC, "issue", *a], cwd=self.root,
                                        capture_output=True, text=True, encoding="utf-8")
        renamed = run("rename", "alpha-task", "feat--alpha-next")
        self.assertEqual(renamed.returncode, 0, renamed.stderr)
        self.assertIn("Rewrote inbound references", renamed.stdout)
        missing = run("supersede", "feat--alpha-next")
        self.assertNotEqual(missing.returncode, 0)
        superseded = run("supersede", "feat--beta-task", "--by", "feat--alpha-next")
        self.assertEqual(superseded.returncode, 0, superseded.stderr)
        self.assertEqual(self.errors(), [])


class TestMilestoneSync(_ErRepo):

    def test_issue_create_adds_key_to_milestone_targets(self):
        result = subprocess.run(
            [sys.executable, EXEC, "issue", "create", "feat", "epsilon-task", "--milestone", MILESTONE],
            cwd=self.root, capture_output=True, text=True, encoding="utf-8")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("feat--epsilon-task", list(_er_fm(self.m)["target_issues"]))

    def test_open_issues_are_counted_from_status(self):
        milestone = entities.resolve_milestone_by_query(self.root, MILESTONE)
        open_keys, total = entities.milestone_open_issues(self.root, milestone)
        self.assertEqual((open_keys, total), (["feat--alpha-task", "feat--beta-task"], 2))


class TestReleaseRefusesOpenMilestone(_ErRepo):

    def setUp(self):
        super().setUp()
        import importlib
        self.bump = importlib.import_module("along_version_bump")
        _er_write(self.root, ".along/MILESTONES/v9.2.0-next-release.md",
                  _er_milestone(slug="v9.2.0-next-release", status="open"))

    def test_open_issues_abort_the_release(self):
        tx = transaction.FileTransaction(self.root, "t")
        with self.assertRaises(self.bump.ReleaseAborted) as ctx:
            self.bump.update_along_milestones(self.root, "9.1.0", tx)
        self.assertIn("feat--alpha-task", str(ctx.exception))
        tx.rollback()
        self.assertEqual(_er_fm(self.m)["status"], "in-progress")

    def test_carry_over_moves_open_issues_and_completes(self):
        _er_write(self.root, ".along/ISSUES/done/feat--zeta-task.md", _er_issue("zeta-task", status="done"))
        tx = transaction.FileTransaction(self.root, "t")
        self.bump.update_along_milestones(self.root, "9.1.0", tx, carry_over="v9.2.0-next-release")
        tx.commit()
        released = _er_fm(self.m)
        self.assertEqual(released["status"], "completed")
        self.assertEqual(released["progress_pct"], 100)
        self.assertEqual(list(released["target_issues"]), [])
        self.assertEqual(_er_fm(self.a)["milestone"], "v9.2.0-next-release")
        nxt = _er_fm(os.path.join(self.root, ".along", "MILESTONES", "v9.2.0-next-release.md"))
        self.assertEqual(sorted(nxt["target_issues"]), ["feat--alpha-task", "feat--beta-task"])


class TestMigrationMilestones(unittest.TestCase):
    """[bug--migration-dangling-template-milestones] REQ-1..REQ-3, REQ-5."""

    def setUp(self):
        import migrate_protocol
        from alongkit import migration
        self.mp = migrate_protocol
        self.migration = migration
        self.root = tempfile.mkdtemp(prefix="along_mig_milestones_")
        os.makedirs(os.path.join(self.root, ".git"))
        self.along = os.path.join(self.root, ".along")
        _er_write(self.root, ".along/MILESTONES/v1.0.0-first-release.md",
                  _er_milestone(slug="v1.0.0-first-release", status="completed"))
        self.closed = _er_write(self.root, ".along/ISSUES/done/feat--closed-task.md",
                                "---\nprotocol: along\nslug: closed-task\ntype: feat\nstatus: done\n"
                                "priority: medium\ncreated: 2026-09-01\nupdated: 2026-09-02\n"
                                "completed: 2026-09-02\n---\n\n# Closed\n")
        self.open = _er_write(self.root, ".along/ISSUES/feat--open-task.md",
                              "---\nprotocol: along\nslug: open-task\ntype: feat\nstatus: open\n"
                              "priority: medium\ncreated: 2026-09-01\nupdated: 2026-09-01\n---\n\n# Open\n")
        self.session = _er_write(self.root, ".along/SESSIONS/2026/2026-09-02--work.md",
                                 "---\nprotocol: along\nslug: work\ndate: 2026-09-02\n---\n\n# Work\n")

    def tearDown(self):
        shutil.rmtree(self.root, ignore_errors=True)

    def migrate(self):
        mig = self.migration.Migration(self.root, dry_run=False, printer=lambda _m: None)
        self.mp.step_migrate_v1_5_entity_ecosystem(mig, self.root, self.along)

    def milestone_errors(self):
        return [e for e in entities.validate_entities(self.root)["errors"]
                if "milestone" in e[1]]

    def test_no_milestone_is_invented(self):
        self.migrate()
        self.assertEqual(self.milestone_errors(), [])
        for path in (self.closed, self.open, self.session):
            self.assertNotIn("milestone", _er_fm(path))
        milestones = sorted(os.listdir(os.path.join(self.along, "MILESTONES")))
        self.assertEqual(milestones, ["v1.0.0-first-release.md"])

    def test_dangling_template_references_are_repaired_idempotently(self):
        for path, slug in ((self.closed, "v1.3.0-knowledge-base-and-graph"),
                           (self.session, "v2.0.0-along-transition")):
            textio.write_text(path, frontmatter.update(textio.read_text(path), {"milestone": slug}))
        textio.write_text(self.open, frontmatter.update(textio.read_text(self.open),
                                                        {"milestone": "v1.0.0-first-release"}))
        self.migrate()
        self.assertNotIn("milestone", _er_fm(self.closed))
        self.assertNotIn("milestone", _er_fm(self.session))
        self.assertEqual(_er_fm(self.open)["milestone"], "v1.0.0-first-release")
        before = {p: textio.read_text(p) for p in (self.closed, self.open, self.session)}
        self.migrate()
        self.assertEqual(before, {p: textio.read_text(p) for p in before})
        self.assertEqual(self.milestone_errors(), [])

    def test_existing_template_milestone_is_kept(self):
        _er_write(self.root, ".along/MILESTONES/v2.0.0-along-transition.md",
                  _er_milestone(slug="v2.0.0-along-transition", status="completed"))
        textio.write_text(self.open, frontmatter.update(textio.read_text(self.open),
                                                        {"milestone": "v2.0.0-along-transition"}))
        self.migrate()
        self.assertEqual(_er_fm(self.open)["milestone"], "v2.0.0-along-transition")


class TestMigrationReusesValidator(unittest.TestCase):

    def test_no_private_dangling_logic_left(self):
        source = textio.read_text(os.path.join(SCRIPTS_DIR, "migrate_protocol.py"))
        self.assertIn("entities.validate_entities(", source)
        self.assertNotIn("external_keys", source)


if __name__ == "__main__":
    unittest.main()
