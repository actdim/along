---
protocol: along
slug: frontmatter-on-ruamel-yaml
title: "Front-matter on ruamel.yaml, with uv for Dependency Delivery"
date: 2026-09-01
status: accepted
tags: [adr, architecture, decision]
---

# ADR-2026-09-01--frontmatter-on-ruamel-yaml - Front-matter on ruamel.yaml, with uv for Dependency Delivery

- Date: 2026-09-01
- Status: accepted
- Context: Front-matter was parsed and written by hand in four independent copies. All shared two defects that lost user data: a line without a colon was skipped, so a block sequence (`tags:` followed by indented `- item` lines) parsed to an empty string and the following full rewrite deleted its items; and the writer emitted `f"{key}: {value}"` with no quoting, so an ordinary title containing a colon produced a block that is not valid YAML. Six such files existed in this repository when this decision was taken, unreadable by PyYAML, `gray-matter`, and GitHub alike, including four milestones and two session logs. A separate finding: `decisions: [012]` was read as the integer 10 by PyYAML (YAML 1.1 octal) and as the string "012" by the hand-rolled parser, so no two readers agreed on the repository's own data. Writing a bespoke subset parser was considered and rejected: YAML is a widely implemented format, the front-matter is read by tools that are not Along, and a hand-rolled parser must be kept correct by tests forever for no gain.
- Decision:
  1. **`ruamel.yaml` in round-trip mode**, chosen over `pyyaml` because it preserves comments, key order, and quoting style. Measured on this repository: a no-op read-and-write is byte-identical for 123 of 123 entity files.
  2. **Reads are strict, edits are surgical**. `frontmatter.parse` raises on a block it cannot understand; `frontmatter.update` names individual keys and leaves every other line untouched; `frontmatter.render` is only for new files and re-parses its own output before returning it. `frontmatter.parse_tolerant` exists for read-only scanners that must not abort on one bad file, and it reports rather than silently reinterpreting.
  3. **A refusal is the correct outcome** for metadata that cannot be parsed: engines skip and report the file and line instead of rewriting it from a partial parse.
  4. **Dependency delivery via uv**, not vendoring: `pyproject.toml` is authoritative, `alongkit.bootstrap` mirrors the list for direct invocation and re-executes an engine once under `uv run` when the import fails, and a test asserts the two lists stay identical. `pixi` was considered and rejected as unnecessary for a pure-Python project.
  5. **Two deliberate deviations from PyYAML defaults**, both to keep existing consumers working: an ISO date stays a `YYYY-MM-DD` string rather than becoming a `datetime.date`, and an unset key reads as the empty string rather than None, because front-matter is text metadata and every caller does `fields.get(key, "")`.
- Consequences: The "zero external dependencies" claim for `along-kb-sync` is no longer true and has been corrected in `skills/along-kb-sync/SKILL.md` and `docs/topic--skills-reference.md`; the honest statement is one dependency, resolved automatically by uv. In exchange, the read-modify-write cycle over a user's files stops losing block sequences, comments, and key order, and a block that is not valid YAML is refused loudly instead of propagated. The six pre-existing invalid files were repaired as part of this change (one line each, net line count unchanged).
