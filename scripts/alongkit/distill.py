"""
alongkit.distill - reduce noisy command output to a high-signal observation.

Raw test/build output injected into an agent's context costs tokens and buries the one
line that matters. `distill()` turns it into a bounded observation:

- exit 0: one `PASS:` line plus at most a few runner summary lines (`Ran 759 tests`,
  `12 passed`, `Build succeeded`).
- exit != 0: ANSI codes, spinner/progress redraws, dependency-resolver chatter,
  deprecation notices and passing-test lines are dropped; failure blocks (Python
  tracebacks, unittest FAIL/ERROR sections, pytest `E` lines, compiler `error:` lines,
  Rust panics) and the runner summary are kept, capped at `max_lines` / `max_bytes`.

The function is pure; callers keep the raw text (telemetry artifacts,
`.along/artifacts/lifecycle/<action>.log`) so nothing is lost.
"""

from __future__ import annotations

if __name__ == "__main__":
    import os
    raise SystemExit(
        f"{os.path.basename(__file__)} is a library module, not a command.\n"
        "Run: along test   (or: python scripts/along_exec.py test)"
    )

import os
import re
from dataclasses import dataclass
from typing import List, Optional, Sequence, Union

DEFAULT_MAX_LINES = 50
DEFAULT_MAX_BYTES = 2048
MAX_SUMMARY_LINES = 3

_ANSI_RE = re.compile(r"\x1b\[[0-9;?]*[ -/]*[@-~]|\x1b\][^\x07]*\x07")

#: Redraw residue: blank lines, progress rows, spinners.
_PROGRESS_RES = tuple(re.compile(p) for p in (
    r"^\s*$",
    r"^[\s.sExF]*\.[\s.sExF]*$",                     # unittest dot-progress rows
    r"^\s*[|/\\\-]\s*$",                             # spinner frames
    r"^\s*\[?[#=>\-\s]*\]?\s*\d{1,3}(\.\d+)?%",      # progress bars / percentages
))

#: Chatter that is noise even inside a failure block.
_CHATTER_RES = tuple(re.compile(p) for p in (
    r"(?i)\bdeprecat(ed|ion)\b",
    r"(?i)^\s*(npm|pnpm|yarn) (warn|notice)\b",
    r"(?i)^\s*\[notice\]",
    r"(?i)^\s*(collecting|downloading|installing collected|requirement already satisfied|using cached)\b",
    r"(?i)^\s*(resolved|prepared|installed|uninstalled|audited|downloaded) \d+ packages?\b",
    r"(?i)^\s*(added|removed|changed) \d+ packages?\b",
    r"(?i)^->\s*\[along\] resolving dependencies",
    r" \.\.\. ok$",                                  # unittest -v passing line
    r"(?i)\bPASSED\b(\s+\[\s*\d+%\])?\s*$",          # pytest -v passing line
    r"^test \S+ \.\.\. ok$",                         # cargo test passing line
    r"(?i)^\s*(compiling|checking|fresh|finished) \S+ v\d",  # cargo build chatter
    r"(?i)^\s*warning: unused",
    r"^\s*[~^]+\s*$",                                # Python 3.11+ traceback caret underlines
))

#: Everything that carries no diagnostic value on failure.
_NOISE_RES = _PROGRESS_RES + _CHATTER_RES

#: Lines that open or carry a failure signal.
_SIGNAL_RES = tuple(re.compile(p) for p in (
    r"^Traceback \(most recent call last\):",
    r"^(FAIL|ERROR): ",
    r"^E\s{2,}",
    r"(?i)\berror(\[[A-Z]?\d+\])?:",
    r"(?i)^\s*(FAILED|FAILURES|ERRORS)\b",
    r"\bAssertionError\b|\bassert\b",
    r"^\w+(\.\w+)*(Error|Exception)\b",
    r"panicked at",
    r"^\s*File \"[^\"]+\", line \d+",
    r"^\s*at .+\(.+:\d+:\d+\)$",                    # JS stack frames
    r"^\s*\S+\.(py|ts|tsx|js|rs|cs|go):\d+",
    # jest/vitest failure glyphs: heavy x U+2715, multiplication sign U+00D7, ASCII x
    r"(?i)^\s*(" + chr(0x2715) + "|" + chr(0xD7) + r"|x) ",
))

#: Final runner summaries worth keeping in both outcomes.
_SUMMARY_RES = tuple(re.compile(p) for p in (
    r"^Ran \d+ tests? in ",
    r"^(OK|FAILED)( \(.*\))?$",
    r"(?i)^=+ .*\b(passed|failed|error)s?\b.* =+$",
    r"(?i)^\s*\d+ (passed|failed)\b",
    r"^test result: ",
    r"(?i)^\s*Tests?:\s+\d+",
    r"(?i)^\s*build (succeeded|failed)",
    r"(?i)^\s*\d+ error\(s\)",
    r"(?i)^\s*found \d+ errors?",
))

_BLOCK_RULE_RE = re.compile(r"^(=|-|_){20,}\s*$|^_{3,} .+ _{3,}$")


