"""
tests/_integration.py - Integration test registry for Along test suite.

Single source of truth for heavy test modules that perform multi-process operations,
real git repository manipulations, venv bootstraps, or Docker executions.
Used by both Pytest (to attach the `integration` marker) and .along/scripts/test.py
(for --unit / --fast filtering).
Pytest-free so importing this module never pulls pytest into standard unittest runs.
"""

from __future__ import annotations

INTEGRATION_MODULES: frozenset[str] = frozenset({
    "test_bootstrap",
    "test_commit",
    "test_devenv",
    "test_docker_image_integration",
    "test_git_gate_enforcement",
    "test_installers",
    "test_lifecycle_wrap",
    "test_merge_driver",
    "test_parallel_closeout",
    "test_release_engine",
    "test_worktree",
})

INTEGRATION_TESTS: frozenset[str] = frozenset()

