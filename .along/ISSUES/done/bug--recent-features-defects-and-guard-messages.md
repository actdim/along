---
protocol: along
slug: recent-features-defects-and-guard-messages
type: bug
status: done
completed: 2026-09-04
priority: high
created: 2026-09-04
updated: 2026-09-04
agent: antigravity
tags: [bug, alongkit, rules, guards]
milestone: v3.0.0-global-quality-revision
blocked_by: []
related: [debt--exception-swallowing-hides-failures, debt--protocol-quality-audit-remediation]
---

# Fix recent feature quality defects and library execution guard messages

## Problem

A critical review of recent commits identified several defects in newly added logic:
1. `scripts/alongkit/rules.py` contains a bare `except: pass` on line 53, violating the project's own Python coding standards (`rules/languages/python.md`).
2. `scripts/alongkit/rules.py` uses `os.path.normpath` without `os.path.normcase` when comparing file paths for rule pruning on line 96, creating a Windows case-sensitivity bug.
3. `scripts/alongkit/rules.py` injects empty markers (`<!-- BEGIN ALONG-RULES -->` and `<!-- END ALONG-RULES -->`) or appends `## Project specifics` to `AGENTS.md` even when no rules match (`required` is empty).
4. `scripts/alongkit/rules.py` lacks a library execution guard.
5. All 15 library modules in `scripts/alongkit/*.py` have execution guards that print `__main__` instead of the module name because `__name__` evaluates to `"__main__"` when run directly.
6. All 15 library modules have a copy-pasted recovery message `"Run: along kb-sync"` regardless of the module's domain.
7. Zero unit tests cover `alongkit.rules`.
8. `.along/ISSUES.md` projection has stale/corrupted entries from manual edits.

## Acceptance Criteria

- [x] `rules.py` catches specific exceptions (`(OSError, UnicodeDecodeError, json.JSONDecodeError)`) instead of bare `except:`.
- [x] `rules.py` uses `os.path.normcase` for Windows case-insensitive path comparisons in pruning.
- [x] `rules.py` does not inject empty rule blocks or headers into `AGENTS.md` when `required` is empty.
- [x] `rules.py` has a standard library execution guard.
- [x] All 16 `alongkit` modules use `os.path.basename(__file__)` in execution guard messages so the real file name is printed instead of `__main__`.
- [x] Execution guard recovery messages in `alongkit` modules give sensible hints (e.g. `along --help` or specific commands).
- [x] Unit tests added in `tests/test_rules.py` covering signature detection, rules attachment, pruning, and AGENTS.md update.
- [x] `.along/ISSUES.md` projection is recompiled and clean.
- [x] Entire test suite (`python .along/scripts/test.py`) passes 100%.
