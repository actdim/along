#!/usr/bin/env python3
"""
tests/hermetic.py - throwaway repository fixtures for the Along test suite.

The rule this module exists to make cheap: no test may point a writing engine at the
repository that contains it. Three tests used to pass `REPO_ROOT` to `along_dash.py`,
`migrate_protocol.py`, and `along_update.py`. The migration engine rewrites front-matter,
sanitizes typography, and rewrites Markdown links across the whole tree, so running the
suite could edit files a developer was working on: it once turned a newly created
`protocol_version: "2.2.8"` into `protocol_version: 2.2.8` mid-session. A suite that
mutates its own repository cannot be a gate, because "the suite is green" and "the tree is
clean" stop being simultaneously achievable. See `[bug--tests-mutate-working-tree]`.

Every engine invocation therefore targets a fixture built here, and
`tests/test_zz_hermetic_suite.py` proves the suite left the real tree alone.

Reading live repository content is still allowed, and several tests depend on it (the ADR
format guard, the entity-status guard, the typography gate). Those tests must open files
read-only and must not invoke an engine that writes.
"""

from __future__ import annotations

import os
import sys

if not os.environ.get("ALONG_TEST_RUNNER"):
    raise SystemExit(
        "[Error] Tests must not be run directly or via standard test commands (unittest/pytest).\n"
        "To run tests with automatically resolved dependencies, use the official project entry point:\n"
        "    python .along/scripts/test.py"
    )

import atexit
import contextlib
import os
import shutil
import sys
import tempfile
import unittest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPTS_DIR = os.path.join(REPO_ROOT, "scripts")
if SCRIPTS_DIR not in sys.path:
    sys.path.insert(0, SCRIPTS_DIR)

from alongkit import bootstrap, textio
from alongkit.version import CURRENT_PROTOCOL_VERSION

#: Skips a test that needs the dashboard stack (`dev` group: `actdim-along[dash]`) when the
#: interpreter lacks it, e.g. no `uv` to enter the project environment.
#: See [bug--test-hook-lacks-dashboard-deps].
requires_dashboard_deps = unittest.skipUnless(
    bootstrap.have_deps(("fastapi", "pydantic")),
    "dashboard stack (fastapi, pydantic) not installed; run in the project environment (uv sync)")

BEGIN_MARKER = "<!-- BEGIN ALONG-PROTOCOL root (managed by along-init - do not edit by hand) -->"
END_MARKER = "<!-- END ALONG-PROTOCOL -->"

#: A fixture issue that satisfies the front-matter schema in AGENTS.md, so the entity
#: graph validator in the migration engine has something real to parse.
FIXTURE_ISSUE = """---
protocol: along
protocol_version: "{version}"
slug: fixture-sample-task
type: task
status: open
priority: medium
created: 2026-09-01
updated: 2026-09-01
agent: test-suite
tags: [fixture]
---

# Fixture sample task

A single well-formed entity, so an engine walking `.along/ISSUES/` is not walking an
empty directory.
"""

FIXTURE_TOPIC = """---
protocol: along
protocol_version: "{version}"
slug: topic--architecture
title: Architecture
type: architecture
created: 2026-09-01
updated: 2026-09-01
tags: [architecture]
---

# Architecture

The fixture Knowledge Base article. Present so that link rewriting and index compilation
have a real target to resolve against.
"""

FIXTURE_ISSUES_BOARD = (
    "# Active Issues\n\n"
    "## Active\n"
    "- [ ] `(task)` fixture-sample-task\n\n"
    "## Backlog\n\n"
    "## Done (recent)\n"
)

FIXTURE_DECISIONS = (
    "# Architectural Decisions\n\n"
    "## ADR-2026-09-01--fixture-decision - Fixture decision\n\n"
    "- Date: 2026-09-01\n"
    "- Status: accepted\n"
    "- Context: The fixture needs exactly one parseable ADR.\n"
    "- Decision: Keep exactly one.\n"
    "- Consequences: None.\n"
)


def to_short_path(path: str) -> str:
    """Return 8.3 short path representation on Windows, or original path on other platforms.

    Used by fixtures to simulate Windows CI runner environments (such as GitHub Actions
    `RUNNER~1` paths) on local developer machines.
    """
    if sys.platform != "win32":
        return path
    try:
        import ctypes
        buf = ctypes.create_unicode_buffer(500)
        res = ctypes.windll.kernel32.GetShortPathNameW(path, buf, 500)
        if res > 0 and buf.value:
            return buf.value
    except (OSError, ValueError, AttributeError):
        pass
    return path


