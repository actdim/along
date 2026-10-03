"""
alongkit.repochecks - repository-state checks for protocol rules that used to be prose.

Each check backs one catalogue gate (`default_gates.yaml`, `enforcement: [git, ci]`) and
is run by `alongkit.gitgates`: `pre-commit` passes the staged paths and reads the staged
blobs, `--ci` passes every tracked path and reads the checked-out tree. A check takes
`(paths, read, options)` and returns `[(location, message)]`; it never writes.

- `check_windows_safe_filenames`  no `<>:"|?*`, control chars, trailing dot/space or
                                  reserved device names (CON, NUL, COM1, ...) in a path.
- `check_untracked_exports`       `.along/dashboard.html` and `.along/DASHBOARD.md` stay
                                  out of git.
- `check_code_fence_language`     every opening Markdown fence names a language.
- `check_portable_links`          Markdown link targets use no `file://` and no backslashes.
- `check_stable_entry_point`      `README.md` and `docs/` never link into `.along/`.
- `check_issue_lifecycle`         closed issues live in `.along/ISSUES/done/`, open ones don't.
- `check_no_tracked_secrets`      no private keys or well-known token shapes in content.
- `check_rule_pack_integrity`     a `.along/rules/**/*.md` rule pack carries the managed header
                                  and its body matches the header hash. Not a catalogue rule
                                  handler: `gitgates.check_rule_packs` runs it for the
                                  `rule_pack_protection` gate, whose rule is the runtime predicate.

A line carrying `along: allow-<gate-id>` (e.g. `along: allow-no-tracked-secrets`) is
exempt, for fixtures that must contain a sample violation.
"""

from __future__ import annotations

if __name__ == "__main__":
    import os
    raise SystemExit(
        f"{os.path.basename(__file__)} is a library module, not a command.\n"
        "Run: along gates check --help   (or: python scripts/along_exec.py gates check --help)"
    )

import fnmatch
import posixpath
import re
from typing import Any, Callable, Dict, Iterable, List, Optional, Sequence, Tuple

Finding = Tuple[str, str]
Reader = Callable[[str], Optional[str]]

_RESERVED_NAMES = {"CON", "PRN", "AUX", "NUL",
                   *(f"COM{i}" for i in range(1, 10)), *(f"LPT{i}" for i in range(1, 10))}
_BAD_CHARS_RE = re.compile(r'[<>:"|?*\x00-\x1f]')
_EXPORTS = ("dashboard.html", "DASHBOARD.md")
_FENCE_RE = re.compile(r"^ {0,3}(`{3,}|~{3,})(.*)$")
_INLINE_CODE_RE = re.compile(r"(`+)(?:(?!\1).)+?\1")
_LINK_RE = re.compile(r"!?\[[^\]\n]*\]\(\s*<?([^)\s>]+)>?(?:\s+\"[^\"]*\")?\s*\)")
_SECRET_PATTERNS: Tuple[Tuple[str, re.Pattern], ...] = (
    ("private key", re.compile(r"-----BEGIN (?:RSA |EC |DSA |OPENSSH |PGP |ENCRYPTED )?PRIVATE KEY(?: BLOCK)?-----")),
    ("AWS access key id", re.compile(r"\b(?:AKIA|ASIA)[0-9A-Z]{16}\b")),
    ("GitHub token", re.compile(r"\b(?:gh[pousr]_[A-Za-z0-9]{36,}|github_pat_[A-Za-z0-9_]{60,})\b")),
    ("Anthropic API key", re.compile(r"\bsk-ant-[A-Za-z0-9_-]{32,}")),
    ("OpenAI API key", re.compile(r"\bsk-(?:proj-)?[A-Za-z0-9]{40,}\b")),
    ("Slack token", re.compile(r"\bxox[abprs]-[A-Za-z0-9-]{20,}")),
    ("Google API key", re.compile(r"\bAIza[0-9A-Za-z_-]{35}\b")),
)
_ISSUE_PATH_RE = re.compile(r"(?:^|/)\.along/ISSUES/(done/)?[^/]+\.md$")
_RULE_PACK_RE = re.compile(r"(?:^|/)\.along/rules/(?:[^/]+/)*[^/]+\.md$", re.IGNORECASE)
_STATUS_RE = re.compile(r"^status:\s*(\S+)", re.MULTILINE)
_CLOSED_STATUSES = {"done", "cancelled", "canceled", "superseded", "wontfix", "rejected"}
_ACTIVE_STATUSES = {"open", "in-progress", "blocked", "review", "todo"}
_BINARY_EXTS = {".png", ".jpg", ".jpeg", ".gif", ".ico", ".webp", ".pdf", ".zip", ".gz",
                ".whl", ".woff", ".woff2", ".ttf", ".pyc", ".exe", ".dll"}


