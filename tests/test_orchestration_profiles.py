#!/usr/bin/env python3
"""
tests/test_orchestration_profiles.py - Hermetic tests for orchestration profiles and resolution.
"""

from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPTS_DIR = os.path.join(REPO_ROOT, "scripts")
if SCRIPTS_DIR not in sys.path:
    sys.path.insert(0, SCRIPTS_DIR)

from alongkit import orchestration_profiles, orchestrator


class TestOrchestrationProfiles(unittest.TestCase):
    def test_list_profile_names_includes_builtins(self) -> None:
        names = orchestration_profiles.list_profile_names()
        self.assertIn("direct", names)
        self.assertIn("team-native", names)
        self.assertIn("cross-tiered", names)

    def test_builtin_profiles_are_valid(self) -> None:
        for name in ("direct", "team-native", "cross-tiered"):
            profile = orchestration_profiles.resolve_orchestration_profile(name)
            self.assertEqual(profile["name"], name)
            valid, errors = orchestration_profiles.validate_profile_dict(profile)
            self.assertTrue(valid, f"Built-in profile '{name}' failed validation: {errors}")

    def test_load_custom_profile_from_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            pdir = orchestration_profiles.get_profiles_dir(tmpdir)
            os.makedirs(pdir, exist_ok=True)
            custom_file = os.path.join(pdir, "custom-deepseek.json")
            with open(custom_file, "w", encoding="utf-8") as f:
                json.dump(
                    {
                        "name": "custom-deepseek",
                        "mode": "cross-runtime",
                        "workspace": "worktree",
                        "timeout": 2400,
                        "roles": {
                            "scout": {"runtime": "claude-code", "model": "claude-3-7-sonnet"},
                            "architect": {"runtime": "claude-code", "model": "claude-3-7-sonnet"},
                            "implementer": {"runtime": "opencode", "model": "deepseek-coder"},
                            "reviewer": {"runtime": "codex", "model": "o3-mini"},
                        },
                    },
                    f,
                )

            names = orchestration_profiles.list_profile_names(repo_root=tmpdir)
            self.assertIn("custom-deepseek", names)

            resolved = orchestration_profiles.resolve_orchestration_profile("custom-deepseek", repo_root=tmpdir)
            self.assertEqual(resolved["name"], "custom-deepseek")
            self.assertEqual(resolved["mode"], "cross-runtime")
            self.assertEqual(resolved["workspace"], "worktree")
            self.assertEqual(resolved["roles"]["implementer"]["runtime"], "opencode")
            self.assertEqual(resolved["roles"]["reviewer"]["runtime"], "codex")

    def test_validation_rejects_invalid_runtime_or_mode(self) -> None:
        bad_profile = {
            "name": "bad",
            "mode": "invalid-mode",
            "roles": {
                "scout": {"runtime": "non-existent-runner"},
            },
        }
        valid, errors = orchestration_profiles.validate_profile_dict(bad_profile)
        self.assertFalse(valid)
        self.assertTrue(any("invalid-mode" in err.lower() for err in errors))

    def test_overrides_cascade(self) -> None:
        profile = orchestration_profiles.resolve_orchestration_profile(
            "cross-tiered",
            overrides={"model": "test-override-model", "timeout": 999},
        )
        for r_name in orchestration_profiles.SUPPORTED_ROLES:
            self.assertEqual(profile["roles"][r_name]["model"], "test-override-model")
            self.assertEqual(profile["roles"][r_name]["timeout"], 999)

    def test_orchestrator_load_role_config_with_profile(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            pdir = orchestration_profiles.get_profiles_dir(tmpdir)
            os.makedirs(pdir, exist_ok=True)
            custom_file = os.path.join(pdir, "hybrid.json")
            with open(custom_file, "w", encoding="utf-8") as f:
                json.dump(
                    {
                        "name": "hybrid",
                        "mode": "cross-runtime",
                        "roles": {
                            "scout": {"runtime": "claude-code"},
                            "architect": {"runtime": "claude-code"},
                            "implementer": {"runtime": "opencode"},
                            "reviewer": {"runtime": "codex"},
                        },
                    },
                    f,
                )

            role_cfg = orchestrator.load_role_config(repo_root=tmpdir, profile="hybrid")
            self.assertEqual(role_cfg["implementer"]["runtime"], "opencode")
            self.assertEqual(role_cfg["reviewer"]["runtime"], "codex")


if __name__ == "__main__":
    unittest.main()
