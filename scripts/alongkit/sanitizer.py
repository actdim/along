#!/usr/bin/env python3
"""
alongkit.sanitizer - Policy and reporting for the ASCII typography rule.

`alongkit.typography` owns the character table and the pure string transformation.
This module owns everything that touches a user's files: which files the rule
governs, how they are read, whether anything is written at all, and what the caller
is told afterwards.

The behaviour it replaces, from `[bug--typography-sanitizer-destroys-non-utf8-files]`:

- The old sanitizer read every candidate with `errors="ignore"` and then overwrote
  the file with the decoded result. Any cp1251, latin-1, or UTF-16 file in the
  repository lost the undecodable bytes permanently, with no warning and no backup.
  Here a file that is not valid UTF-8 is skipped, reported, and left byte-identical.
- It wrote with `newline="\\n"`, forcing LF onto `.ps1` and `.bat` files that
  `.gitattributes` declares `eol=crlf`. Here the bytes a file already uses for its
  line endings are preserved: the read keeps them verbatim and the write does not
  translate. Nothing parses `.gitattributes`, because preserving what is there
  cannot contradict it.
- It rewrote `.json`, `.yaml`, and `.toml` unconditionally, so a French or Russian
  resource bundle was corrupted as a side effect of a commit. Data files are opt-in
  (`include_data=True`) and localized resource directories are never scanned.
- It had no mode other than "rewrite everything now", and its callers detected
  change by string-matching its stdout. Here `Mode.CHECK` is the default, writing
  requires `Mode.WRITE`, and callers consume a `Report`.

Scanning deliberately descends into hidden directories. The old implementation used
`glob`, which never matches a leading dot, so a byte order mark inside `.along/**`
was invisible to the tool meant to remove it.
"""


from __future__ import annotations
if __name__ == "__main__":
    raise SystemExit(
        f"{__name__} is a library module, not a command.\n"
        "Run: along kb-sync   (or: python scripts/along_exec.py kb-sync)"
    )


import fnmatch
import os
from dataclasses import dataclass, field
from typing import Dict, Iterable, Iterator, List, Optional, Sequence, Tuple

from . import repo, textio, typography

#: File classes the ASCII typography rule governs by default: agent-authored prose
#: and the source files whose comments, docstrings, and string literals agents write.
#: Recorded as ADR-2026-09-01--typography-rule-scope.
DEFAULT_SUFFIXES: Tuple[str, ...] = (".md", ".py", ".sh", ".ps1", ".bat")

#: Structured data and configuration. Opt-in only: these files carry user and product
#: content as often as they carry agent-authored text, and a replacement inside one
#: changes data rather than prose.
DATA_SUFFIXES: Tuple[str, ...] = (".json", ".yaml", ".yml", ".toml")

#: Directories holding localized user-facing content. Never scanned, in any mode:
#: replacing a guillemet or a typographic apostrophe there is not a cleanup, it is a
#: translation defect.
LOCALIZED_DIRS: frozenset = frozenset({
    "locales", "locale", "i18n", "intl", "_locales",
    "lang", "langs", "translations", "translation",
})

#: Optional per-repository exclusion list, one glob per line, `#` for comments.
IGNORE_FILE = ".alongsanitizeignore"


class Mode:
    """What a run is allowed to do. `CHECK` is the default everywhere."""

    CHECK = "check"      # never writes; a finding is a failure (non-zero exit)
    DRY_RUN = "dry-run"  # never writes; a finding is informational
    WRITE = "write"      # applies the replacements

    ALL: Tuple[str, ...] = (CHECK, DRY_RUN, WRITE)


@dataclass(frozen=True)
class FileFinding:
    """What the rule found in one file, and whether it was acted on."""

    path: str                      # repository-relative, forward slashes
    replacements: int              # total banned characters present
    lines: List[int]               # 1-based line numbers carrying at least one
    counts: Dict[str, int]         # readable character name -> occurrences
    bom_removed: bool              # a leading byte order mark was, or would be, stripped
    written: bool                  # the file was actually rewritten

    def as_dict(self) -> dict:
        return {
            "path": self.path,
            "replacements": self.replacements,
            "lines": self.lines,
            "counts": self.counts,
            "bom_removed": self.bom_removed,
            "written": self.written,
        }


@dataclass(frozen=True)
class SkippedFile:
    """A candidate the sanitizer refused to touch, and why."""

    path: str
    reason: str

    def as_dict(self) -> dict:
        return {"path": self.path, "reason": self.reason}