def _rc_pragma(gate_id: str) -> str:
    return "along: allow-" + gate_id.replace("_", "-")


def _rc_excluded(path: str, options: Dict[str, Any]) -> bool:
    return any(fnmatch.fnmatch(path, pat) for pat in options.get("exclude_paths") or [])


def _rc_markdown(paths: Iterable[str], options: Dict[str, Any]) -> List[str]:
    return [p for p in paths if p.lower().endswith(".md") and not _rc_excluded(p, options)]


def _rc_prose_lines(text: str) -> Iterable[Tuple[int, str]]:
    """(line number, line) for Markdown lines outside fenced code blocks."""
    fence: Optional[str] = None
    for number, line in enumerate(text.splitlines(), 1):
        match = _FENCE_RE.match(line)
        if fence is None:
            if match:
                fence = match.group(1)
                continue
            yield number, line
        elif match and match.group(1)[0] == fence[0] and len(match.group(1)) >= len(fence) \
                and not match.group(2).strip():
            fence = None


def _rc_link_targets(line: str) -> List[str]:
    return [m.group(1) for m in _LINK_RE.finditer(_INLINE_CODE_RE.sub("", line))]


# ---------------------------------------------------------------------------
# Path-only checks
# ---------------------------------------------------------------------------

def check_windows_safe_filenames(paths: Sequence[str], read: Reader,
                                 options: Dict[str, Any]) -> List[Finding]:
    findings: List[Finding] = []
    for path in paths:
        if _rc_excluded(path, options):
            continue
        for part in path.split("/"):
            problem = None
            if _BAD_CHARS_RE.search(part):
                problem = f"component '{part}' contains a character Windows forbids (<>:\"|?* or control)"
            elif part.endswith((".", " ")):
                problem = f"component '{part}' ends with a dot or space"
            elif part.split(".")[0].upper() in _RESERVED_NAMES:
                problem = f"component '{part}' is a reserved Windows device name"
            if problem:
                findings.append((path, problem + "; use YYYY-MM-DD dates and ASCII names"))
                break
    return findings


def check_untracked_exports(paths: Sequence[str], read: Reader,
                            options: Dict[str, Any]) -> List[Finding]:
    return [(path, "local dashboard export must not be tracked; `git rm --cached` it "
                   "and keep it in .gitignore")
            for path in paths
            if posixpath.basename(path) in _EXPORTS
            and posixpath.basename(posixpath.dirname(path)) == ".along"]


# ---------------------------------------------------------------------------
# Content checks
# ---------------------------------------------------------------------------

def check_code_fence_language(paths: Sequence[str], read: Reader,
                              options: Dict[str, Any]) -> List[Finding]:
    findings: List[Finding] = []
    pragma = _rc_pragma("code_fence_language")
    for path in _rc_markdown(paths, options):
        text = read(path)
        if not text:
            continue
        fence: Optional[str] = None
        for number, line in enumerate(text.splitlines(), 1):
            match = _FENCE_RE.match(line)
            if not match:
                continue
            marker, info = match.group(1), match.group(2).strip()
            if fence is None:
                fence = marker
                if not info and pragma not in line:
                    findings.append((f"{path}:{number}",
                                     "code fence without a language; use ```text for plain output"))
            elif marker[0] == fence[0] and len(marker) >= len(fence) and not info:
                fence = None
    return findings


