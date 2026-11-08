#!/usr/bin/env python3
# Status: verified
"""
test.py - Automated Test Runner Hook for along repository.
Executes the comprehensive unit test suite via Python standard unittest.

This is the only supported entry point for this repository's suite: the tests refuse
raw `python -m unittest` / `pytest` because they need `ALONG_TEST_RUNNER`, the syntax
gate, and the resolved dependencies set up here. Pass `-q` / `--quiet` for dot output
(`npm run test:quiet`). See [bug--test-quiet-script-guard-conflict].
"""

import os
import subprocess
import sys
import time
import unittest

# The engines depend on ruamel.yaml. Resolve it before the suite imports them, so
# `python .along/scripts/test.py` works from a bare interpreter as documented.
sys.path.insert(0, os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "scripts"))
from alongkit import bootstrap, gates, testruns

# The suite also needs the `dev` group (the dashboard stack), which the shared runtime
# environment `~/.along/venv` does not carry: run inside the project environment first.
# See [bug--test-hook-lacks-dashboard-deps].
bootstrap.ensure_project_env(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    ("ruamel.yaml", "fastapi", "pydantic"))
bootstrap.ensure_deps()


class TimingTestResult(unittest.TextTestResult):
    """Tracks per-test elapsed time [feat--test-gate-cost-reduction] REQ-3."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.durations = []
        self._test_start_times = {}

    def startTest(self, test):
        super().startTest(test)
        self._test_start_times[test.id()] = time.monotonic()

    def stopTest(self, test):
        super().stopTest(test)
        start = self._test_start_times.pop(test.id(), None)
        if start is not None:
            self.durations.append((time.monotonic() - start, test.id()))


class TimingTestRunner(unittest.TextTestRunner):
    resultclass = TimingTestResult


def _normalize_test_target(target: str) -> str:
    """Normalize test target argument into discoverable pattern or dotted name.

    Converts pytest-style paths (e.g. tests/test_x.py::Class::method or
    test_x.py:Class.method) into dotted names for loadTestsFromName.
    """
    raw = target.replace("\\", "/")
    if raw.startswith("tests/"):
        raw = raw[len("tests/"):]
    elif raw.startswith("./tests/"):
        raw = raw[len("./tests/"):]
    elif raw.startswith("./"):
        raw = raw[len("./"):]

    if "::" in raw:
        parts = raw.split("::")
        mod_part = parts[0]
        if mod_part.endswith(".py"):
            mod_part = mod_part[:-3]
        mod_part = os.path.basename(mod_part)
        return ".".join([mod_part] + [p for p in parts[1:] if p])
    elif ":" in raw:
        parts = raw.split(":", 1)
        mod_part = parts[0]
        if mod_part.endswith(".py"):
            mod_part = mod_part[:-3]
        mod_part = os.path.basename(mod_part)
        rest = parts[1].replace("::", ".")
        return f"{mod_part}.{rest}" if rest else mod_part
    return raw


def _filter_suite_by_pattern(suite: unittest.TestSuite, pattern: str) -> unittest.TestSuite:
    """Filter test suite to include only tests whose ID contains the pattern substring."""
    filtered = unittest.TestSuite()
    pattern_lower = pattern.lower()
    for test in suite:
        if isinstance(test, unittest.TestSuite):
            sub = _filter_suite_by_pattern(test, pattern)
            if sub.countTestCases() > 0:
                filtered.addTest(sub)
        else:
            if type(test).__name__ == "_FailedTest":
                filtered.addTest(test)
                continue
            test_id = getattr(test, "id", None)
            if callable(test_id):
                test_id_str = test.id()
            else:
                test_id_str = str(test)
            if pattern in test_id_str or pattern_lower in test_id_str.lower():
                filtered.addTest(test)
    return filtered


def _filter_suite_exclude_integration(suite: unittest.TestSuite) -> unittest.TestSuite:
    """Filter test suite to exclude integration modules and individual integration tests."""
    from _integration import INTEGRATION_MODULES, INTEGRATION_TESTS

    filtered = unittest.TestSuite()
    for test in suite:
        if isinstance(test, unittest.TestSuite):
            sub = _filter_suite_exclude_integration(test)
            if sub.countTestCases() > 0:
                filtered.addTest(sub)
        else:
            if type(test).__name__ == "_FailedTest":
                filtered.addTest(test)
                continue
            mod = getattr(test, "__module__", "")
            if mod.startswith("tests."):
                mod = mod[len("tests."):]
            test_id = test.id() if callable(getattr(test, "id", None)) else str(test)
            if mod in INTEGRATION_MODULES or test_id in INTEGRATION_TESTS:
                continue
            filtered.addTest(test)
    return filtered


def main():
    repo_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    if repo_root not in sys.path:
        sys.path.insert(0, repo_root)

    quiet = any(arg in ("-q", "--quiet") for arg in sys.argv[1:])

    # Pre-Flight Syntax Gate: halt before test discovery if syntax errors exist
    if not gates.syntax_gate(repo_root, label="Pre-Flight Syntax Gate", quiet=quiet):
        print("[CRITICAL] Syntax validation failed before test discovery. Aborting.", file=sys.stderr)
        sys.exit(1)

    tests_dir = os.path.join(repo_root, "tests")
    if tests_dir not in sys.path:
        sys.path.insert(0, tests_dir)
    
    os.environ["ALONG_TEST_RUNNER"] = "1"
    # The suite must not see the agent session that launched it: gates bind per session id.
    from alongkit import session
    for var in session.SESSION_ENV_VARS:
        os.environ.pop(var, None)

    is_doc = any(arg in ("--doc", "--doc-tests") for arg in sys.argv[1:])

    # Parse CLI arguments for options (-q, --slowest, -k, --unit, --fast, -n) and test targets
    k_pattern = None
    is_unit = False
    xdist_workers = None
    positional_args = []
    i = 1
    while i < len(sys.argv):
        arg = sys.argv[i]
        if arg in ("-q", "--quiet", "--doc", "--doc-tests"):
            i += 1
            continue
        elif arg.startswith("--slowest="):
            i += 1
            continue
        elif arg in ("--unit", "--fast"):
            is_unit = True
            i += 1
            continue
        elif arg == "-n":
            if i + 1 < len(sys.argv):
                xdist_workers = sys.argv[i + 1]
                i += 2
                continue
            else:
                print("[Error] Option '-n' requires an argument (<count> or 'auto').", file=sys.stderr)
                sys.exit(2)
        elif arg.startswith("-n="):
            xdist_workers = arg.split("=", 1)[1]
            i += 1
            continue
        elif arg.startswith("-n") and len(arg) > 2 and not arg.startswith("-no"):
            xdist_workers = arg[2:]
            i += 1
            continue
        elif arg == "-k":
            if i + 1 < len(sys.argv):
                k_pattern = sys.argv[i + 1]
                i += 2
                continue
            else:
                print("[Error] Option '-k' requires a pattern argument.", file=sys.stderr)
                sys.exit(2)
        elif arg.startswith("-k="):
            k_pattern = arg.split("=", 1)[1]
            i += 1
            continue
        elif arg.startswith("-k") and len(arg) > 2:
            k_pattern = arg[2:]
            i += 1
            continue
        elif not arg.startswith("-"):
            positional_args.append(arg)
            i += 1
        else:
            i += 1

    if xdist_workers:
        try:
            import xdist  # noqa: F401
            has_xdist = True
        except ImportError:
            has_xdist = False

        if not has_xdist:
            print("[Notice] pytest-xdist is not installed; falling back to sequential test runner.", file=sys.stderr)
        else:
            from test_zz_hermetic_suite import porcelain_snapshot, classify_snapshot_changes
            baseline = porcelain_snapshot(repo_root)

            pytest_cmd = [
                sys.executable, "-m", "pytest",
                f"-n={xdist_workers}",
                "--dist=loadfile",
                "-p", "no:cacheprovider",
            ]
            if quiet:
                pytest_cmd.append("-q")
            if is_unit:
                pytest_cmd.extend(["-m", "not integration"])
            if k_pattern:
                pytest_cmd.extend(["-k", k_pattern])
            if positional_args:
                pytest_cmd.extend(positional_args)

            env = dict(os.environ, ALONG_TEST_RUNNER="pytest")
            res = subprocess.run(pytest_cmd, cwd=repo_root, env=env)
            if res.returncode != 0:
                sys.exit(res.returncode)

            # In full runs, execute the hermetic test serially against the pre-run baseline
            if not is_unit and not positional_args and not k_pattern and not is_doc:
                after = porcelain_snapshot(repo_root)
                if after is not None and baseline is not None:
                    report = classify_snapshot_changes(baseline, after, repo_root)
                    if report:
                        print(
                            "[Error] Hermeticity violation after parallel run:\n" + "\n".join(report),
                            file=sys.stderr,
                        )
                        sys.exit(1)

                tree = testruns.tree_hash(repo_root)
                if tree:
                    testruns.record_run(repo_root, True, tree, "test.py")

            sys.exit(0)

    loader = unittest.TestLoader()
    normalized_args = [_normalize_test_target(a) for a in positional_args]

    if is_doc:
        doc_targets = gates.get_doc_tests(repo_root)
        suite = unittest.TestSuite()
        for target in doc_targets:
            norm = _normalize_test_target(target)
            if norm.endswith(".py") or "*" in norm:
                pattern = os.path.basename(norm)
                suite.addTests(loader.discover(start_dir=tests_dir, pattern=pattern))
            else:
                suite.addTests(loader.loadTestsFromName(norm))
    elif normalized_args:
        suite = unittest.TestSuite()
        for target in normalized_args:
            if target.endswith(".py") or "*" in target:
                pattern = os.path.basename(target)
                suite.addTests(loader.discover(start_dir=tests_dir, pattern=pattern))
            else:
                suite.addTests(loader.loadTestsFromName(target))
    else:
        suite = loader.discover(start_dir=tests_dir, pattern="test_*.py")

    if is_unit:
        suite = _filter_suite_exclude_integration(suite)

    if k_pattern:
        suite = _filter_suite_by_pattern(suite, k_pattern)

    # Zero-Test Safeguard: reject runs that collected 0 tests
    if suite.countTestCases() == 0:
        print("[Error] No tests collected matching the specified arguments or pattern.", file=sys.stderr)
        sys.exit(1)

    runner = TimingTestRunner(verbosity=1 if quiet else 2)
    result = runner.run(suite)

    # Zero-Test Safeguard: reject runs that executed 0 tests
    if result.testsRun == 0:
        print("[Error] Zero tests were executed.", file=sys.stderr)
        sys.exit(1)

    durations = sorted(getattr(result, "durations", []), key=lambda x: x[0], reverse=True)
    slowest_limit = 5
    for a in sys.argv[1:]:
        if a.startswith("--slowest="):
            try:
                slowest_limit = int(a.split("=")[1])
            except ValueError:
                pass
    if not quiet and durations and slowest_limit > 0:
        top = durations[:slowest_limit]
        print(f"\nSlowest tests (top {len(top)}):")
        for dur, tid in top:
            print(f"  {dur:6.2f}s  {tid}")

    # [feat--test-gate-cost-reduction] REQ-1 & REQ-6, [feat--test-gate-scope] REQ-6: record run for full suite
    if not is_doc and not normalized_args and not k_pattern and not is_unit:
        tree = testruns.tree_hash(repo_root)
        if tree:
            testruns.record_run(repo_root, result.wasSuccessful(), tree, "test.py")

    if not result.wasSuccessful():
        note = testruns.baseline_note(repo_root)
        if note:
            print(note, file=sys.stderr)

    sys.exit(0 if result.wasSuccessful() else 1)

if __name__ == "__main__":
    main()
