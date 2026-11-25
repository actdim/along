# Living Plan: bug--commit-gates-skip-chained-and-dash-c-commits

Execution Mode: Direct (single cohesive bug fix within the `alongkit.hooks` subsystem and its unit tests; pre-approved for autonomous execution).

## Context

Both runtime commit gates (`commit_issue_binding` and `commit_no_conflict_markers`) in `scripts/alongkit/hooks/default_gates.yaml` filter `CommandLine` with `^git\s+commit`, and `check_staged_conflict_markers` in `scripts/alongkit/hooks/predicates.py` re-checks `re.match(r"^git\s+commit\b", cmd)` and slices `cmd[len("git commit"):]`. As a result, chained commands (`cd /tmp && git commit ...`, `cd /tmp; git commit ...`, `echo x | git commit ...`) and `git -C <path> commit ...` bypass runtime enforcement.

Meanwhile, `commit_no_ai_coauthor`'s predicate (`check_ai_coauthor` in `predicates.py`) defines a separate private `_GIT_COMMIT_RE`.

## Steps

- [x] Step 1: Support shared pattern references in `declarative.py` and shared git global-option parsing in `shellparse.py` / `deletion.py`
  - Extract `_resolve_symbol(dotted_path)` in `scripts/alongkit/hooks/declarative.py` shared by `resolve_handler` and a new `resolve_pattern(spec)` supporting `{ref: dotted.module.PATTERN}` in `match_args` and `rule.pattern`.
  - Add `git_subcommand(words, cwd="")` in `scripts/alongkit/hooks/shellparse.py` and delegate `deletion._strip_git_globals` / `deletion._git_cwd` to it so `-C <dir>` and git global option stripping are defined once.
- [x] Step 2: Centralize `GIT_COMMIT_RE` and commit-segment resolution in `predicates.py` and wire all commit gates in `default_gates.yaml`
  - Define `GIT_COMMIT_RE` once in `scripts/alongkit/hooks/predicates.py` (unanchored, word-bounded, supporting `git commit`, `git.exe`, `-C <path>` including quoted paths, `-c`, `--git-dir`, `--work-tree`, `--namespace`, `--no-pager`, and avoiding `git commit-tree` via `(?!-)`).
  - Add shared helpers `_command_base_cwd`, `_has_commit_all_flag`, `_extract_git_commit_invocations`, and `_run_git_diff_for_commit` in `predicates.py`.
  - Add `check_commit_issue_binding` so non-commit commands mentioning `"git commit"` (such as `rg "git commit"` or `git log --grep="git commit"`) are not falsely rejected by `commit_issue_binding`.
  - Update `check_staged_conflict_markers` and `check_ai_coauthor` to use `GIT_COMMIT_RE` and the shared invocation helpers (handling `cd <dir>`, `git -C <dir>`, `-a`/`--all`, and `-F <file>` accurately).
  - Update `scripts/alongkit/hooks/default_gates.yaml` so `commit_issue_binding` and `commit_no_conflict_markers` reference `alongkit.hooks.predicates.GIT_COMMIT_RE` in `match_args` (and `commit_issue_binding` runs `check_commit_issue_binding` before its `regex_match` rule).
- [x] Step 3: Add comprehensive tests and verify
  - Update/expand `tests/test_conflict_marker_gate.py`, `tests/test_ai_coauthor_attribution.py`, and `tests/test_declarative_gates.py` to test all invocation shapes (`git commit`, `cd ... && git commit`, `...; git commit`, `... | git commit`, `git -C <path> commit`, quoted `-C`, non-commit false-positive resistance, `-am` in chained/subrepo invocations, and single-source pattern identity in `default_gates.yaml`).
  - Run targeted tests, full test suite (`$env:ALONGKIT_PROJECT_ENV="1"; C:\Users\Admin\.along\venv\Scripts\python.exe .along\scripts\test.py -q`), `along sanitize`, `along hook verify`, and `along kb sync` / doc updates if needed.
- [x] Step 4: Wrap, commit, and push
  - Check off acceptance criteria in `.along/ISSUES/bug--commit-gates-skip-chained-and-dash-c-commits.md` and mark completed steps in `plan.md`.
  - Wrap with `along wrap`, verify commit and push (`git status -s` clean).