@dataclass
class Report:
    """The machine-readable outcome of a run. This is what callers consume.

    Nothing downstream may go back to parsing the tool's printed output: the count
    line the commit engine used to grep for is a formatting detail, and it silently
    stopped matching the moment the wording changed.
    """

    mode: str
    root: str
    files_scanned: int = 0
    findings: List[FileFinding] = field(default_factory=list)
    skipped: List[SkippedFile] = field(default_factory=list)

    @property
    def files_with_findings(self) -> int:
        return len(self.findings)

    @property
    def files_written(self) -> List[str]:
        return [f.path for f in self.findings if f.written]

    @property
    def total_replacements(self) -> int:
        return sum(f.replacements for f in self.findings)

    @property
    def boms_removed(self) -> List[str]:
        """Every path whose leading byte order mark was, or would be, stripped.

        Reported by path on purpose: the strip used to be silent, so a BOM could
        appear and disappear across commits with nothing in the log to say so.
        """
        return [f.path for f in self.findings if f.bom_removed]

    @property
    def clean(self) -> bool:
        return not self.findings

    @property
    def exit_code(self) -> int:
        """0 unless a check-mode run found something to report."""
        if self.mode == Mode.CHECK and self.findings:
            return 1
        return 0

    def as_dict(self) -> dict:
        return {
            "mode": self.mode,
            "root": repo.normalize_posix(self.root),
            "files_scanned": self.files_scanned,
            "files_with_findings": self.files_with_findings,
            "total_replacements": self.total_replacements,
            "files_written": self.files_written,
            "boms_removed": self.boms_removed,
            "findings": [f.as_dict() for f in self.findings],
            "skipped": [s.as_dict() for s in self.skipped],
        }

    def summary_line(self) -> str:
        if self.clean:
            base = f"{self.files_scanned} files scanned, no banned characters"
        else:
            verb = "rewritten" if self.mode == Mode.WRITE else "affected"
            base = (f"{self.files_scanned} files scanned, "
                    f"{self.total_replacements} banned characters in "
                    f"{self.files_with_findings} files {verb}")
        if self.skipped:
            base += f", {len(self.skipped)} skipped"
        return base


def load_ignore_patterns(root: str) -> List[str]:
    """Globs from `<root>/.alongsanitizeignore`, or an empty list when absent.

    Read leniently: an unreadable or undecodable ignore file must not abort a run
    that is otherwise safe, it just means nothing extra is excluded.
    """
    path = os.path.join(root, IGNORE_FILE)
    if not os.path.isfile(path):
        return []
    try:
        text = textio.read_text(path, strict=False)
    except OSError:
        return []
    patterns = []
    for line in text.splitlines():
        entry = line.strip()
        if entry and not entry.startswith("#"):
            patterns.append(entry)
    return patterns


def matches_exclude(rel_path: str, patterns: Sequence[str]) -> bool:
    """True when the repository-relative posix path is covered by any pattern.

    A pattern matches the whole path (`docs/*.md`), a trailing directory
    (`fixtures/`), or a single path segment (`vendor`), which is the subset of
    gitignore semantics an exclusion list actually needs.
    """
    segments = rel_path.split("/")
    for raw in patterns:
        pattern = raw.strip()
        if not pattern:
            continue
        if pattern.endswith("/"):
            directory = pattern.rstrip("/")
            if directory in segments or fnmatch.fnmatch(rel_path, f"{directory}/*"):
                return True
            continue
        if fnmatch.fnmatch(rel_path, pattern):
            return True
        if fnmatch.fnmatch(rel_path, f"{pattern}/*") or f"/{pattern}/" in f"/{rel_path}":
            return True
        if any(fnmatch.fnmatch(segment, pattern) for segment in segments):
            return True
    return False


def target_suffixes(include_data: bool = False,
                    extra: Iterable[str] = ()) -> Tuple[str, ...]:
    """The suffix set for a run, normalized to a leading dot and lowercase."""
    suffixes = list(DEFAULT_SUFFIXES)
    if include_data:
        suffixes.extend(DATA_SUFFIXES)
    for item in extra:
        value = item.strip().lower()
        if not value:
            continue
        if not value.startswith("."):
            value = f".{value}"
        if value not in suffixes:
            suffixes.append(value)
    return tuple(suffixes)


