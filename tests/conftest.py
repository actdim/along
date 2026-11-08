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
