---
protocol: along
protocol_version: "4.4.8"
date: 2026-10-09
slug: inquiry-readonly-commands-blocked
agent: antigravity
branch: main
commit: d1c8c7c
summary: Completed bug--inquiry-readonly-commands-blocked
milestone: v4.5.0-multi-user-merge-automation
issues_advanced: []
issues_completed: [bug--inquiry-readonly-commands-blocked]
decisions: []
risks_logged: []
spikes_conducted: []
---

# Session: Inquiry readonly commands blocked

## Summary
Completed bug--inquiry-readonly-commands-blocked

## Decisions
- None (confirmed at wrap: no architectural decisions).

## Blackboard Record

Execution mode: direct; plan revision 1; approved: true.

### Attributed Files

| Path | Kind | Edits | Last edit | Sessions |
| --- | --- | --- | --- | --- |
| `.along/ISSUES/bug--inquiry-readonly-commands-blocked.md` | state | 1 | 2026-10-09T09:12:57Z | antigravity--1f2c8ca5-823b-4cb2-a4ab-a479e17d4858 |
| `.along/ISSUES/bug--plan-gate-blocks-help.md` | state | 1 | 2026-10-09T09:13:08Z | antigravity--1f2c8ca5-823b-4cb2-a4ab-a479e17d4858 |
| `docs/topic--runtime-hooks-and-gates.md` | docs | 1 | 2026-10-09T09:12:41Z | antigravity--1f2c8ca5-823b-4cb2-a4ab-a479e17d4858 |
| `scripts/alongkit/hooks/shellparse.py` | source | 4 | 2026-10-09T09:05:01Z | antigravity--1f2c8ca5-823b-4cb2-a4ab-a479e17d4858 |
| `tests/test_shell_classification.py` | source | 3 | 2026-10-09T09:06:17Z | antigravity--1f2c8ca5-823b-4cb2-a4ab-a479e17d4858 |
| `tests/test_subcommand_help.py` | source | 3 | 2026-10-09T09:08:13Z | antigravity--1f2c8ca5-823b-4cb2-a4ab-a479e17d4858 |

### Plan

#### Living Plan: inquiry-readonly-commands-blocked

##### Revision 1 (2026-10-09T09:01:21Z, plan approve --plan-file)

#### Implementation Plan: Inquiry Read-Only Commands and Help Flag Classification

##### Context and Scope
- Bound Issues: `bug--inquiry-readonly-commands-blocked`, `bug--plan-gate-blocks-help`
- Target components:
  - [shellparse.py](../../../scripts/alongkit/hooks/shellparse.py)
  - [test_shell_classification.py](../../../tests/test_shell_classification.py)
  - [test_subcommand_help.py](../../../tests/test_subcommand_help.py)
- Execution Mode: Direct (modifications localized to 1 engine module and 2 test files; <= 3 files)

##### Critical Technical Analysis and Trade-offs
1. **Script Blocks (`{ ... }`) vs Segment Splitting**:
   - In PowerShell, `{ ... }` acts as a script block parameter (e.g. `ForEach-Object { ... }`, `Measure-Command { ... }`).
   - Semicolons `;` and pipes `|` inside script blocks must not split the outer pipeline.
   - Braces must only be treated as script blocks when standalone or preceded by whitespace/delimiters. Non-whitespace preceding characters (e.g. `stash@{0}`, `${VAR}`) must not be captured as script blocks.
   - The body inside `{ ... }` must be recursively validated. Any mutating command inside (e.g. `Remove-Item`, `rm -rf`, or mutating redirect) must strictly reject the entire command.
2. **Safe Redirections vs Working Tree Mutation**:
   - Redirecting output to null devices (`/dev/null`, `nul`, `$null`), temporary locations (`$env:TEMP`, `%TEMP%`, `/tmp`, system temp directory), `.along/artifacts/`, `.along/.session/`, or `.along/diagnostics/` does not modify repository source files.
   - Any redirection targeting working tree paths (e.g. `> src/a.py`, `> out.txt`) remains strictly classified as mutating.
3. **Along CLI `--help` / `-h` Classification**:
   - Any invocation of Along CLI (`along`, `along_exec.py`, `scripts/along_*.py`, `.along/scripts/*.py`, `along-*`) passing `--help`, `-h`, or `help` is inherently non-mutating and should pass the plan gate regardless of the subcommand.