def make_repo_fixture(prefix: str = "along-fixture-",
                      protocol_version: str | None = None,
                      with_docs: bool = True,
                      simulate_short_path: bool = True) -> str:
    """Create a throwaway repository that looks like a current Along project.

    Returns its path; the caller removes it (or uses `repo_fixture()`, which does).
    Deliberately NOT a git repository: nothing a test runs here should be able to reach
    a real index or history.
    """
    version = protocol_version or CURRENT_PROTOCOL_VERSION
    raw_root = tempfile.mkdtemp(prefix=prefix)
    root = to_short_path(raw_root) if simulate_short_path else raw_root
    put = textio.write_text

    put(os.path.join(root, "AGENTS.md"),
        f"{BEGIN_MARKER}\n"
        f"# ALONG-PROTOCOL v{version}\n\n"
        "Fixture context. Entities live in `.along/`.\n"
        f"{END_MARKER}\n\n"
        "## Project specifics\n\n"
        "- A throwaway fixture repository built by tests/hermetic.py.\n")
    put(os.path.join(root, "CLAUDE.md"), "See @AGENTS.md.\n")
    put(os.path.join(root, "README.md"),
        "# Fixture Project\n\nSee [Index](./docs/INDEX.md).\n")

    along = os.path.join(root, ".along")
    os.makedirs(os.path.join(along, "ISSUES", "done"), exist_ok=True)
    os.makedirs(os.path.join(along, "SESSIONS"), exist_ok=True)
    put(os.path.join(along, "ISSUES", "task--fixture-sample-task.md"),
        FIXTURE_ISSUE.format(version=version))
    put(os.path.join(along, "ISSUES.md"), FIXTURE_ISSUES_BOARD)
    put(os.path.join(along, "DECISIONS.md"), FIXTURE_DECISIONS)
    put(os.path.join(along, "HISTORY.md"), "# History\n\n")
    put(os.path.join(along, "GLOSSARY.md"), "# Glossary\n\n")
    put(os.path.join(along, "VISION.md"), "# Vision\n\nFixture.\n")

    if with_docs:
        docs = os.path.join(root, "docs")
        put(os.path.join(docs, "topic--architecture.md"),
            FIXTURE_TOPIC.format(version=version))
        put(os.path.join(docs, "INDEX.md"),
            "# Knowledge Base Index\n\n- [Architecture](./topic--architecture.md)\n")
    return root


@contextlib.contextmanager
def repo_fixture(prefix: str = "along-fixture-",
                 protocol_version: str | None = None,
                 with_docs: bool = True,
                 simulate_short_path: bool = True):
    """`make_repo_fixture` as a context manager that always cleans up."""
    root = make_repo_fixture(prefix=prefix, protocol_version=protocol_version,
                             with_docs=with_docs,
                             simulate_short_path=simulate_short_path)
    try:
        yield root
    finally:
        shutil.rmtree(root, ignore_errors=True)


#: Provider-specific overrides that would point an engine back at real user state.
PROVIDER_HOME_VARS = ("CODEX_HOME", "CLAUDE_CONFIG_DIR", "OPENCODE_HOME", "GEMINI_HOME")

_ISOLATED_HOME: str | None = None


def isolated_home() -> str:
    """One empty throwaway home directory per test process, removed at exit."""
    global _ISOLATED_HOME
    if _ISOLATED_HOME is None or not os.path.isdir(_ISOLATED_HOME):
        raw = tempfile.mkdtemp(prefix="along-home-")
        _ISOLATED_HOME = to_short_path(raw)
        atexit.register(shutil.rmtree, raw, True)
    return _ISOLATED_HOME


def isolated_home_env(base: dict | None = None) -> dict:
    """A child environment whose home directory is an empty throwaway directory.

    Engines resolve global skills, manifests, and diagnostics through `~`; a child started
    with this environment cannot read or write the developer's real `~/.claude`,
    `~/.codex`, `~/.gemini`, or `~/.along`, so a result never depends on whether Along is
    installed on the machine running the suite. See [bug--non-hermetic-global-skill-tests].
    """
    env = dict(os.environ if base is None else base)
    home = isolated_home()
    env["HOME"] = home
    env["USERPROFILE"] = home
    env["XDG_CONFIG_HOME"] = os.path.join(home, ".config")
    for var in PROVIDER_HOME_VARS:
        env.pop(var, None)
    return env


#: What an installer needs from a checkout, and nothing else: no `.along/`, no `.git`,
#: no tests. Keeping the migration step's trigger out of the copy is deliberate - an
#: installer test must not exercise the migration engine as a side effect.
CHECKOUT_CONTENTS = ("skills", "rules", "scripts", "config",
                     "install.sh", "install.ps1", "install.bat")


def make_installer_checkout(prefix: str = "along checkout ") -> str:
    """Copy the parts of this checkout an installer reads into a throwaway directory.

    The installers are run against this copy rather than against `REPO_ROOT`, for the
    same reason every other engine is run against a fixture: an installer is a program
    that writes, and a test that points one at the repository containing it cannot
    prove anything about a clean tree.

    The default prefix contains a space on purpose. `install.ps1` falls back to
    `cmd /c mklink /J` when it cannot create a symlink, and that call used to be
    double-quoted (`""C:\\path""`), which works only while no path contains a space -
    the exact case the fallback exists to serve.
    See `[bug--installer-parity-and-destructive-rules-overwrite]` REQ-5.
    """
    root = tempfile.mkdtemp(prefix=prefix)
    for name in CHECKOUT_CONTENTS:
        source = os.path.join(REPO_ROOT, name)
        target = os.path.join(root, name)
        if os.path.isdir(source):
            shutil.copytree(source, target,
                            ignore=shutil.ignore_patterns("__pycache__"))
        elif os.path.isfile(source):
            shutil.copy2(source, target)
    return root


@contextlib.contextmanager
def installer_checkout(prefix: str = "along checkout "):
    """`make_installer_checkout` as a context manager that always cleans up."""
    root = make_installer_checkout(prefix=prefix)
    try:
        yield root
    finally:
        shutil.rmtree(root, ignore_errors=True)
