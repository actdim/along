#!/usr/bin/env python3
"""
tests/test_output_distillation.py - distilled observations for noisy command output.

Covers [feat--observation-and-telemetry-distillation]: `alongkit.distill` (success
one-liner, failure isolation, caps, ANSI / carriage-return cleanup, >= 70% token
reduction on noisy output), `proc.run_capture(distill=True)`, the telemetry span that
records only the observation while the raw output is offloaded, and the lifecycle output
mode for `along test` / `along build`. All filesystem work happens in temp directories.
"""

from __future__ import annotations

import os
import shutil
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

from alongkit import distill, lifecycle, proc


def _od_noisy_unittest_failure():
    """A realistic failing unittest run buried in resolver and deprecation chatter."""
    lines = ["-> [Along] resolving dependencies via uv: ruamel.yaml>=0.18",
             "Resolved 12 packages in 3ms", "Installed 12 packages in 40ms"]
    lines += [f"test_case_{i} (tests.test_mod.TestX.test_case_{i}) ... ok" for i in range(300)]
    lines += [f"/usr/lib/python3/site.py:{i}: DeprecationWarning: pkg_resources is deprecated"
              for i in range(40)]
    lines += [
        "=" * 70,
        "FAIL: test_math (tests.test_mod.TestX.test_math)",
        "-" * 70,
        "Traceback (most recent call last):",
        '  File "tests/test_mod.py", line 42, in test_math',
        "    self.assertEqual(add(2, 2), 5)",
        "AssertionError: 4 != 5",
        "",
        "-" * 70,
        "Ran 301 tests in 2.345s",
        "",
        "FAILED (failures=1)",
    ]
    return "\n".join(lines) + "\n"


class TestDistill(unittest.TestCase):
    def test_success_is_one_line_plus_summary(self):
        raw = "\n".join(f"test_{i} ... ok" for i in range(100)) + "\nRan 100 tests in 1.0s\n\nOK\n"
        obs = distill.distill(raw, "", 0, ["pytest", "-q"], duration=1.25)
        self.assertTrue(obs.ok)
        lines = obs.text.splitlines()
        self.assertEqual(lines[0], "PASS: pytest -q completed successfully (code 0, 1.2s)")
        self.assertIn("Ran 100 tests in 1.0s", lines)
        self.assertLessEqual(len(lines), 1 + distill.MAX_SUMMARY_LINES)

    def test_failure_isolates_assertion_and_reduces_tokens_by_70_percent(self):
        raw = _od_noisy_unittest_failure()
        obs = distill.distill(raw, "", 1, "python -m unittest")
        self.assertFalse(obs.ok)
        self.assertTrue(obs.text.startswith("FAIL: python -m unittest exited with code 1"))
        for needle in ("FAIL: test_math", 'tests/test_mod.py", line 42', "AssertionError: 4 != 5",
                       "Ran 301 tests", "FAILED (failures=1)"):
            self.assertIn(needle, obs.text)
        self.assertNotIn("DeprecationWarning", obs.text)
        self.assertNotIn("... ok", obs.text)
        reduction = 1 - distill.estimate_tokens(obs.text) / distill.estimate_tokens(raw)
        self.assertGreaterEqual(reduction, 0.70, f"only {reduction:.0%} reduction")

    def test_failure_payload_is_capped(self):
        raw = "\n".join(f"src/m.py:{i}: error: boom {i}" for i in range(500))
        obs = distill.distill(raw, "", 2, "mypy", max_lines=50, max_bytes=2048,
                              raw_ref=".along/artifacts/lifecycle/build.log")
        self.assertLessEqual(len(obs.text.splitlines()), 50)
        self.assertLessEqual(len(obs.text.encode("utf-8")), 2048)
        self.assertIn("more line(s) omitted; raw output: .along/artifacts/lifecycle/build.log", obs.text)

    def test_summary_survives_the_cap(self):
        raw = "\n".join(f"src/m.py:{i}: error: boom {i}" for i in range(500)) + "\nFound 500 errors\n"
        obs = distill.distill(raw, "", 1, "mypy", max_lines=20, max_bytes=1024)
        self.assertEqual(obs.text.splitlines()[-1], "Found 500 errors")
        self.assertLessEqual(len(obs.text.splitlines()), 20)

    def test_ansi_and_carriage_return_redraws(self):
        self.assertEqual(distill.clean_lines("\x1b[31mred\x1b[0m\n10%\r50%\r100% done"),
                         ["red", "100% done"])

    def test_unknown_failure_falls_back_to_signal_tail(self):
        raw = "\n".join(["Collecting foo", "something odd happened", "giving up"])
        obs = distill.distill(raw, "", 3, "tool")
        self.assertIn("giving up", obs.text)
        self.assertNotIn("Collecting", obs.text)

    def test_output_is_clean_ascii_for_ascii_input(self):
        obs = distill.distill(_od_noisy_unittest_failure(), "", 1, "x")
        self.assertTrue(all(ord(ch) < 128 for ch in obs.text))


