#!/usr/bin/env python3
"""
tests/test_gate_profiles.py - Hermetic tests for gate strictness profiles per model tier.

Covers [feat--gate-strictness-profiles] REQ-2:
- Gates declare strictness profiles (strict / standard / light) with severity block / warn / off.
- State-layer gates and invariant gates remain enforcing (block) across all profiles.
- Procedural gates adapt their enforcement mode according to active profile.
- Disabled/off gates are skipped during evaluation.
- Profile resolution integrates into HooksConfig and HookEngine.
"""

from __future__ import annotations

import json
import os
import shutil
import sys
import unittest
from unittest import mock

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPTS_DIR = os.path.join(REPO_ROOT, "scripts")
if SCRIPTS_DIR not in sys.path:
    sys.path.insert(0, SCRIPTS_DIR)

from alongkit import bootstrap
bootstrap.ensure_deps()

from alongkit import session, textio
from alongkit.hooks import config as hook_config
from alongkit.hooks.declarative import load_gate_entries, get_all_declarative_gates
from hermetic import make_repo_fixture

CLEAN_ENV = {k: v for k, v in os.environ.items()
             if k not in session.SESSION_ENV_VARS and k != "ALONG_PROFILE"}
KEY = session.session_key("generic", "sess-gate-prof")


class TestGateProfilesCatalogue(unittest.TestCase):
    def test_all_catalogue_gates_declare_profiles(self):
        path = os.path.join(SCRIPTS_DIR, "alongkit", "hooks", "default_gates.yaml")
        entries = load_gate_entries(path)
        self.assertGreaterEqual(len(entries), 30)

        for defn, raw in entries:
            with self.subTest(gate=defn.id):
                profiles = defn.profiles or raw.get("profiles")
                self.assertIsNotNone(profiles, f"Gate '{defn.id}' must declare 'profiles:' block")
                self.assertIn("strict", profiles, f"Gate '{defn.id}' missing 'strict' profile")
                self.assertIn("standard", profiles, f"Gate '{defn.id}' missing 'standard' profile")
                self.assertIn("light", profiles, f"Gate '{defn.id}' missing 'light' profile")
                for prof_name in ("strict", "standard", "light"):
                    sev = profiles[prof_name]
                    self.assertIn(sev, ("block", "warn", "off"),
                                  f"Gate '{defn.id}' invalid severity '{sev}' for profile '{prof_name}'")

    def test_state_layer_and_invariant_gates_stay_block_across_all_profiles(self):
        path = os.path.join(SCRIPTS_DIR, "alongkit", "hooks", "default_gates.yaml")
        entries = load_gate_entries(path)
        entry_map = {defn.id: defn for defn, _ in entries}

        for gate_name in hook_config.STATE_LAYER_GATES:
            with self.subTest(state_layer_gate=gate_name):
                defn = entry_map.get(gate_name)
                self.assertIsNotNone(defn, f"State-layer gate '{gate_name}' must exist in default gates")
                self.assertEqual(defn.profiles.get("strict"), "block")
                self.assertEqual(defn.profiles.get("standard"), "block")
                self.assertEqual(defn.profiles.get("light"), "block")

        for defn, raw in entries:
            tier = raw.get("tier") or hook_config.gate_tier(defn.id)
            if tier == hook_config.TIER_INVARIANT:
                with self.subTest(invariant_gate=defn.id):
                    self.assertEqual(defn.profiles.get("strict"), "block")
                    self.assertEqual(defn.profiles.get("standard"), "block")
                    self.assertEqual(defn.profiles.get("light"), "block")


class TestHooksConfigProfiles(unittest.TestCase):
    def test_procedural_gate_adapts_to_profile(self):
        # require_plan_approval is block in strict/standard, warn in light
        cfg_strict = hook_config.HooksConfig(profile="strict")
        self.assertTrue(cfg_strict.is_enforcing("require_plan_approval"))
        self.assertEqual(cfg_strict.get_gate_mode("require_plan_approval"), hook_config.HookMode.ENFORCE)

        cfg_std = hook_config.HooksConfig(profile="standard")
        self.assertTrue(cfg_std.is_enforcing("require_plan_approval"))
        self.assertEqual(cfg_std.get_gate_mode("require_plan_approval"), hook_config.HookMode.ENFORCE)

        cfg_light = hook_config.HooksConfig(profile="light")
        self.assertFalse(cfg_light.is_enforcing("require_plan_approval"))
        self.assertEqual(cfg_light.get_gate_mode("require_plan_approval"), hook_config.HookMode.SHADOW)

    def test_state_layer_gate_enforces_in_all_profiles(self):
        for prof in ("strict", "standard", "light"):
            cfg = hook_config.HooksConfig(profile=prof)
            for gate in hook_config.STATE_LAYER_GATES:
                with self.subTest(profile=prof, gate=gate):
                    self.assertTrue(cfg.is_enforcing(gate), f"State-layer gate '{gate}' must enforce under {prof}")
                    self.assertEqual(cfg.get_gate_mode(gate), hook_config.HookMode.ENFORCE)

    def test_custom_override_takes_precedence_unless_invariant(self):
        # A procedural gate overridden explicitly in config
        cfg = hook_config.HooksConfig(profile="standard", gates={"require_plan_approval": "shadow"})
        self.assertFalse(cfg.is_enforcing("require_plan_approval"))

        # Procedural gate elevated explicitly under light profile
        cfg_elevated = hook_config.HooksConfig(profile="light", gates={"require_plan_approval": "enforce"})
        self.assertTrue(cfg_elevated.is_enforcing("require_plan_approval"))

        # Invariant tier gate ignores shadow override across any profile
        cfg_invariant = hook_config.HooksConfig(profile="light", gates={"workspace_containment": "shadow"})
        self.assertTrue(cfg_invariant.is_enforcing("workspace_containment"))


class TestProfileIntegrationInRepo(unittest.TestCase):
    def setUp(self):
        self.env = mock.patch.dict(os.environ, dict(CLEAN_ENV, ALONG_SESSION_ID="sess-gate-prof"), clear=True)
        self.env.start()
        self.root = make_repo_fixture(prefix="along-gate-prof-", with_docs=False)

    def tearDown(self):
        self.env.stop()
        shutil.rmtree(self.root, ignore_errors=True)

    def test_load_config_picks_up_repo_profile(self):
        cfg_path = os.path.join(self.root, ".along", "config.json")
        textio.write_text(cfg_path, json.dumps({"profile": "light"}))

        config = hook_config.load_config(self.root)
        self.assertEqual(config.profile, "light")
        self.assertFalse(config.is_enforcing("require_plan_approval"))
        self.assertTrue(config.is_enforcing("require_active_issue"))

    def test_load_config_session_override(self):
        session.init_session(self.root, "my-issue", profile="light")
        session.bind_session(self.root, "my-issue", key=KEY, profile="light")

        config = hook_config.load_config(self.root)
        self.assertEqual(config.profile, "light")
        self.assertFalse(config.is_enforcing("require_plan_approval"))


if __name__ == "__main__":
    unittest.main(verbosity=2)