4. **POSIX and PowerShell Read-Only Additions**:
   - Add `Test-Path`, `Select-Object`, `Measure-Object`, `od`, `date`, `Compare-Object`, `Out-String`, `Out-Null`, `Out-Host` to `_READ_COMMANDS`.
   - Add `session list`, `plan status`, `issue list`, `milestone list`, `decision list`, `rules status`, `rules diff` to `_ALONG_READ`.
   - Add bash arithmetic expansion `$(( ... ))` with recursive command substitution verification.
   - Allow pipeline variable/property reads (e.g. `$_.Name`, `$_.FullName`, `$item.Property`) in script blocks.

##### Proposed Changes

###### 1. Engine: `scripts/alongkit/hooks/shellparse.py`
- Update `_READ_COMMANDS` and `_ALONG_READ` sets with new read-only inspection commands and subcommands.
- Implement `_is_safe_redirect(target)` and update `_has_write_redirect(segment)` to permit redirects to temp/scratch/artifacts while rejecting working tree writes.
- Update `split_segments(command)`:
  - Track brace depth `brace_depth` outside quotes to avoid splitting on `;`, `|`, `&&`, `||`, `&`, `\n` inside script blocks.
  - Parse bash arithmetic expansion `$(( ... ))` and verify inner substitutions.
- Implement `_split_script_block(segment)` and script block validation in `_segment_is_read_only(segment)`:
  - Validate script blocks for `ForEach-Object`, `Measure-Command`, `Where-Object`, and bare `{ ... }`.
  - Validate pipeline variable and property read tokens (`$_.Name`, `$_.FullName`).
- Recognize Along CLI entry points (`along`, `along_exec.py`, `scripts/along_*.py`, `.along/scripts/*.py`, `along-*`) with `--help` or `-h` as read-only.

###### 2. Tests: `tests/test_shell_classification.py` and `tests/test_subcommand_help.py`
- Add all 6 inquiry regression cases to `READ_ONLY`:
  - `Test-Path .along/.migration-backup/x; git status --porcelain -u | Select-Object -First 20`
  - `Get-Content a.json; Get-Content b.md -TotalCount 25; Get-ChildItem dir | ForEach-Object { $_.Name; Get-Content $_.FullName }`
  - `along session list; along plan status; git status --short | Measure-Object | Select-Object Count`
  - `Measure-Command { python .along/scripts/test.py -q *> $env:TEMP\t.txt } | Select-Object TotalSeconds`
  - `tail -c 1 .along/HISTORY.md | od -c | head -1`
  - `s=$(date +%s); python .along/scripts/test.py -q 2>&1 | grep -E "^Ran |^OK"; echo $(( $(date +%s) - s ))`
- Add mutating counter-tests to `MUTATING`:
  - `ForEach-Object { rm -rf src }`
  - `ForEach-Object { $_.Name; Remove-Item $_.FullName }`
  - `Measure-Command { Remove-Item src }`
  - `Measure-Command { python .along/scripts/test.py -q > src/a.py }`
  - `echo $(( $(rm -rf src) + 1 ))`
- Add hermetic help gate tests:
  - `along commit --help`
  - `along bump --help`
  - `python scripts/along_commit.py --help`
  - `python scripts/along_commit.py -h`
  - `python scripts/along_version_bump.py --help`

##### Verification Plan
1. Run `python .along/scripts/test.py -q` ensuring zero failures across all 1129+ tests.
2. Run targeted test: `python .along/scripts/test.py -q -k "shell_classification or subcommand_help"`.
3. Check typography cleanly via `python scripts/along_exec.py sanitize` (zero violations).

### Execution Trace

#### Execution Trace: inquiry-readonly-commands-blocked
- 2026-10-08T18:25:06Z denied [require_plan_approval] run_command: Inquiry Read-Only Invariance [gate: require-plan-approval]: No approved plan for issue 'inquiry-readonly-commands-blocked' (phase: 'planning', plan_approved:... (x5)
- 2026-10-09T09:01:21Z plan recorded: revision 1 (plan approve --plan-file)
- 2026-10-09T09:01:21Z plan approved (along plan approve)
- 2026-10-09T09:05:01Z edit scripts/alongkit/hooks/shellparse.py (x4)
- 2026-10-09T09:06:17Z edit tests/test_shell_classification.py (x3)
- 2026-10-09T09:08:13Z edit tests/test_subcommand_help.py (x3)
- 2026-10-09T09:12:41Z edit docs/topic--runtime-hooks-and-gates.md
- 2026-10-09T09:12:57Z edit .along/ISSUES/bug--inquiry-readonly-commands-blocked.md
- 2026-10-09T09:13:08Z edit .along/ISSUES/bug--plan-gate-blocks-help.md
- 2026-10-09T09:16:38Z test pass (Wrap Quality Gate)