class TestRunCaptureDistill(unittest.TestCase):
    def test_observation_set_and_raw_kept(self):
        code = "import sys; print('chatter\\n' * 200); sys.stderr.write('ValueError: bad\\n'); sys.exit(1)"
        res = proc.run_capture([sys.executable, "-c", code], distill=True, trip_on_anomaly=False)
        self.assertEqual(res.returncode, 1)
        self.assertIn("chatter", res.stdout)
        self.assertIn("ValueError: bad", res.observation)
        self.assertLess(len(res.observation), len(res.stdout))

    def test_default_has_no_observation(self):
        res = proc.run_capture([sys.executable, "-c", "print(1)"], trip_on_anomaly=False)
        self.assertIsNone(res.observation)


class TestSpanRecordsObservation(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="along-distill-span-")

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_span_output_is_observation_and_raw_is_offloaded(self):
        from alongkit.telemetry import conventions
        from alongkit.telemetry.tracer import Tracer

        tracer = Tracer(self.tmp, auto_flush=False)
        with tracer.tool_span("run_command") as span:
            tracer.record_command_result(span=span, cmd=["x"], exit_code=1,
                                         stdout="short raw output", observation="FAIL: x")
            attrs = dict(span.attributes)
        self.assertEqual(attrs[conventions.OUTPUT_VALUE], "FAIL: x")
        self.assertTrue(attrs[conventions.ALONG_ARTIFACT_OFFLOADED])
        artifact = os.path.join(self.tmp, *attrs[conventions.ALONG_ARTIFACT_REF].split("/"))
        with open(artifact, encoding="utf-8") as handle:
            self.assertEqual(handle.read(), "short raw output")


class TestLifecycleOutputMode(unittest.TestCase):
    def test_precedence(self):
        with mock.patch.dict(os.environ, {lifecycle.OUTPUT_MODE_ENV: ""}):
            self.assertEqual(lifecycle.resolve_output_mode("test", ["-q"], stdout_isatty=False),
                             ("distill", ["-q"]))
            self.assertEqual(lifecycle.resolve_output_mode("test", ["-q"], stdout_isatty=True),
                             ("raw", ["-q"]))
            self.assertEqual(lifecycle.resolve_output_mode("dev", [], stdout_isatty=False), ("raw", []))
            self.assertEqual(lifecycle.resolve_output_mode("test", ["--raw", "-q"], stdout_isatty=False),
                             ("raw", ["-q"]))
            self.assertEqual(lifecycle.resolve_output_mode("build", ["--distill"], stdout_isatty=True),
                             ("distill", []))
        with mock.patch.dict(os.environ, {lifecycle.OUTPUT_MODE_ENV: "raw"}):
            self.assertEqual(lifecycle.resolve_output_mode("test", [], stdout_isatty=False), ("raw", []))

    def test_distilled_run_prints_observation_and_keeps_raw_log(self):
        tmp = tempfile.mkdtemp(prefix="along-distill-life-")
        try:
            code = "import sys; print('noise\\n' * 100); print('Ran 3 tests in 0.1s'); print('OK')"
            with mock.patch("builtins.print") as fake_print:
                rc = lifecycle.run_lifecycle_command("test", [sys.executable, "-c", code], tmp, "distill")
            self.assertEqual(rc, 0)
            printed = "\n".join(str(c.args[0]) for c in fake_print.call_args_list if c.args)
            self.assertIn("PASS:", printed)
            self.assertIn("Ran 3 tests", printed)
            self.assertNotIn("noise\nnoise", printed)
            self.assertLess(len(printed.splitlines()), 10)
            with open(lifecycle.raw_log_path(tmp, "test"), encoding="utf-8") as handle:
                self.assertIn("noise", handle.read())
        finally:
            shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
