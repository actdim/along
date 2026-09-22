---
protocol: along
slug: cli-and-documentation-traceability-reconciliation
date: 2026-09-21
agent: antigravity
summary: "Implemented along hook eval, documented debug lifecycle command, added missing topic docs to mkdocs.yml, cleaned duplicate frontmatter, synchronized 19 skills across documentation, resolved hash drift, and injected site-extra assets"
milestone: v4.0.0-runtime-gates-and-worktree-isolation
issues_advanced: []
issues_completed: [docs--cli-and-documentation-traceability-reconciliation]
decisions: []
risks_logged: []
spikes_conducted: []
branch: main
commit: unknown
---

# Session Log: 2026-09-21 - CLI Hook Interface Reconciliation, Navigation Completeness, and Version Traceability

## 1. Objectives & Context

Completion of `[docs--cli-and-documentation-traceability-reconciliation]` under milestone `v4.0.0-runtime-gates-and-worktree-isolation`:
- Implement the missing `along hook eval` subcommand in `scripts/along_hook.py`.
- Document `debug` lifecycle command in `scripts/along_exec.py` and `scripts/alongkit/lifecycle.py`.
- Add missing topic documents (`cli-reference`, `declarative-gates-and-traceability`, `runtime-hooks-and-gates`) to `mkdocs.yml` navigation.
- Clean up duplicate frontmatter and update protocol version in `docs/topic--cli-reference.md`.
- Synchronize skill count (19) across `README.md`, `llms.txt`, `llms-full.txt`, and `scripts/alongkit/cli.py`.
- Reconcile version and source content hashes across documentation and update `dashboard/__init__.py`.
- Clarify `v3.4.0` release history in `CHANGELOG.md`.
- Inject `site-extra` assets (`robots.txt`, `schema.jsonld`, `.well-known/agents.json`) in `hooks/rewrite_links.py`.
- Add automated unit tests for `along hook eval`.

## 2. Key Architecture & Changes

1. **CLI Hook Dispatcher (`scripts/along_hook.py`)**:
   - Implemented `along hook eval <event> [payload] [--runtime {antigravity,claude,codex,cursor,opencode,generic}] [--payload <json_or_string>] [--mode {enforce,shadow}] [--repo-root <path>]`.
   - Unified hook evaluation in `_evaluate_and_respond`.
   - Added UTF-8 BOM (`\ufeff`) stripping on incoming stdin and payload across all adapters (`generic.py`, `antigravity.py`, `claude.py`, `codex.py`).
   - Added `tool_args` recognition in `GenericCliAdapter`.

2. **Lifecycle Router (`scripts/along_exec.py`, `scripts/alongkit/lifecycle.py`)**:
   - Added `debug` command to `Lifecycle Commands (project hooks)` in CLI help.
   - Updated `LIFECYCLE_ACTIONS` tuple in `alongkit/lifecycle.py` to `("build", "test", "dev", "debug")`.

3. **MkDocs Navigation & Assets (`mkdocs.yml`, `hooks/rewrite_links.py`)**:
   - Added `CLI Reference: topic--cli-reference.md`, `Runtime Hooks & Gates: topic--runtime-hooks-and-gates.md`, and `Declarative Gates & Traceability: topic--declarative-gates-and-traceability.md` to `nav:` in `mkdocs.yml`.
   - In `hooks/rewrite_links.py`, enhanced `on_files()` to recursively discover and inject files from `site-extra/` into the MkDocs files manifest.

4. **Skill Count & Documentation Synchronization**:
   - Updated `README.md`, `llms.txt`, and `llms-full.txt` to consistently state 19 singular automation skills.
   - Updated `scripts/alongkit/cli.py` to reference nineteen `SKILL.md` files.
   - Merged duplicate frontmatter in `docs/topic--cli-reference.md` and set `protocol_version: "3.9.4"`.
   - Updated `__version__ = "3.9.4"` in `dashboard/__init__.py`.
   - Recomputed and updated all drifted source SHA-256 hashes in `docs/topic--*.md`.

5. **Release History**:
   - Clarified `v3.4.0` in `CHANGELOG.md` as consolidated directly into the `v3.5.0` tag.

6. **Automated Tests**:
   - Added `test_cli_along_hook_eval_with_payload_opt`, `test_cli_along_hook_eval_with_positional_payload_denied`, and `test_cli_along_hook_eval_stdin_pipe` in `tests/test_hooks_generic.py`.

## 3. Verification & Invariants

- Ran full test suite via `python .along/scripts/test.py`: 520 tests passed, 0 failures.
- Ran `python scripts/along_kb_sync.py --check`: 0 drift, 0 broken links, all 321 links verified.
- Ran `python scripts/along_hook.py verify --strict`: all 14 gates verified and anchored.
- Ran `python scripts/along_exec.py sanitize --check`: 499 files clean, zero non-ASCII violations.
