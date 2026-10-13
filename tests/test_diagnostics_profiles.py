#!/usr/bin/env python3
"""
tests/test_diagnostics_profiles.py - Hermetic tests for profile diagnostics and CLI visibility.

Covers [feat--gate-strictness-profiles] REQ-5:
- along doctor displays active profile, resolution source, and gate strictness matrix.
- along hook verify (audit_traceability / format_traceability_report) displays active profile,
  source, and strictness matrix per gate.
"""

from __future__ import annotations

import io
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
from alongkit.hooks import traceability
from hermetic import make_repo_fixture

CLEAN_ENV = {k: v for k, v in os.environ.items()
             if k not in session.SESSION_ENV_VARS and k != "ALONG_PROFILE"}


class TestTraceabilityProfileDiagnostics(unittest.TestCase):
    def test_traceability_report_carries_profile_and_source(self):
        report = traceability.audit_traceability(REPO_ROOT)
        self.assertIsNotNone(report.active_profile)
        self.assertIn(report.active_profile, ("strict", "standard", "light"))
        self.assertIn(report.profile_source, ("session", "env", "config", "default"))
        self.assertGreater(len(report.gate_profiles), 0)

        rendered = traceability.format_traceability_report(report)
        self.assertIn(f"Active Profile:      {report.active_profile}", rendered)
        self.assertIn(f"(source: {report.profile_source})", rendered)
        self.assertIn("[Enforcement Matrix]", rendered)

    def test_traceability_report_reflects_env_profile(self):
        with mock.patch.dict(os.environ, {"ALONG_PROFILE": "light"}):
            report = traceability.audit_traceability(REPO_ROOT)
            self.assertEqual(report.active_profile, "light")
            self.assertEqual(report.profile_source, "env")

            rendered = traceability.format_traceability_report(report)
            self.assertIn("Active Profile:      light (source: env)", rendered)
            # require_plan_approval is warn under light profile
            self.assertIn("require_plan_approval        [WARN ]", rendered)
            # require_active_issue is block under all profiles
            self.assertIn("require_active_issue         [BLOCK]", rendered)


class TestDoctorProfileOutput(unittest.TestCase):
    def setUp(self):
        self.env = mock.patch.dict(os.environ, dict(CLEAN_ENV, ALONG_SESSION_ID="sess-doc-prof"), clear=True)
        self.env.start()
        self.root = make_repo_fixture(prefix="along-doc-prof-", with_docs=False)

    def tearDown(self):
        self.env.stop()
        shutil.rmtree(self.root, ignore_errors=True)

    def _run_doctor(self, args=None) -> str:
        from along_exec import handle_doctor_command
        buf = io.StringIO()
        with mock.patch("sys.stdout", buf):
            with self.assertRaises(SystemExit) as cm:
                handle_doctor_command(self.root, args or [])
        return buf.getvalue()

    def test_doctor_prints_default_profile_and_matrix(self):
        out = self._run_doctor()
        self.assertIn("--- Gate Strictness Profile: standard (source: default) ---", out)
        self.assertIn("[OK] Gate strictness profile: standard (source: default)", out)
        self.assertIn("Gate strictness matrix", out)
        self.assertIn("require_active_issue         [BLOCK]", out)

    def test_doctor_reflects_config_profile(self):
        cfg_path = os.path.join(self.root, ".along", "config.json")
        textio.write_text(cfg_path, json.dumps({"profile": "light"}))

        out = self._run_doctor()
        self.assertIn("--- Gate Strictness Profile: light (source: config) ---", out)
        self.assertIn("[OK] Gate strictness profile: light (source: config)", out)
        self.assertIn("require_plan_approval        [WARN]", out)
        self.assertIn("require_active_issue         [BLOCK]", out)

    def test_doctor_reflects_env_profile_override(self):
        cfg_path = os.path.join(self.root, ".along", "config.json")
        textio.write_text(cfg_path, json.dumps({"profile": "light"}))

        with mock.patch.dict(os.environ, {"ALONG_PROFILE": "strict"}):
            out = self._run_doctor()
            self.assertIn("--- Gate Strictness Profile: strict (source: env) ---", out)
            self.assertIn("[OK] Gate strictness profile: strict (source: env)", out)


if __name__ == "__main__":
    unittest.main(verbosity=2)
