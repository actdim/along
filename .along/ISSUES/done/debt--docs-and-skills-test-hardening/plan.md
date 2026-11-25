# Plan: Harden test_docs.py and test_skills_and_scripts.py assertions

## Execution Mode
Direct

## Context and Scope
Follow-up to `debt--test-suite-paper-compliance-cleanup` (`0171a45`), which missed `tests/test_docs.py` and `tests/test_skills_and_scripts.py`:
1. `tests/test_docs.py` relies on literal prose/marketing substring matching (`assertIn`) instead of structural Markdown, YAML frontmatter schema, code fence, relative link, and real CLI/symbol verification via `alongkit.markdown`, `alongkit.frontmatter`, and `alongkit.repochecks`.
2. `tests/test_skills_and_scripts.py` performs shallow `os.path.isfile`/`os.path.exists` and raw substring checks on `SKILL.md` manifests and resolved engine scripts instead of verifying Python AST syntax (`ast.parse`), YAML frontmatter schemas, non-empty Markdown bodies, code fence integrity, and valid relative Markdown links.

Target Issue: `debt--docs-and-skills-test-hardening`
Milestone: `v5.0.0-agent-run-protocol-and-observability`

## Requirements
- REQ-1: `tests/test_docs.py` MUST replace brittle marketing/prose substring matching with structural Markdown link, code fence, frontmatter schema, heading, and real symbol/CLI checks via `alongkit.markdown`, `alongkit.frontmatter`, and `alongkit.repochecks`.
- REQ-2: `tests/test_skills_and_scripts.py` MUST upgrade superficial `os.path.isfile`/`os.path.exists` and substring checks on scripts and skills to Python AST parsing (`ast.parse`) and `SKILL.md` YAML frontmatter schema, body, code fence, and relative link validation while keeping all functional CLI and installer tests intact.

## Implementation Steps

### Step 1: Harden `tests/test_docs.py` (REQ-1)
- Add structural Markdown verification helpers using `alongkit.markdown` (`FenceTracker`, `extract_heading_anchors`, `find_links`, `find_broken_links`, `resolve_target`), `alongkit.frontmatter` (`parse`), and `alongkit.repochecks` (`check_code_fence_language`).
- Validate YAML frontmatter schemas (`protocol`, `slug`, `title`, `type`, `tags`, `write_policy` where applicable) on `skills/along-init/protocol-reference.md`, `.along/PROTOCOL.md`, `docs/topic--troubleshooting.md`, `docs/INDEX.md`, and `skills/along-team/SKILL.md`.
- Replace brittle literal prose/marketing `assertIn` checks across lines 25-92 with structural heading checks, closed/labeled code fence verification, relative Markdown link resolution on disk, and real symbol/gate/CLI/filesystem checks verified against `along_exec` and repository paths.
- Verify `docs/INDEX.md` and `llms.txt` structurally register `topic--troubleshooting.md` via parsed Markdown links (without leaking `topic--along-protocol.md`) and pass link/fence checks.

### Step 2: Harden `tests/test_skills_and_scripts.py` (REQ-2)
- Upgrade `test_01_all_python_files_compile` to parse every repository Python file into an AST via `ast.parse` (and verify non-`__init__.py` scripts contain executable/definition AST statements in `tree.body`, alongside `compile`).
- Upgrade `test_03_skill_manifests_validity` from raw `startswith("---")` and substring `assertIn` checks to strict `alongkit.frontmatter.parse` schema validation (`name` matching `skills/along-*` folder name, non-empty string `description`, expected key schema), non-empty Markdown body with headings, closed/labeled code fences, and valid relative Markdown links via `alongkit.markdown.find_broken_links`.
- Upgrade `test_03e_skills_document_canonical_along_commands` so directories in `skills/` require a valid `SKILL.md` (no silent skip) and backticked/fenced `along <subcmd>` invocations resolve against real `along_exec` commands.
- Upgrade `test_20_candidate_scripts_resolution` (and any superficial script existence checks) to parse resolved script ASTs (`ast.parse`) and confirm runnable entrypoint structure (`main`) while keeping all existing functional, CLI, and installer tests intact.

### Step 3: Verification and Closeout
- Run targeted tests (`tests.test_docs`, `tests.test_skills_and_scripts`) and the full test suite via `.along\scripts\test.py -q`.
- Run `along sanitize` and `along hook verify --strict`.
- Update issue checkboxes, wrap (`along wrap`), commit (`along commit`), and push (`git push`).