def iter_targets(root: str,
                 include_data: bool = False,
                 extra_suffixes: Iterable[str] = (),
                 excludes: Sequence[str] = ()) -> Iterator[str]:
    """Absolute paths of the files a run may inspect, in a stable order."""
    suffixes = target_suffixes(include_data, extra_suffixes)
    patterns = list(excludes)
    for path in repo.iter_files(root, suffixes=suffixes, include_hidden=True,
                                extra_ignores=LOCALIZED_DIRS):
        rel = repo.normalize_posix(repo.safe_relpath(path, root))
        if patterns and matches_exclude(rel, patterns):
            continue
        yield path


def inspect(text: str) -> Tuple[str, int, List[int], Dict[str, int]]:
    """Pure analysis of one file's text.

    Returns `(cleaned, total, lines, counts)` where `counts` is keyed by readable
    character name, so a report says "3 non-breaking spaces" rather than a code point.
    """
    hits = typography.findings(text)
    counts: Dict[str, int] = {}
    lines: List[int] = []
    for line_number, _column, char in hits:
        name = typography.name_of(char)
        counts[name] = counts.get(name, 0) + 1
        if line_number not in lines:
            lines.append(line_number)
    cleaned, _changed = typography.clean(text)
    return cleaned, len(hits), lines, counts


def inspect_file(path: str, root: str, mode: str = Mode.CHECK
                 ) -> Tuple[Optional[FileFinding], Optional[SkippedFile]]:
    """Inspect one file and, in write mode only, rewrite it.

    Exactly one of the two returned values is set, or neither when the file is clean.
    A file that is not valid UTF-8 yields a `SkippedFile` and is never opened for
    writing: decoding it lossily and rewriting the result is how content disappears.
    """
    rel = repo.normalize_posix(repo.safe_relpath(path, root))
    try:
        original = textio.read_text(path, strict=True)
    except UnicodeDecodeError as exc:
        return None, SkippedFile(rel, f"not valid UTF-8 ({exc.reason} at byte {exc.start})")
    except OSError as exc:
        return None, SkippedFile(rel, f"unreadable ({exc.strerror or exc})")

    cleaned, total, lines, counts = inspect(original)
    if not total:
        return None, None

    bom_removed = original.startswith(textio.BOM)
    written = False
    if mode == Mode.WRITE:
        try:
            # `newline=None` writes the string byte for byte, so CRLF stays CRLF.
            textio.write_text(path, cleaned)
            written = True
        except OSError as exc:
            return None, SkippedFile(rel, f"unwritable ({exc.strerror or exc})")

    return FileFinding(path=rel, replacements=total, lines=lines, counts=counts,
                       bom_removed=bom_removed, written=written), None


def run(root: str,
        mode: str = Mode.CHECK,
        include_data: bool = False,
        extra_suffixes: Iterable[str] = (),
        excludes: Sequence[str] = (),
        use_ignore_file: bool = True) -> Report:
    """Scan `root` under `mode` and return the report. Writes only in `Mode.WRITE`."""
    if mode not in Mode.ALL:
        raise ValueError(f"unknown sanitizer mode: {mode!r} (expected one of {Mode.ALL})")

    root = os.path.abspath(root)
    patterns = list(excludes)
    if use_ignore_file:
        patterns.extend(load_ignore_patterns(root))

    report = Report(mode=mode, root=root)
    for path in iter_targets(root, include_data=include_data,
                             extra_suffixes=extra_suffixes, excludes=patterns):
        report.files_scanned += 1
        finding, skipped = inspect_file(path, root, mode)
        if finding:
            report.findings.append(finding)
        elif skipped:
            report.skipped.append(skipped)
    return report


def format_report(report: Report, verbose: bool = True) -> str:
    """Human-readable rendering of a report, for stderr or a gate message."""
    lines: List[str] = []
    if verbose:
        for finding in report.findings:
            detail = ", ".join(f"{count} {name}" for name, count in
                               sorted(finding.counts.items()))
            where = ", ".join(str(n) for n in finding.lines[:8])
            if len(finding.lines) > 8:
                where += ", ..."
            marker = "fixed " if finding.written else ""
            lines.append(f"  {marker}{finding.path}: {detail} (line {where})")
            if finding.bom_removed:
                verb = "removed" if finding.written else "present"
                lines.append(f"    byte order mark {verb}")
        for skipped in report.skipped:
            lines.append(f"  skipped {skipped.path}: {skipped.reason}")
    lines.append(report.summary_line())
    return "\n".join(lines)
