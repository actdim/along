---
protocol: along
protocol_version: "4.2.0"
slug: ci-test-matrix-workflow
type: task
status: open
priority: high
created: 2026-09-27
updated: 2026-09-27
agent: cowork
tags: [ci, tests, github-actions]
milestone: v4.3.0-developer-experience-and-runtime-resilience
blocked_by: [bug--py310-fstring-syntax-error, bug--non-hermetic-global-skill-tests]
related: [feat--git-level-gate-enforcement]
---

# CI workflow running the test suite on a Python and OS matrix

## Problem

`.github/workflows/` contains only `pages.yml` (docs and dashboard publishing on Python 3.12). Nothing runs the 639-test suite, the syntax gate, the typography check or the dashboard type check on push or pull request. This is how `bug--py310-fstring-syntax-error` shipped in v4.2.0 unnoticed.

## Requirements

- REQ-1: New workflow `.github/workflows/tests.yml` on `push` and `pull_request`.
- REQ-2: Matrix: Python 3.10, 3.11, 3.12, 3.13 x `ubuntu-latest`, `windows-latest` (macOS optional).
- REQ-3: Runs the canonical entry point `python .along/scripts/test.py` (not raw `unittest`), with `ruamel.yaml` and the `dash` extra installed via `uv`.
- REQ-4: Separate job for `packages/dashboard-ui`: `pnpm install --frozen-lockfile` and `pnpm --filter @along/dashboard-ui typecheck`.
- REQ-5: Runs `along sanitize` (check mode) and the Markdown link gate.
- REQ-6: Release engine (`/along-version-bump`) documents that a green CI run is the release precondition.

## Acceptance Criteria

- [ ] Workflow is green on all matrix cells on `main`
- [ ] A deliberately broken 3.10-only syntax change fails CI
- [ ] README or `docs/topic--setup-and-workflow.md` shows the CI badge and the supported matrix
- [ ] Automated tests passing