@dataclass(frozen=True)
class Observation:
    text: str            # distilled observation for the agent / span
    ok: bool
    raw_lines: int
    kept_lines: int

    @property
    def reduction(self) -> float:
        """Fraction of lines removed (0.0 .. 1.0)."""
        return 0.0 if not self.raw_lines else 1.0 - self.kept_lines / self.raw_lines


def clean_lines(text: str) -> List[str]:
    """Strip ANSI codes and resolve carriage-return redraws to their final frame."""
    lines = []
    for raw in _ANSI_RE.sub("", text or "").replace("\r\n", "\n").split("\n"):
        lines.append(raw.rsplit("\r", 1)[-1].rstrip())
    return lines


def _is(res: Sequence[re.Pattern], line: str) -> bool:
    return any(r.search(line) for r in res)


def _cmd_label(cmd: Union[Sequence[str], str, None]) -> str:
    if cmd is None:
        return "command"
    if isinstance(cmd, str):
        label = cmd
    else:
        # Absolute interpreter / script paths add nothing but length: keep the name.
        label = " ".join(os.path.basename(str(c)) if os.path.isabs(str(c)) else str(c) for c in cmd)
    return label if len(label) <= 120 else label[:117] + "..."


def _summaries(lines: Sequence[str]) -> List[str]:
    found = [line.strip() for line in lines if _is(_SUMMARY_RES, line)]
    return found[-MAX_SUMMARY_LINES:]


def _failure_lines(lines: Sequence[str]) -> List[str]:
    """Keep failure blocks: a signal line opens a block that runs until a blank line,
    a rule line, or another block; context lines inside a block survive noise filtering
    (they are the assertion diff and the source excerpt)."""
    kept: List[str] = []
    in_block = False
    for line in lines:
        if _BLOCK_RULE_RE.match(line):
            in_block = False
            continue
        if _is(_CHATTER_RES, line):
            continue
        if _is(_SUMMARY_RES, line):         # reported once, after the failures
            in_block = False
            continue
        if _is(_SIGNAL_RES, line):
            in_block = True
            kept.append(line)
            continue
        if in_block:
            if not line.strip():
                in_block = False
                continue
            kept.append(line)
    return kept


def _cost(lines: Sequence[str]) -> int:
    return sum(len(line.encode("utf-8")) + 1 for line in lines)


def _cap(lines: List[str], max_lines: int, max_bytes: int, raw_ref: Optional[str]) -> List[str]:
    """First lines that fit, plus an omission marker; the marker counts toward both limits."""
    if len(lines) <= max_lines and _cost(lines) <= max_bytes:
        return list(lines)
    where = f"; raw output: {raw_ref}" if raw_ref else ""
    marker_budget = len(f"... [{len(lines)} more line(s) omitted{where}]") + 1
    out: List[str] = []
    size = 0
    for line in lines:
        cost = len(line.encode("utf-8")) + 1
        if len(out) >= max_lines - 1 or size + cost > max_bytes - marker_budget:
            break
        out.append(line)
        size += cost
    out.append(f"... [{len(lines) - len(out)} more line(s) omitted{where}]")
    return out


def distill(stdout: str, stderr: str = "", returncode: int = 0,
            cmd: Union[Sequence[str], str, None] = None, duration: Optional[float] = None,
            max_lines: int = DEFAULT_MAX_LINES, max_bytes: int = DEFAULT_MAX_BYTES,
            raw_ref: Optional[str] = None) -> Observation:
    """Distill a finished command's output. `raw_ref` names where the raw text lives."""
    combined = (stdout or "") + ("\n" if stdout and stderr else "") + (stderr or "")
    lines = clean_lines(combined)
    raw_count = len([line for line in lines if line.strip()])
    timing = f", {duration:.1f}s" if duration is not None else ""
    label = _cmd_label(cmd)

    if returncode == 0:
        body = [f"PASS: {label} completed successfully (code 0{timing})"]
        body += _summaries(lines)
        return Observation("\n".join(body), True, raw_count, len(body))

    header = f"FAIL: {label} exited with code {returncode}{timing}"
    failures = _failure_lines(lines)
    if not failures:
        # No recognizable failure block: fall back to the non-noise tail.
        signal = [line for line in lines if not _is(_NOISE_RES, line)]
        failures = signal[-(max_lines - 2):]
    # The runner summary is reserved up front so the cap can never cut it off.
    summary = [s for s in _summaries(lines) if s not in failures]
    tail = summary + ([f"(raw output: {raw_ref})"] if raw_ref else [])
    budget_lines = max(2, max_lines - 1 - len(tail))
    budget_bytes = max(200, max_bytes - _cost([header]) - _cost(tail))
    body = _cap(failures, budget_lines, budget_bytes, raw_ref)
    if raw_ref and body and body[-1].startswith("... ["):
        tail = summary                      # the omission marker already names raw_ref
    text = "\n".join([header, *body, *tail])
    return Observation(text, False, raw_count, 1 + len(body) + len(tail))


def estimate_tokens(text: str) -> int:
    """Rough token estimate (4 characters per token) for reduction reporting and tests."""
    return (len(text or "") + 3) // 4


__all__: Sequence[str] = ("Observation", "distill", "clean_lines", "estimate_tokens",
                          "DEFAULT_MAX_LINES", "DEFAULT_MAX_BYTES")