def check_portable_links(paths: Sequence[str], read: Reader,
                         options: Dict[str, Any]) -> List[Finding]:
    findings: List[Finding] = []
    pragma = _rc_pragma("portable_links")
    for path in _rc_markdown(paths, options):
        for number, line in _rc_prose_lines(read(path) or ""):
            if pragma in line:
                continue
            for target in _rc_link_targets(line):
                if target.lower().startswith("file:"):
                    findings.append((f"{path}:{number}", f"link '{target}' uses file://; use a relative path"))
                elif "\\" in target:
                    findings.append((f"{path}:{number}", f"link '{target}' uses backslashes; use '/'"))
    return findings


def check_stable_entry_point(paths: Sequence[str], read: Reader,
                             options: Dict[str, Any]) -> List[Finding]:
    """Links from public files into `.along/` rot when entities move; route through docs/."""
    scope = options.get("scope") or ["README.md", "docs/*"]
    findings: List[Finding] = []
    pragma = _rc_pragma("stable_entry_point")
    for path in _rc_markdown(paths, options):
        if not any(fnmatch.fnmatch(path, pat) for pat in scope):
            continue
        base = posixpath.dirname(path)
        for number, line in _rc_prose_lines(read(path) or ""):
            if pragma in line:
                continue
            for target in _rc_link_targets(line):
                if "://" in target or target.startswith(("#", "mailto:")):
                    continue
                resolved = posixpath.normpath(posixpath.join(base, target.split("#")[0]))
                if resolved == ".along" or resolved.startswith(".along/"):
                    findings.append((f"{path}:{number}",
                                     f"link '{target}' points into .along/; link docs/INDEX.md "
                                     "or a docs/topic--*.md article instead"))
    return findings


def check_issue_lifecycle(paths: Sequence[str], read: Reader,
                          options: Dict[str, Any]) -> List[Finding]:
    """Closed issues live in `.along/ISSUES/done/`, active ones directly in `.along/ISSUES/`."""
    findings: List[Finding] = []
    for path in paths:
        match = _ISSUE_PATH_RE.search(path)
        if not match or _rc_excluded(path, options):
            continue
        status_match = _STATUS_RE.search((read(path) or "").split("\n---", 1)[0])
        status = status_match.group(1).strip("'\"").lower() if status_match else ""
        in_done = bool(match.group(1))
        if not in_done and status in _CLOSED_STATUSES:
            findings.append((path, f"status '{status}' but the file is not in ISSUES/done/; "
                                   "run `along issue done <slug>`"))
        elif in_done and status in _ACTIVE_STATUSES:
            findings.append((path, f"status '{status}' but the file is in ISSUES/done/; "
                                   "move it back or close it"))
    return findings


def check_rule_pack_integrity(paths: Sequence[str], read: Reader,
                              options: Dict[str, Any]) -> List[Finding]:
    """Managed rule packs are pristine copies of the Along templates [gate: rule-pack-protection]."""
    from .rules import compute_rule_hash, parse_rule_header

    findings: List[Finding] = []
    for path in paths:
        if not _RULE_PACK_RE.search(path) or _rc_excluded(path, options):
            continue
        text = read(path)
        if text is None:
            continue
        _, header_hash, body = parse_rule_header(text)
        if header_hash is None:
            findings.append((path, "rule pack has no managed header; run `along rules attach` "
                                   "(or `along rules restore`)"))
        elif compute_rule_hash(body) != header_hash.lower():
            findings.append((path, "managed rule pack was edited; move project guidelines to "
                                   "docs/topic--*.md or AGENTS.md 'Project specifics' and run "
                                   "`along rules restore`"))
    return findings


def check_no_tracked_secrets(paths: Sequence[str], read: Reader,
                             options: Dict[str, Any]) -> List[Finding]:
    findings: List[Finding] = []
    pragma = _rc_pragma("no_tracked_secrets")
    for path in paths:
        if _rc_excluded(path, options) or posixpath.splitext(path)[1].lower() in _BINARY_EXTS:
            continue
        text = read(path)
        if not text or "\x00" in text:
            continue
        for number, line in enumerate(text.splitlines(), 1):
            if pragma in line:
                continue
            for label, pattern in _SECRET_PATTERNS:
                if pattern.search(line):
                    findings.append((f"{path}:{number}",
                                     f"looks like a {label}; remove it and rotate the credential"))
                    break
    return findings
