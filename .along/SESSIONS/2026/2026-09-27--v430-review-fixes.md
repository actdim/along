---
protocol: along
protocol_version: "4.2.1"
date: 2026-09-27
slug: v430-review-fixes
agent: cowork
branch: main
commit: a94d382
summary: 'v4.3.0: 8 review issues closed (py3.10, hermetic tests, test:quiet, gate bypasses, conflict-marker gate, session YAML, Cowork runtime); CI workflow pending manual add'
milestone: v4.3.0-developer-experience-and-runtime-resilience
issues_advanced: []
issues_completed: [bug--py310-fstring-syntax-error, bug--non-hermetic-global-skill-tests, bug--test-quiet-script-guard-conflict, bug--claude-adapter-unmapped-tools, bug--safe-command-prefix-bypass, bug--conflict-marker-gate-wrong-target, bug--session-create-unsafe-yaml, feat--cowork-runtime-support]
decisions: []
risks_logged: []
spikes_conducted: []
---

# Session: V430 review fixes

## Summary
v4.3.0: 8 review issues closed (py3.10, hermetic tests, test:quiet, gate bypasses, conflict-marker gate, session YAML, Cowork runtime); CI workflow pending manual add

## Execution Mode
Direct (single agent, Claude Cowork), issues executed sequentially in the order the user approved. Runtime gates were not active in this environment (advisory mode); gate-tagged rules were self-applied, files were edited with file tools only, no commits were made (user instruction).

## Work Completed
1. `bug--py310-fstring-syntax-error`: PEP 701 f-string in `along_exec.py` rewritten; every tracked `.py` compiles on 3.10.12.
2. `bug--non-hermetic-global-skill-tests`: `along_update.py` resolves `protocol.md` from `ALONG_PROTOCOL_SOURCE` / its own checkout before global skills; `tests/hermetic.py` isolated home for engine children; Windows-only test skipped elsewhere; new meta-test.
3. `bug--test-quiet-script-guard-conflict`: `.along/scripts/test.py -q`; `test:quiet` uses it; decision documented in `docs/topic--setup-and-workflow.md`.
4. `bug--claude-adapter-unmapped-tools`: Claude map extended (MultiEdit, NotebookEdit, Grep, Glob, read tools); engine-wide fail-closed normalization (`hooks/adapters/normalize.py`) with `unmapped_tool` audit.
5. `bug--safe-command-prefix-bypass`: segment-aware classifier `hooks/shellparse.py` replaces the prefix/substring allowlist.
6. `bug--conflict-marker-gate-wrong-target`: gate now inspects `git diff --cached` / `git diff HEAD` for added markers.
7. `bug--session-create-unsafe-yaml`: session logs rendered through `frontmatter.render`, real branch/commit, evidence-only test line (this file is its first real output).
8. `feat--cowork-runtime-support`: `alongkit/runtime.py`, Cowork detection in `detect_agent`, doctor Runtime section, capability matrix and Cowork guide in `docs/topic--runtime-hooks-and-gates.md`, one protocol rule.
9. `task--ci-test-matrix-workflow`: workflow written, docs and release precondition updated; left in-progress because `.github/workflows/` is protected from remote tools in Cowork - the user adds `tests.yml` by hand.

## Code Review & Blast Radius
- Tests: `.along/scripts/test.py -q` on Python 3.12 and 3.10.12 (Linux, Cowork VM): 698 tests OK, 3 skipped (was 5 failures + 1 error on 3.12, syntax-gate abort on 3.10). During iteration individual modules were run with `ALONG_TEST_RUNNER=1 python -m unittest discover -s tests -p <file>`; every issue was closed only after a full runner pass.
- `along graph-impact` flagged `docs/topic--cli-reference.md` (updated: doctor Runtime section, `session create --commit`) plus the three topic articles already edited; `along kb-sync` recompiled `llms-full.txt`.
- `git diff --stat`: 22 tracked files, +432 / -86, no unexpected size reductions; 8 new files (3 modules, 5 test files).
- Typography check clean (`sanitize_typography.py . --check`, 625 files).

## Observations
- `along wrap` cannot close issues in a Cowork folder without delete permission: it writes `done/<file>` and then fails on `os.remove(src)`. Issues were closed by the equivalent manual steps (front-matter `done` + `completed`, file moved with `mv`, projections recompiled); originals moved to `.git/_to_delete/`.
- Every full test run leaves `.git/index.lock` (hermetic meta-test `git status` in a no-delete mount); moved to `.git/_to_delete/` after each run. Kept by decision (`ADR-2026-09-07--revert-git-stat-cache-workarounds`); doctor now warns.
- `feat--git-level-gate-enforcement` conflicts with the "Zero Git Hooks" invariant in `docs/topic--runtime-hooks-and-gates.md`; noted in that issue (ADR needed first).
- Link gate `along_kb_sync.py --check --strict` fails locally on 9 links into `packages/dashboard-ui/node_modules` from `docs/topic--dependencies.md` (pre-existing).
