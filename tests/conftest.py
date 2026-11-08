"""
tests/conftest.py - Pytest configuration and environment bridge for Along test suite.

Satisfies the ALONG_TEST_RUNNER guard for Pytest and IDE test explorers while
ensuring repository roots and scripts are in sys.path.
"""

from __future__ import annotations

import os
import sys

# Ensure runner environment flag is set during conftest evaluation
os.environ["ALONG_TEST_RUNNER"] = "pytest"

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TESTS_DIR = os.path.join(REPO_ROOT, "tests")
SCRIPTS_DIR = os.path.join(REPO_ROOT, "scripts")

for p in (REPO_ROOT, TESTS_DIR, SCRIPTS_DIR):
    if p not in sys.path:
        sys.path.insert(0, p)


def pytest_configure(config):
    """Pytest configuration hook executed before test discovery and import."""
    os.environ["ALONG_TEST_RUNNER"] = "pytest"
    for p in (REPO_ROOT, TESTS_DIR, SCRIPTS_DIR):
        if p not in sys.path:
            sys.path.insert(0, p)

    # Clear active agent session variables so tests remain hermetic
    from alongkit import session
    for var in session.SESSION_ENV_VARS:
        os.environ.pop(var, None)


def pytest_collection_modifyitems(config, items):
    """Mark integration tests from registry and deselect hermetic meta-test under xdist."""
    import pytest
    from _integration import INTEGRATION_MODULES, INTEGRATION_TESTS

    is_xdist = bool(os.environ.get("PYTEST_XDIST_WORKER"))
    selected = []
    deselected = []

    for item in items:
        mod_name = getattr(item.module, "__name__", "")
        if mod_name.startswith("tests."):
            mod_name = mod_name[len("tests."):]
        file_stem = os.path.splitext(os.path.basename(str(item.fspath)))[0]

        if is_xdist and (file_stem == "test_zz_hermetic_suite" or mod_name == "test_zz_hermetic_suite"):
            deselected.append(item)
            continue

        selected.append(item)

        if file_stem in INTEGRATION_MODULES or mod_name in INTEGRATION_MODULES or item.nodeid in INTEGRATION_TESTS:
            item.add_marker(pytest.mark.integration)

    if deselected:
        config.hook.pytest_deselected(items=deselected)
        items[:] = selected
