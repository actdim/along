#!/usr/bin/env python3
"""
tests/test_profiles.py - Hermetic tests for gate strictness profiles engine.

Covers [feat--gate-strictness-profiles] REQ-1, REQ-4:
- Named profiles validation (strict, standard, light).
- Resolution hierarchy: session binding > ALONG_PROFILE > config.json/yaml > default standard.
- along start --profile flag integration.
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

from alongkit import profiles, session, textio
from hermetic import make_repo_fixture

CLEAN_ENV = {k: v for k, v in os.environ.items()
             if k not in session.SESSION_ENV_VARS and k != "ALONG_PROFILE"}
KEY = session.session_key("generic", "sess-prof")


class TestProfilesBasics(unittest.TestCase):
    def test_constants_and_validation(self):
        self.assertEqual(profiles.DEFAULT_PROFILE, "standard")
        self.assertEqual(profiles.validate_profile("strict"), "strict")
        self.assertEqual(profiles.validate_profile("standard"), "standard")
        self.assertEqual(profiles.validate_profile("light"), "light")
        self.assertEqual(profiles.validate_profile("  LIGHT  "), "light")
        self.assertEqual(profiles.validate_profile(None), "standard")
        self.assertEqual(profiles.validate_profile(""), "standard")

        with self.assertRaises(ValueError):
            profiles.validate_profile("ultra-hardcore")

    def test_normalize_profile(self):
        self.assertEqual(profiles.normalize_profile("strict"), "strict")
        self.assertEqual(profiles.normalize_profile("unknown"), "standard")
        self.assertEqual(profiles.normalize_profile(None, default="light"), "light")


class TestProfileResolutionHierarchy(unittest.TestCase):
    def setUp(self):
        self.env = mock.patch.dict(os.environ, dict(CLEAN_ENV, ALONG_SESSION_ID="sess-prof"), clear=True)
        self.env.start()
        self.root = make_repo_fixture(prefix="along-prof-", with_docs=False)

    def tearDown(self):
        self.env.stop()
        shutil.rmtree(self.root, ignore_errors=True)

    def test_default_resolution_is_standard(self):
        prof, source = profiles.resolve_active_profile_with_source(self.root, session_key=KEY)
        self.assertEqual(prof, "standard")
        self.assertEqual(source, profiles.SOURCE_DEFAULT)
        self.assertEqual(profiles.resolve_active_profile(self.root, session_key=KEY), "standard")

    def test_config_json_top_level_profile(self):
        config_path = os.path.join(self.root, ".along", "config.json")
        textio.write_text(config_path, json.dumps({"profile": "light"}))

        prof, source = profiles.resolve_active_profile_with_source(self.root, session_key=KEY)
        self.assertEqual(prof, "light")
        self.assertEqual(source, profiles.SOURCE_CONFIG)

    def test_config_json_nested_hooks_profile(self):
        config_path = os.path.join(self.root, ".along", "config.json")
        textio.write_text(config_path, json.dumps({"hooks": {"profile": "strict"}}))

        prof, source = profiles.resolve_active_profile_with_source(self.root, session_key=KEY)
        self.assertEqual(prof, "strict")
        self.assertEqual(source, profiles.SOURCE_CONFIG)

    def test_env_var_overrides_config(self):
        config_path = os.path.join(self.root, ".along", "config.json")
        textio.write_text(config_path, json.dumps({"profile": "light"}))

        with mock.patch.dict(os.environ, {"ALONG_PROFILE": "strict"}):
            prof, source = profiles.resolve_active_profile_with_source(self.root, session_key=KEY)
            self.assertEqual(prof, "strict")
            self.assertEqual(source, profiles.SOURCE_ENV)

    def test_session_binding_overrides_env_and_config(self):
        config_path = os.path.join(self.root, ".along", "config.json")
        textio.write_text(config_path, json.dumps({"profile": "strict"}))

        # Bind session with profile 'light'
        session.init_session(self.root, "my-issue", profile="light")
        session.bind_session(self.root, "my-issue", key=KEY, profile="light")

        with mock.patch.dict(os.environ, {"ALONG_PROFILE": "strict"}):
            prof, source = profiles.resolve_active_profile_with_source(self.root, session_key=KEY)
            self.assertEqual(prof, "light")
            self.assertEqual(source, profiles.SOURCE_SESSION)
            self.assertEqual(session.get_session_profile(self.root, key=KEY), "light")


class TestAlongStartProfile(unittest.TestCase):
    def setUp(self):
        self.env = mock.patch.dict(os.environ, dict(CLEAN_ENV, ALONG_SESSION_ID="sess-prof-cli"), clear=True)
        self.env.start()
        self.root = make_repo_fixture(prefix="along-start-prof-", with_docs=False)

    def tearDown(self):
        self.env.stop()
        shutil.rmtree(self.root, ignore_errors=True)

    def test_along_start_with_profile_flag(self):
        from along_exec import handle_start_command
        # Create an issue
        issue_path = os.path.join(self.root, ".along", "ISSUES", "feat--test-cli-prof.md")
        textio.write_text(issue_path, "---\nslug: test-cli-prof\ntype: feat\nstatus: open\n---\n# Test\n")

        with self.assertRaises(SystemExit) as cm:
            handle_start_command(self.root, ["test-cli-prof", "--profile", "strict"])
        self.assertEqual(cm.exception.code, 0)

        key = session.current_session_key()
        binding = session.load_binding(self.root, key)
        self.assertIsNotNone(binding)
        self.assertEqual(binding.get("profile"), "strict")

        st = session.load_state(self.root, "test-cli-prof")
        self.assertIsNotNone(st)
        self.assertEqual(st.get("profile"), "strict")

        prof = profiles.resolve_active_profile(self.root, session_key=key)
        self.assertEqual(prof, "strict")


if __name__ == "__main__":
    unittest.main()
