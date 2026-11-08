---
protocol: along
protocol_version: "4.7.0"
slug: simplify-cli-safety-gate-and-predicates
type: task
status: done
completed: 2026-11-08
priority: medium
created: 2026-11-07
updated: 2026-11-08
agent: antigravity
tags: [hooks, gates, cli-safety, predicates, false-positives]
blocked_by: []
related: [debt--gate-config-layers, debt--gate-simplification]
---

# Fix cli_safety false positives and detection gaps

Keep the `cli_safety` gate and its mode as they are, and fix the measured false positives (heredoc detection, pip in project environments) and gaps (npm global installs, `pacman -S` and other system managers) in `DANGEROUS_CLI_PATTERNS`.

## Context and Problem Statement

The original framing (switch to shadow mode, strip the writer patterns, streamline `shellwrite.py` / `shellparse.py`) was withdrawn after the 2026-11-08 review (see [plan.md](./task--simplify-cli-safety-gate-and-predicates/plan.md)):
- `cli_safety` is already non-blocking: `default_gates.yaml` sets `warn` in every profile, `config.py` maps `warn` to `HookMode.SHADOW`, and `test_warns_by_default` asserts it.
- PowerShell writers, `sed -i` and `perl -i` already match only in command position.
- The writer patterns are the only signal for the AGENTS.md rule `[gate: cli_safety] file content via file tools, never heredocs or python -c`.
- `check_approval_record_shell_write` relies on `shellwrite._lex` to stop forging the plan-approval record; simplifying it is a security regression.

Measured behavior of the current patterns:

| Command | Current | Wanted |
| :--- | :--- | :--- |
| `git commit -m "fix <<EOF handling in parser"` | heredoc | none |
| `grep -rn '<<EOF' scripts` | heredoc | none |
| `echo $((x << y))` | heredoc | none |
| `uv pip install requests` | pip global | none |
| `pip install -r requirements.txt` (venv active) | pip global | none |
| `npm i -g typescript` | none | npm global |
| `pacman -S ripgrep` | none | system install |

## Requirements

- REQ-1 (Heredoc): Flag `<<WORD` only when it is unquoted, outside `$(( ))`, and the command has a following line (a heredoc body). Single-line commands and quoted occurrences never match. PowerShell here-string rule unchanged.
- REQ-2 (pip): Never flag `uv pip ...` or installs with `-e`, `--user`, `--target`, `--prefix`. Flag `pip` / `pip3` / `python -m pip install` only when no virtual environment is active (`VIRTUAL_ENV` unset and no repo `.venv`).
- REQ-3 (npm): Flag `npm install|i|add` with `-g` / `--global` anywhere in the segment.
- REQ-4 (System managers): Detect `choco`, `winget`, `scoop`, `apt`, `apt-get`, `brew`, `yum`, `dnf` `install` and `pacman -S`, in command position.
- REQ-5 (Unchanged): Gate mode and profiles, `InlineEchoWriter`, PowerShell / .NET / `New-Item -Value` writers, `sed -i`, `perl -i`, inline Python writers, the `python -c` internal-module probe, `check_approval_record_shell_write`, `shellparse.py`.
- REQ-6 (Tests): Every row of the table above added to `tests/test_cli_safety_patterns.py`; existing rows kept; `tests/test_hooks_core.py` covers pip with and without an active venv.
- REQ-7 (ASCII Typography): `python scripts/sanitize_typography.py --check` passes.

## Acceptance Criteria

- [x] The three heredoc false positives pass; real multi-line heredocs (`cat <<EOF > f` followed by a body) are still flagged.
- [x] `uv pip install` and venv-scoped `pip install -r` pass; bare `pip install x` outside a venv is flagged.
- [x] `npm i -g` and `pacman -S` are flagged.
- [x] No change to gate mode, writer patterns, `check_approval_record_shell_write` or `shellparse.py`.
- [x] `python .along/scripts/test.py test_cli_safety_patterns.py test_hooks_core.py` and the full suite pass.
- [x] `python scripts/sanitize_typography.py --check` passes.
- [x] Removing `cli_safety` altogether, if still wanted, is a separate ADR, not this issue.
