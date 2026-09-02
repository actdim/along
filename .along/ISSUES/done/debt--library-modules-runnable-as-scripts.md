---
protocol: along
protocol_version: "2.2.9"
slug: library-modules-runnable-as-scripts
type: debt
status: done
completed: 2026-09-02
priority: medium
created: 2026-09-01
updated: 2026-09-02
agent: claude-code
tags: [alongkit, entrypoints, agent-ergonomics, false-green]
milestone: v3.0.0-global-quality-revision
blocked_by: []
related: [skill-commands-reference-missing-script-paths]
parent: protocol-quality-audit-remediation
---

# alongkit library modules run as scripts and exit 0 in silence

## Problem

`scripts/alongkit/*.py` are library modules with no command interface, but nothing stops an
agent from invoking one directly, and the two failure shapes are both wrong:

```text
python scripts/alongkit/repo.py          -> exit 0, no output
python scripts/alongkit/frontmatter.py   -> ImportError: attempted relative import with no known parent package
python -m alongkit --version             -> No module named alongkit.__main__
```

The first case is the damaging one. An agent that guesses a path, runs it, and reads exit
code 0 with empty stdout records a successful no-op. Nothing in the output says the module
was not a command, so the agent proceeds on a false premise. Which of the twelve modules
behaves this way depends only on whether the module happens to use a relative import at
top level, so the behaviour is accidental rather than designed.

The second case is honest about failing but says nothing actionable: `attempted relative
import` describes a Python mechanism, not what the agent should have run instead.

The third case is a missed opportunity. `python -m alongkit` is the form an agent guesses
first for a package, and it currently fails, while the same dispatch already exists in
`alongkit.cli:main` behind the `along` console entry point.

## Non-goal: the engines

`scripts/along_*.py`, `migrate_protocol.py`, and `sanitize_typography.py` MUST remain
directly runnable. Direct invocation is the documented form in the skills
(`skills/along-kb-sync/SKILL.md:40`), and it is the only form that works for case 2 in
`alongkit/bootstrap.py` - a flat file install into `~/.along/bin/` with no virtual
environment attached. This issue must not add guards there.

The separate defect that direct engine invocation names a `scripts/` directory absent from
consumer repositories is `[bug--skill-commands-reference-missing-script-paths]`.

## Why a runtime guard rather than metadata

A header comment, a docstring note, or a machine-readable marker is only read by an agent
that has already opened the file. An agent that guessed the path and ran it reads stdout,
not source. Metadata covers the case that is not failing, and a marker with no consumer
becomes another unenforced source of truth.

## Requirements

- REQ-1: Every module in `scripts/alongkit/` except `cli.py` and `__init__.py` refuses
  direct execution with a non-zero exit and a message naming the correct command:

```python
if __name__ == "__main__":
    raise SystemExit(
        "alongkit.repo is a library module, not a command.\n"
        "Run: along kb-sync   (or: python scripts/along_exec.py kb-sync)"
    )
```

- REQ-2: The guard must fire before any import that can fail, so the module reports its own
  nature rather than an `ImportError` about relative imports.
- REQ-3: Add `scripts/alongkit/__main__.py` forwarding to `cli.main()`, so `python -m
  alongkit <subcommand>` works. Opening the door an agent guesses is worth more than closing
  the ones it does not.
- REQ-4: A test walks `scripts/alongkit/*.py`, excludes `cli.py`, `__init__.py`,
  `__main__.py`, and asserts each remaining module carries the guard. Without a test this
  degrades the same way a comment would.
- REQ-5: A test asserts `python -m alongkit --version` exits 0 and prints the protocol
  version.
- REQ-6: Do not touch `scripts/along_*.py`, `migrate_protocol.py`, or
  `sanitize_typography.py`.

## Acceptance Criteria

- [ ] `python scripts/alongkit/<any library module>.py` exits non-zero with an actionable message.
- [ ] No library module exits 0 in silence.
- [ ] `python -m alongkit --version` works.
- [ ] Engines remain directly runnable and their tests unchanged.
- [ ] Guard coverage and the `-m` entry point are both asserted by tests.
