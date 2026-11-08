# Living Plan: Fix cli_safety false positives and detection gaps (reframed)

## Execution Mode
Direct (2 production files, 2 test files).

## Revision note (2026-11-08 review)
The previous revision rested on premises that do not hold:
- REQ-1 is already satisfied. `scripts/alongkit/hooks/default_gates.yaml:70` sets `cli_safety`
  to `warn` in every profile, `config.py:54` maps `warn` to `HookMode.SHADOW`, and
  `tests/test_cli_safety_patterns.py::test_warns_by_default` asserts it is not enforcing. Only a
  bare `CliSafetyGate.evaluate()` returns `DENY`; the engine downgrades it. Nothing blocks with
  exit 2 at runtime.
- Several cited false positives are already fixed: PowerShell writers, `sed -i` and `perl -i`
  match only in command position, so `Select-String -Pattern 'Set-Content'` does not trip;
  the heredoc regex excludes `<<<` and numeric shifts.
- Removing the writer patterns removes the only signal for the protocol rule
  `[gate: cli_safety] file content via file tools, never heredocs or python -c` (AGENTS.md).
  The gate is already non-blocking, so the cost of keeping it is a warning, not friction.
- `check_approval_record_shell_write` (`predicates.py:1004`) uses `shellwrite._lex` to stop
  shell writes that forge the plan-approval record. Simplifying it is a security regression.
- The pip pattern the old plan called "near-zero false positive" has real false positives.

The issue title, requirements and acceptance criteria were rewritten (2026-11-08) to match this plan.

## 1. Measured behavior (probe, 2026-11-08)

| Command | Current hits | Wanted |
| :--- | :--- | :--- |
| `git commit -m "fix <<EOF handling in parser"` | Heredoc | none |
| `grep -rn '<<EOF' scripts` | Heredoc | none |
| `echo $((x << y))` | Heredoc | none |
| `uv pip install requests` | pip global | none (project venv) |
| `pip install -r requirements.txt` | pip global | keep warning only outside a venv (see 2.2) |
| `python -m pip install -e .` | none | none |
| `Select-String -Pattern 'Set-Content' x.py` | none | none |
| `npm i -g typescript` | none | npm global (gap) |
| `pacman -S ripgrep` | none | system install (gap) |

## 2. Changes
### 2.1 Heredoc: quote-aware, body-required
Use the existing `shellwrite._lex` tokens: flag `<<WORD` only when the operator is unquoted and
outside `$(( ))`, and the command contains a following line (a heredoc body). Single-line
commands and quoted occurrences never match. Keep the PowerShell here-string rule as is.

### 2.2 pip
- Never flag `uv pip ...`, `python -m pip` with `-e`, `--user`, `--target`, `--prefix`.
- Flag bare `pip install` / `pip3 install` / `python -m pip install` only when no virtual
  environment is active (`VIRTUAL_ENV` unset in the hook environment and no `.venv` in the
  repo); otherwise allow.

### 2.3 Close gaps
- npm: `\bnpm\s+(?:install|i|add)\b[^|;&\n]*\s(?:-g|--global)\b` (flag anywhere in the segment).
- System managers: add `pacman -S`, `yum install`, `dnf install`, `scoop install`, `apt install`;
  anchor all in command position like the PowerShell rules.

### 2.4 Unchanged
`InlineEchoWriter`, PowerShell writers, `[IO.File]::Write*`, `New-Item -Value`, `sed -i`,
`perl -i`, inline Python writers, the `python -c` internal-module probe,
`check_approval_record_shell_write`, `shellparse.py` (used by `deletion.py`, `escalation.py`).
No mode change in `gates.yaml` or `config.py`.

## 3. Steps
1. `scripts/alongkit/hooks/predicates.py`: replace the heredoc regex with a callable matcher
   (same `(matcher, label)` shape as `InlineEchoWriter`), update pip / npm / system-manager
   patterns.
2. If the heredoc matcher grows past a few lines, place it in `shellwrite.py` next to the lexer.
3. `tests/test_cli_safety_patterns.py`: add every row of the table in section 1 to the
   `BLOCKED` / `ALLOWED` matrices; keep all existing rows.
4. `tests/test_hooks_core.py`: a venv-active vs no-venv case for the pip rule.

## 4. Verification
- `python .along/scripts/test.py test_cli_safety_patterns.py test_hooks_core.py`
- Full `python .along/scripts/test.py`
- `python scripts/sanitize_typography.py --check`

## 5. Follow-up (not in this issue)
If the team still wants `cli_safety` removed rather than fixed, that is a protocol change to
AGENTS.md's gate list and needs its own ADR superseding the current rule.
