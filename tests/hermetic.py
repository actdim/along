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

import contextlib
import os
import shutil
import sys
import tempfile

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPTS_DIR = os.path.join(REPO_ROOT, "scripts")
if SCRIPTS_DIR not in sys.path:
    sys.path.insert(0, SCRIPTS_DIR)

from alongkit import textio
from alongkit.version import CURRENT_PROTOCOL_VERSION

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


def make_repo_fixture(prefix: str = "along-fixture-",
                      protocol_version: str | None = None,
                      with_docs: bool = True) -> str:
    """Create a throwaway repository that looks like a current Along project.

    Returns its path; the caller removes it (or uses `repo_fixture()`, which does).
    Deliberately NOT a git repository: nothing a test runs here should be able to reach
    a real index or history.
    """
    version = protocol_version or CURRENT_PROTOCOL_VERSION
    root = tempfile.mkdtemp(prefix=prefix)
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
                 with_docs: bool = True):
    """`make_repo_fixture` as a context manager that always cleans up."""
    root = make_repo_fixture(prefix=prefix, protocol_version=protocol_version,
                             with_docs=with_docs)
    try:
        yield root
    finally:
        shutil.rmtree(root, ignore_errors=True)
