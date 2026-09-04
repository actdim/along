#!/usr/bin/env python3
"""
alongkit - Shared implementation behind the Along engines.

The engines in `scripts/` used to be twelve standalone programs with no shared module.
`find_repo_root` existed in five divergent copies, front-matter parsing in four, and
`subprocess.run` was called 25+ times with no shared convention, which is how a single
encoding defect reached every one of them. This package holds one implementation of
each shared concern:

- `repo`        repository root, state directory, engine resolution, directory walking
- `frontmatter` the YAML front-matter reader and writer (ruamel.yaml, round-trip)
- `entities`    entity vocabulary, canonical keys, ADR records
- `proc`        subprocess execution with fixed UTF-8 conventions
- `textio`      strict reads, line-ending preservation, atomic writes
- `markdown`    links, fenced-code tracking, heading anchors
- `typography`  the forbidden-character table
- `sanitizer`   which files that table governs, and the report a caller consumes
- `transaction` snapshot and byte-exact rollback around a multi-file mutation
- `migration`   collision policy, backup, and dry-run plan for the migration engine
- `version`     the protocol version constant
- `bootstrap`   dependency resolution for a directly invoked engine

Import style inside the engines is `from alongkit import repo, proc`, which works
unmodified both in the source repository and in the flat `~/.along/bin/` install,
because Python places the running script's directory on `sys.path` and the package is
always copied next to the engines.
"""

from __future__ import annotations

from . import (bootstrap, entities, markdown, migration, proc, repo, sanitizer,
               textio, transaction, typography, version)
from .proc import Result, run_capture, run_passthrough, run_python
from .repo import find_repo_root, find_state_dir, resolve_tool_script, safe_relpath, state_dir
from .repo import (find_agent_contexts, find_manifest_projects, find_repo_root,
                    find_state_dir, resolve_llm_targets, resolve_tool_script,
                    safe_relpath, state_dir)
from .textio import read_text, write_text
from .version import CURRENT_PROTOCOL_VERSION

__all__ = [
    "bootstrap",
    "entities",
    "markdown",
    "migration",
    "proc",
    "repo",
    "sanitizer",
    "textio",
    "transaction",
    "typography",
    "version",
    "CURRENT_PROTOCOL_VERSION",
    "Result",
    "find_agent_contexts",
    "find_manifest_projects",
    "find_repo_root",
    "find_state_dir",
    "read_text",
    "resolve_llm_targets",
    "resolve_tool_script",
    "run_capture",
    "run_passthrough",
    "run_python",
    "safe_relpath",
    "state_dir",
    "write_text",
]

# `frontmatter` is deliberately absent from the eager imports above: it requires
# ruamel.yaml, and an engine that only needs `repo` or `proc` must not be forced to
# resolve a third-party dependency. Import it explicitly where it is used:
#     from alongkit import frontmatter
