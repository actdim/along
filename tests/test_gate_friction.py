#!/usr/bin/env python3
"""
tests/test_gate_friction.py - Bypass accountability, gate tiers and gate statistics.

Covers [feat--gate-friction-and-bypass-accountability] REQ-3..REQ-5: a bypass needs a reason
and, where user messages are recorded, the user's reply after the gate failed; it is
recorded (trace, audit log, commit trailer). Invariant gates ignore shadow overrides and
`enabled: false`. `along gates stats` counts blocks, warnings and bypasses per gate.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import unittest
from unittest import mock

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPTS_DIR = os.path.join(REPO_ROOT, "scripts")
if SCRIPTS_DIR not in sys.path:
    sys.path.insert(0, SCRIPTS_DIR)

from alongkit import bootstrap
bootstrap.ensure_deps()

from alongkit import bypass, gatestats, session, textio
from alongkit.hooks import config as hook_config
from alongkit.hooks.declarative import load_gate_entries
from hermetic import make_repo_fixture

COMMIT = os.path.join(SCRIPTS_DIR, "along_commit.py")
CLEAN_ENV = {k: v for k, v in os.environ.items() if k not in session.SESSION_ENV_VARS}
KEY = session.session_key("generic", "sess-g")


class _FrictionFixture(unittest.TestCase):
    def setUp(self):
        self.env = mock.patch.dict(os.environ, dict(CLEAN_ENV, ALONG_SESSION_ID="sess-g"), clear=True)
        self.env.start()
        self.root = make_repo_fixture(prefix="along-friction-", with_docs=False)

    def tearDown(self):
        self.env.stop()
        shutil.rmtree(self.root, ignore_errors=True)


class TestBypassAuthorization(_FrictionFixture):
    def test_reason_is_required(self):
        refusal, _ = bypass.authorize(self.root, bypass.PRE_COMMIT, "  ", key=KEY)
        self.assertIn("needs a reason", refusal)

    def test_without_recorded_user_messages_the_bypass_is_unverified(self):
        self.assertEqual(bypass.authorize(self.root, bypass.PRE_COMMIT, "r", key=KEY), (None, bypass.UNVERIFIED))

    def test_needs_a_failure_and_a_user_reply_after_it(self):
        session.record_user_prompt(self.root, KEY, "2000-01-01T00:00:00Z")
        refusal, _ = bypass.authorize(self.root, bypass.PRE_COMMIT, "r", key=KEY)
        self.assertIn("has not failed", refusal)
        bypass.record_failure(self.root, bypass.PRE_COMMIT, KEY)
        refusal, _ = bypass.authorize(self.root, bypass.PRE_COMMIT, "r", key=KEY)
        self.assertIn("no user reply", refusal)
        session.record_user_prompt(self.root, KEY, "2999-01-01T00:00:00Z")
        self.assertEqual(bypass.authorize(self.root, bypass.PRE_COMMIT, "r", key=KEY), (None, bypass.VERIFIED))

    def test_record_writes_audit_entry_and_trailer(self):
        trailer = bypass.record(self.root, bypass.TESTS, "flaky CI runner", bypass.UNVERIFIED, key=KEY)
        self.assertEqual(trailer, "Along-Bypass: tests; unverified; flaky CI runner")
        rows = gatestats.collect(self.root)
        self.assertEqual([(r.gate, r.bypassed) for r in rows], [("tests", 1)])

    def test_team_step_denial_counts_as_a_failure(self):
        bypass.record_hook_denial(self.root, "team_step_active", KEY)
        session.record_user_prompt(self.root, KEY, "2999-01-01T00:00:00Z")
        self.assertEqual(bypass.authorize(self.root, bypass.TEAM_STEPS, "r", key=KEY)[0], None)


class TestCommitBypass(_FrictionFixture):
    def setUp(self):
        super().setUp()
        for args in (["init", "-q"], ["config", "user.email", "t@example.com"], ["config", "user.name", "t"]):
            subprocess.run(["git", *args], cwd=self.root, check=True, capture_output=True)
        textio.write_text(os.path.join(self.root, "notes.txt"), "x\n")

    def commit(self, *extra):
        return subprocess.run([sys.executable, COMMIT, "-a", "-m", "chore: x", *extra], cwd=self.root,
                              capture_output=True, text=True, encoding="utf-8")

    def test_no_verify_without_reason_is_refused(self):
        res = self.commit("-n")
        self.assertEqual(res.returncode, 2, res.stdout + res.stderr)
        self.assertIn("needs a reason", res.stderr)

    def test_no_verify_with_reason_commits_with_a_trailer(self):
        res = self.commit("-n", "--reason", "user accepted: hotfix")
        self.assertEqual(res.returncode, 0, res.stdout + res.stderr)
        body = subprocess.run(["git", "log", "-1", "--format=%B"], cwd=self.root, capture_output=True,
                              text=True, encoding="utf-8").stdout
        self.assertIn("Along-Bypass: pre-commit; unverified; user accepted: hotfix", body)


class TestGateTiers(unittest.TestCase):
    def test_invariant_and_advisory_ignore_overrides(self):
        cfg = hook_config.HooksConfig(mode="shadow", gates={"workspace_containment": "shadow",
                                                            "wrapped_work_uncommitted": "enforce"})
        self.assertTrue(cfg.is_enforcing("workspace_containment"))
        self.assertFalse(cfg.is_enforcing("wrapped_work_uncommitted"))
        self.assertFalse(cfg.is_enforcing("test_before_stop"))
        self.assertIn("test_before_stop", hook_config.HooksConfig(gates={"test_before_stop": "shadow"}).overridden_gates())

    def test_catalogue_tiers_match_the_config_table(self):
        path = os.path.join(SCRIPTS_DIR, "alongkit", "hooks", "default_gates.yaml")
        declared = {defn.id: str(raw.get("tier") or hook_config.TIER_PROCESS) for defn, raw in load_gate_entries(path)}
        for gate, tier in declared.items():
            with self.subTest(gate=gate):
                self.assertEqual(hook_config.gate_tier(gate), tier)

    def test_invariant_gate_cannot_be_disabled_by_repo_entry(self):
        from alongkit.hooks.declarative import get_all_declarative_gates
        root = make_repo_fixture(prefix="along-tier-", with_docs=False)
        try:
            os.makedirs(os.path.join(root, ".along", "rules"), exist_ok=True)
            textio.write_text(os.path.join(root, ".along", "rules", "gates.yaml"),
                              "version: 1\ngates:\n  - id: workspace_containment\n    enabled: false\n"
                              "  - id: fast_retrieval\n    enabled: false\n")
            names = {g.name for g in get_all_declarative_gates(repo_root=root)}
            self.assertIn("workspace_containment", names)
            self.assertNotIn("fast_retrieval", names)
        finally:
            shutil.rmtree(root, ignore_errors=True)


class TestGateStats(_FrictionFixture):
    def test_counts_blocks_warnings_and_bypasses(self):
        path = os.path.join(self.root, ".along", "diagnostics", "hooks_audit.jsonl")
        os.makedirs(os.path.dirname(path), exist_ok=True)
        rows = [{"gate": "cli_safety", "decision": "deny", "mode": "enforce", "timestamp": "2026-10-11T00:00:00Z"},
                {"gate": "cli_safety", "decision": "deny", "mode": "enforce", "timestamp": "2026-10-11T00:00:00Z"},
                {"gate": "cli_safety", "decision": "bypass", "mode": "verified", "timestamp": "2026-10-11T00:00:00Z"},
                {"gate": "wrapped_work_uncommitted", "decision": "deny", "mode": "shadow", "timestamp": "2026-10-11T00:00:00Z"},
                {"gate": "old", "decision": "deny", "mode": "enforce", "timestamp": "2020-01-01T00:00:00Z"}]
        textio.write_text(path, "".join(json.dumps(r) + "\n" for r in rows))
        stats = {r.gate: r for r in gatestats.collect(self.root, since="2026-01-01")}
        self.assertEqual((stats["cli_safety"].blocked, stats["cli_safety"].bypassed), (2, 1))
        self.assertEqual(stats["wrapped_work_uncommitted"].warned, 1)
        self.assertNotIn("old", stats)
        self.assertEqual([r.gate for r in gatestats.most_bypassed(list(stats.values()))], ["cli_safety"])
        self.assertIn("bypass%", gatestats.format_table(list(stats.values())))


if __name__ == "__main__":
    unittest.main(verbosity=2)
