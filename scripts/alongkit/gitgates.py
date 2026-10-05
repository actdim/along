"""
alongkit.gitgates - runtime-agnostic gate enforcement through git hooks and CI.

Runtime gates (PreToolUse/Stop) only exist inside agent runtimes that load Along's
hooks. Humans, CI bots, Cowork, Cursor and every other runtime bypass them. This module
runs the commit-time subset of the catalogue - every gate declaring `git` or `ci` in its
`enforcement` list (`default_gates.yaml`) - against what git is about to record:

- `pre-commit`   staged diff: typography, conflict markers, anti-stub on added lines;
                 projection freshness of staged `.along/` boards.
- `commit-msg`   message file: issue binding, AI co-author trailers.
- `--ci`         a commit range: both of the above per commit / per range diff, plus
                 projection freshness of the checked-out tree and link integrity.
- both           entity reference integrity (`validate_entities` on the staged / checked-out
                 `.along/` against HEAD / the range base; only newly introduced problems
                 block) whenever the change touches an entity file;
                 repository-state gates (`alongkit.repochecks`: filenames, exports, code
                 fences, portable links, stable entry point, secrets) over the staged
                 files (pre-commit) or every tracked file (CI);
                 rule pack integrity (`.along/rules/**/*.md` matches its managed header hash).

Patterns come from the gate catalogue so runtime, git and CI can never disagree.
Checks are read-only: projections are recompiled in a throwaway snapshot, never in the
working tree. Git hooks are installed only by `along hooks install --git`, never by
default (ADR-2026-09-29--opt-in-git-hooks-supersede-zero-git-hooks).
"""

from __future__ import annotations

if __name__ == "__main__":
    import os
    raise SystemExit(
        f"{os.path.basename(__file__)} is a library module, not a command.\n"
        "Run: along gates check --help   (or: python scripts/along_exec.py gates check --help)"
    )

import os
import re
import shutil
import stat
import sys
import tempfile
from dataclasses import dataclass
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

from . import proc

HOOK_NAMES: Tuple[str, ...] = ("pre-commit", "commit-msg")
HOOK_MARKER = "# along-git-hook:"
CHAINED_SUFFIX = ".pre-along"

#: Commit subjects that never carry an issue binding.
EXEMPT_SUBJECT_RE = re.compile(r"^(release: |Merge |Revert \"|fixup! |squash! |amend! )")

_HUNK_RE = re.compile(r"^@@ -\d+(?:,\d+)? \+(\d+)(?:,\d+)? @@")


@dataclass(frozen=True)
class Violation:
    gate: str        # canonical catalogue id, e.g. "typography"
    location: str    # "path:line", "commit <sha>", "message"
    message: str

    def render(self) -> str:
        return f"[gate: {self.gate.replace('_', '-')}] {self.location}: {self.message}"


# ---------------------------------------------------------------------------
# Catalogue access
# ---------------------------------------------------------------------------

def _definitions(layer: str):
    from .hooks.declarative import DEFAULT_GATES_FILE, load_gate_definitions
    return {d.id: d for d in load_gate_definitions(DEFAULT_GATES_FILE) if layer in d.enforcement}


def _rule_pattern(definitions, gate_id: str) -> Optional[re.Pattern]:
    defn = definitions.get(gate_id)
    if not defn:
        return None
    return next((r.pattern for r in defn.rules if r.pattern is not None), None)


def enforcement_matrix() -> Dict[str, List[str]]:
    """`{gate id: [layers]}` for every catalogue gate (for `along hook verify`)."""
    from .hooks.declarative import DEFAULT_GATES_FILE, load_gate_definitions
    return {d.id: list(d.enforcement) for d in load_gate_definitions(DEFAULT_GATES_FILE)}


# ---------------------------------------------------------------------------
# Diff parsing
# ---------------------------------------------------------------------------

def added_lines(diff_text: str) -> Dict[str, List[Tuple[int, str]]]:
    """`{path: [(new line number, text)]}` for every line a unified diff adds."""
    result: Dict[str, List[Tuple[int, str]]] = {}
    current: Optional[str] = None
    lineno = 0
    for line in diff_text.splitlines():
        if line.startswith("+++ "):
            target = line[4:].strip()
            current = None if target == "/dev/null" else (target[2:] if target.startswith("b/") else target)
            continue
        if line.startswith("--- ") or line.startswith("diff --git"):
            continue
        hunk = _HUNK_RE.match(line)
        if hunk:
            lineno = int(hunk.group(1))
            continue
        if current is None:
            continue
        if line.startswith("+"):
            result.setdefault(current, []).append((lineno, line[1:]))
            lineno += 1
        elif line.startswith(" "):
            lineno += 1
    return result


def _typography_governed(path: str, ignore_patterns: Sequence[str]) -> bool:
    from . import sanitizer
    norm = path.replace("\\", "/")
    if any(seg in sanitizer.LOCALIZED_DIRS for seg in norm.split("/")):
        return False
    if not norm.lower().endswith(sanitizer.DEFAULT_SUFFIXES):
        return False
    return not sanitizer.matches_exclude(norm, ignore_patterns)


def check_diff(diff_text: str, repo_root: str, layer: str = "git") -> List[Violation]:
    """Typography, conflict markers and anti-stub on the lines a diff ADDS.

    Only added lines count, so pre-existing debt elsewhere in a file never blocks a commit.
    """
    from . import sanitizer, typography
    from .hooks.predicates import find_added_conflict_markers

    definitions = _definitions(layer)
    violations: List[Violation] = []

    if "commit_no_conflict_markers" in definitions:
        for hit in find_added_conflict_markers(diff_text):
            path, _, marker = hit.partition(": ")
            violations.append(Violation("commit_no_conflict_markers", path,
                                        f"unresolved conflict marker '{marker}'"))

    added = added_lines(diff_text)
    stub_re = _rule_pattern(definitions, "anti_stub_injection")
    ignore = sanitizer.load_ignore_patterns(repo_root) if repo_root else []
    for path, lines in sorted(added.items()):
        for lineno, text in lines:
            if stub_re is not None and stub_re.search(text):
                violations.append(Violation("anti_stub_injection", f"{path}:{lineno}",
                                            "truncation placeholder / code skeleton stub"))
        if "typography" in definitions and _typography_governed(path, ignore):
            for lineno, text in lines:
                hits = typography.findings(text)
                if hits:
                    names = sorted({typography.name_of(ch) for _, _, ch in hits})
                    violations.append(Violation("typography", f"{path}:{lineno}",
                                                "forbidden non-ASCII typography: " + ", ".join(names)))
    return violations


# ---------------------------------------------------------------------------
# Commit messages
# ---------------------------------------------------------------------------

def _message_body(text: str) -> str:
    """Drop git's comment lines (the commit template) from a message file."""
    return "\n".join(line for line in text.splitlines() if not line.startswith("#")).strip()


def check_message(text: str, repo_root: Optional[str], layer: str = "git",
                  location: str = "message") -> List[Violation]:
    from . import attribution

    definitions = _definitions(layer)
    body = _message_body(text)
    violations: List[Violation] = []
    if not body:
        return violations
    subject = body.splitlines()[0]

    binding = _rule_pattern(definitions, "commit_issue_binding")
    if binding is not None and not EXEMPT_SUBJECT_RE.match(subject) and not binding.search(body):
        violations.append(Violation(
            "commit_issue_binding", location,
            "message does not bind an issue: add '(refs #<slug>)' or '[<type>--<slug>]' (use /along-commit)"))

    if "commit_no_ai_coauthor" in definitions and not attribution.allow_ai_coauthor(repo_root):
        trailer = attribution.find_ai_coauthor(body)
        if trailer:
            violations.append(Violation("commit_no_ai_coauthor", location,
                                        f"AI co-author trailer '{trailer[:80]}'"))
    return violations


# ---------------------------------------------------------------------------
# Projection freshness
# ---------------------------------------------------------------------------

_SNAPSHOT_IGNORE = shutil.ignore_patterns(".session", "worktrees", ".migration-backup",
                                          "diagnostics", "*.lock")


def along_roots(paths: Iterable[str]) -> List[str]:
    """Context roots (relative, "" for the repo root) of every `.along/` in `paths`."""
    roots = set()
    for path in paths:
        parts = path.replace("\\", "/").split("/")
        if ".along" in parts:
            roots.add("/".join(parts[:parts.index(".along")]))
    return sorted(roots)


def _snapshot_from_index(repo_root: str, roots: Sequence[str], dest: str) -> None:
    specs = [f"{r}/.along" if r else ".along" for r in roots]
    listing = proc.run_capture(["git", "ls-files", "-z", "--", *specs], cwd=repo_root,
                               check=False, trip_on_anomaly=False)
    files = [f for f in listing.stdout.split("\0") if f]
    if not files:
        return
    prefix = dest.replace("\\", "/").rstrip("/") + "/"
    proc.run_capture(["git", "checkout-index", "-f", f"--prefix={prefix}", "--", *files],
                     cwd=repo_root, check=False, trip_on_anomaly=False)


def _snapshot_from_tree(repo_root: str, roots: Sequence[str], dest: str) -> None:
    for root in roots:
        src = os.path.join(repo_root, root, ".along")
        if os.path.isdir(src):
            shutil.copytree(src, os.path.join(dest, root, ".along"), ignore=_SNAPSHOT_IGNORE)


def _norm(text: str) -> str:
    return text.replace("\r\n", "\n").strip()


def _read_or_empty(path: str) -> Optional[str]:
    from . import textio
    return textio.read_text(path, strict=False) if os.path.isfile(path) else None


def stale_projections(snapshot_root: str, roots: Sequence[str]) -> List[str]:
    """Recompile boards inside `snapshot_root` and list those that differed (relative)."""
    from . import entities

    stale: List[str] = []
    for root in roots:
        ctx = os.path.join(snapshot_root, root)
        sdir = os.path.join(ctx, ".along")
        if not os.path.isdir(sdir):
            continue
        rel = (root + "/" if root else "") + ".along/"
        targets = ["ISSUES.md"] if os.path.isdir(os.path.join(sdir, "ISSUES")) else []
        if os.path.isdir(os.path.join(sdir, "DECISIONS")):
            targets += ["DECISIONS.md", "CONSTRAINTS.md"]
        before = {name: _read_or_empty(os.path.join(sdir, name)) for name in targets}
        if "ISSUES.md" in targets:
            entities.sync_issues_board(ctx)
        if "DECISIONS.md" in targets:
            entities.compile_decisions_board(ctx)
            entities.sync_constraints(ctx)
        for name in targets:
            after = _read_or_empty(os.path.join(sdir, name))
            if before[name] is not None and _norm(before[name]) != _norm(after or ""):
                stale.append(rel + name)
    return stale


def check_projections(repo_root: str, roots: Sequence[str], source: str) -> List[Violation]:
    """`source` is "index" (pre-commit) or "tree" (CI checkout)."""
    if not roots or "projection_protection" not in _definitions("git" if source == "index" else "ci"):
        return []
    tmp = tempfile.mkdtemp(prefix="along-gates-")
    try:
        if source == "index":
            _snapshot_from_index(repo_root, roots, tmp)
        else:
            _snapshot_from_tree(repo_root, roots, tmp)
        stale = stale_projections(tmp, roots)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    return [Violation("projection_protection", path,
                      "projection does not match a fresh compile of its entity files; run "
                      "`along issue sync` / `along decision sync` (or `along git sync`) and stage it")
            for path in stale]


# ---------------------------------------------------------------------------
# Entry points
# ---------------------------------------------------------------------------

def _git_out(repo_root: str, *args: str) -> str:
    result = proc.run_capture(["git", *args], cwd=repo_root, check=False, trip_on_anomaly=False)
    return result.stdout if result.ok else ""


REPO_CHECK_PREFIX = "alongkit.repochecks."


def _tree_reader(repo_root: str):
    def read(path: str) -> Optional[str]:
        try:
            with open(os.path.join(repo_root, path), "r", encoding="utf-8", errors="replace") as fh:
                return fh.read()
        except OSError:
            return None
    return read


def _index_reader(repo_root: str):
    def read(path: str) -> Optional[str]:
        result = proc.run_capture(["git", "show", f":{path}"], cwd=repo_root, check=False,
                                  trip_on_anomaly=False)
        return result.stdout if result.ok else None
    return read


def check_repo_state(repo_root: str, paths: Sequence[str], layer: str, read) -> List[Violation]:
    """Run every `alongkit.repochecks` gate enforced at `layer` over `paths`."""
    from . import repochecks
    violations: List[Violation] = []
    paths = [p.replace("\\", "/") for p in paths if p]
    for gate_id, defn in _definitions(layer).items():
        for rule in defn.rules:
            handler = rule.handler_name or ""
            if not handler.startswith(REPO_CHECK_PREFIX):
                continue
            check = getattr(repochecks, handler[len(REPO_CHECK_PREFIX):])
            for location, message in check(paths, read, defn.options):
                violations.append(Violation(gate_id, location, message))
    return violations


RULE_PACK_GATE = "rule_pack_protection"


def check_rule_packs(paths: Sequence[str], layer: str, read) -> List[Violation]:
    """[gate: rule-pack-protection] at git / ci: rule packs in `paths` are pristine.

    The gate's catalogue rule is the runtime predicate, so `check_repo_state` does not pick
    it up; the commit-time check is `repochecks.check_rule_pack_integrity`.
    """
    from . import repochecks
    defn = _definitions(layer).get(RULE_PACK_GATE)
    if defn is None:
        return []
    paths = [p.replace("\\", "/") for p in paths if p]
    return [Violation(RULE_PACK_GATE, location, message)
            for location, message in repochecks.check_rule_pack_integrity(paths, read, defn.options)]


ENTITY_GATE = "entity_reference_integrity"
ENTITY_SUBDIRS: Tuple[str, ...] = ("ISSUES", "MILESTONES", "RISKS", "SPIKES", "CHECKLISTS",
                                   "DECISIONS", "SESSIONS")


def touches_entities(paths: Iterable[str]) -> bool:
    """True when any path is an entity file under some `.along/<entity dir>/`."""
    for path in paths:
        parts = path.replace("\\", "/").split("/")
        if ".along" in parts:
            idx = parts.index(".along")
            if len(parts) > idx + 2 and parts[idx + 1] in ENTITY_SUBDIRS:
                return True
    return False


def _snapshot_from_commit(repo_root: str, commit: str, roots: Sequence[str], dest: str,
                          specs: Optional[Sequence[str]] = None) -> None:
    import tarfile
    specs = list(specs) if specs is not None else [f"{r}/.along" if r else ".along" for r in roots]
    if not specs:
        return
    archive = os.path.join(dest, ".along-snapshot.tar")
    result = proc.run_capture(["git", "archive", "--format=tar", "-o", archive, commit, "--", *specs],
                              cwd=repo_root, check=False, trip_on_anomaly=False)
    if not result.ok or not os.path.isfile(archive):
        return
    with tarfile.open(archive) as tar:
        members = [m for m in tar.getmembers() if m.isfile() or m.isdir()]
        safe = {"filter": "data"} if hasattr(tarfile, "data_filter") else {}
        tar.extractall(dest, members=members, **safe)
    os.remove(archive)


def entity_problems(snapshot_root: str, roots: Sequence[str]) -> set:
    """{(location, message)} from `validate_entities` over every context in a snapshot."""
    from . import entities
    problems = set()
    for root in roots:
        ctx = os.path.join(snapshot_root, root)
        if not os.path.isdir(os.path.join(ctx, ".along")):
            continue
        prefix = root + "/" if root else ""
        for rel, message in entities.validate_entities(ctx)["errors"]:
            if entities.is_integrity_error(message):
                problems.add((prefix + rel.replace("\\", "/"), message))
    return problems


def _entity_snapshot(repo_root: str, roots: Sequence[str], source: str) -> set:
    tmp = tempfile.mkdtemp(prefix="along-entities-")
    try:
        # A `.git` marker bounds the ancestor-context walk to the snapshot.
        os.makedirs(os.path.join(tmp, ".git"), exist_ok=True)
        if source == "index":
            _snapshot_from_index(repo_root, roots, tmp)
        elif source == "tree":
            _snapshot_from_tree(repo_root, roots, tmp)
        elif source:
            _snapshot_from_commit(repo_root, source, roots, tmp)
        return entity_problems(tmp, roots)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def _entity_dirs_at(repo_root: str, commit: str) -> Optional[List[str]]:
    """Every `<ctx>/.along/<entity dir>` tracked at `commit` (None when git cannot say)."""
    result = proc.run_capture(["git", "ls-tree", "-r", "--name-only", "-z", commit], cwd=repo_root,
                              check=False, trip_on_anomaly=False)
    if not result.ok:
        return None
    dirs = set()
    for path in result.stdout.split("\0"):
        parts = path.split("/")
        if ".along" in parts:
            idx = parts.index(".along")
            if len(parts) > idx + 2 and parts[idx + 1] in ENTITY_SUBDIRS:
                dirs.add("/".join(parts[:idx + 2]))
    return sorted(dirs)


def tracked_diagnostics(repo_root: str) -> List[str]:
    """Tracked files under any `.along/diagnostics/` below `repo_root`, relative POSIX paths.

    Empty outside git. Per-machine runtime state that only lingers in the index because it
    was committed before the directory ignored itself. See [bug--diagnostics-files-stay-tracked].
    """
    from .repochecks import is_diagnostics_path
    listing = _git_out(repo_root, "ls-files", "-z")
    return sorted(p for p in listing.split("\0") if p and is_diagnostics_path(p))


def untrack_diagnostics(repo_root: str, dry_run: bool = False) -> List[str]:
    """Remove tracked diagnostics from the index (`git rm --cached`); files stay on disk.

    Returns the paths untracked (or that would be, with `dry_run`). Idempotent: a second
    run finds nothing. The removal is staged, so the next commit records it.
    """
    paths = tracked_diagnostics(repo_root)
    if paths and not dry_run:
        result = proc.run_capture(["git", "rm", "--cached", "-q", "--", *paths], cwd=repo_root,
                                  check=False, trip_on_anomaly=False)
        if not result.ok:
            return []
    return paths


def baseline_entity_problems(repo_root: str, base: str = "HEAD") -> Optional[set]:
    """Integrity problems of the `repo_root` context at commit `base`, as {(location, message)}.

    Locations are POSIX paths relative to `repo_root`, the shape `gates.entity_integrity_errors`
    prints. The snapshot holds the entity dirs of every `.along/` in the commit, so ancestor
    and nested contexts resolve as they do on disk. None when `base` does not resolve (no
    commit yet) or git is unavailable. [bug--entity-gate-blocks-preexisting-problems]
    """
    from . import entities
    top = _git_out(repo_root, "rev-parse", "--show-toplevel").strip()
    if not top or not _git_out(repo_root, "rev-parse", "--verify", "-q", base).strip():
        return None
    prefix = os.path.relpath(os.path.abspath(repo_root), os.path.abspath(top)).replace("\\", "/")
    prefix = "" if prefix == "." else prefix
    dirs = _entity_dirs_at(top, base)
    if dirs is None:
        return None
    tmp = tempfile.mkdtemp(prefix="along-entities-base-")
    try:
        os.makedirs(os.path.join(tmp, ".git"), exist_ok=True)
        _snapshot_from_commit(top, base, [], tmp, specs=dirs)
        ctx = os.path.join(tmp, prefix) if prefix else tmp
        if not os.path.isdir(os.path.join(ctx, ".along")):
            return set()
        return {(rel.replace("\\", "/"), message)
                for rel, message in entities.validate_entities(ctx)["errors"]
                if entities.is_integrity_error(message)}
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def check_entity_references(repo_root: str, changed: Sequence[str], layer: str, source: str,
                            base: Optional[str]) -> List[Violation]:
    """[gate: entity-reference-integrity] problems the change introduces.

    Validates the entity graph of `source` ("index" or "tree") and of the `base` commit;
    only problems absent at `base` block. Pre-existing ones are printed as a notice so an
    old defect elsewhere never blocks an unrelated commit. Runs only when `changed`
    touches an entity file (deleting one counts).
    """
    if not touches_entities(changed) or ENTITY_GATE not in _definitions(layer):
        return []
    listing = (_git_out(repo_root, "ls-files", "-z").split("\0") if source == "index"
               else [p for p in changed if p])
    roots = sorted(set(along_roots(listing)) | set(along_roots(changed))
                   | ({""} if os.path.isdir(os.path.join(repo_root, ".along")) else set()))
    after = _entity_snapshot(repo_root, roots, source)
    before = _entity_snapshot(repo_root, roots, base) if base else set()
    old = sorted(after & before)
    if old:
        print(f"[Along gates] entity-reference-integrity: {len(old)} pre-existing problem(s), "
              "not blocking:", file=sys.stderr)
        for location, message in old[:10]:
            print(f"  {location}: {message}", file=sys.stderr)
    return [Violation(ENTITY_GATE, location,
                      message + " (fix it, or use `along issue rename` / `along issue supersede` "
                                "instead of deleting a referenced entity)")
            for location, message in sorted(after - before)]


def _range_base(repo_root: str, commit_range: Optional[str]) -> Optional[str]:
    if not commit_range:
        return None
    if "..." in commit_range:
        left, right = commit_range.split("...", 1)
        return _git_out(repo_root, "merge-base", left, right or "HEAD").strip() or None
    if ".." in commit_range:
        return commit_range.split("..", 1)[0] or None
    return None


def check_pre_commit(repo_root: str) -> List[Violation]:
    diff = _git_out(repo_root, "diff", "--cached", "-U0", "--no-color", "--no-ext-diff")
    staged = _git_out(repo_root, "diff", "--cached", "--name-only").splitlines()
    added = _git_out(repo_root, "diff", "--cached", "--name-only", "-z", "--diff-filter=ACMR").split("\0")
    head = "HEAD" if _git_out(repo_root, "rev-parse", "--verify", "-q", "HEAD") else None
    return (check_diff(diff, repo_root, "git")
            + check_projections(repo_root, along_roots(staged), "index")
            + check_repo_state(repo_root, added, "git", _index_reader(repo_root))
            + check_rule_packs(added, "git", _index_reader(repo_root))
            + check_entity_references(repo_root, staged, "git", "index", head))


def check_commit_msg(repo_root: str, message_file: str) -> List[Violation]:
    from . import textio
    if not os.path.isfile(message_file):
        return []
    return check_message(textio.read_text(message_file, strict=False), repo_root, "git")


def default_ci_range() -> Optional[str]:
    """Commit range from the CI environment: GitHub PR base, else push `before`."""
    base = os.environ.get("GITHUB_BASE_REF")
    if base:
        return f"origin/{base}...HEAD"
    before = os.environ.get("ALONG_CI_BEFORE") or ""
    if before and set(before) != {"0"}:
        return f"{before}..HEAD"
    return None


def check_ci(repo_root: str, commit_range: Optional[str] = None, links: bool = True,
             kb_script: Optional[str] = None) -> List[Violation]:
    violations: List[Violation] = []
    commit_range = commit_range or default_ci_range()
    if not commit_range and _git_out(repo_root, "rev-parse", "--verify", "-q", "HEAD^"):
        commit_range = "HEAD^..HEAD"

    changed: List[str] = []
    if commit_range:
        for sha in _git_out(repo_root, "rev-list", "--no-merges", commit_range).split():
            message = _git_out(repo_root, "log", "-1", "--format=%B", sha)
            violations += check_message(message, repo_root, "ci", location=f"commit {sha[:10]}")
        diff = _git_out(repo_root, "diff", "-U0", "--no-color", "--no-ext-diff", commit_range)
        violations += check_diff(diff, repo_root, "ci")
        changed = _git_out(repo_root, "diff", "--name-only", commit_range).splitlines()

    roots = sorted(set(along_roots(changed)) | ({""} if os.path.isdir(os.path.join(repo_root, ".along")) else set()))
    violations += check_projections(repo_root, roots, "tree")
    violations += check_entity_references(repo_root, changed, "ci", "tree",
                                          _range_base(repo_root, commit_range))
    tracked = _git_out(repo_root, "ls-files", "-z").split("\0")
    violations += check_repo_state(repo_root, tracked, "ci", _tree_reader(repo_root))
    violations += check_rule_packs(tracked, "ci", _tree_reader(repo_root))

    if links and kb_script and os.path.isdir(os.path.join(repo_root, "docs")):
        result = proc.run_capture([sys.executable, kb_script, "--check"], cwd=repo_root,
                                  check=False, trip_on_anomaly=False)
        if not result.ok:
            tail = (result.stdout + result.stderr).strip().splitlines()[-5:]
            violations.append(Violation("link_integrity", "docs/",
                                        "along kb-sync --check failed: " + " | ".join(tail)))
    return violations


def format_report(violations: Sequence[Violation], context: str) -> str:
    if not violations:
        return f"[Along gates] {context}: all checks passed."
    lines = [f"[Along gates] {context}: {len(violations)} violation(s)"]
    lines += ["  " + v.render() for v in violations]
    lines.append("Fix the violations, or bypass once with `git commit --no-verify` "
                 "(CI will still enforce them).")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Hook installation (`along hooks install --git`)
# ---------------------------------------------------------------------------

def hooks_dir(repo_root: str) -> Tuple[Optional[str], bool]:
    """(hooks directory, managed_by_core_hooksPath)."""
    custom = _git_out(repo_root, "config", "--get", "core.hooksPath").strip()
    path = _git_out(repo_root, "rev-parse", "--git-path", "hooks").strip()
    if not path:
        return None, bool(custom)
    if not os.path.isabs(path):
        path = os.path.join(repo_root, path)
    return os.path.normpath(path), bool(custom)


def hook_script(name: str, python: Optional[str] = None, engine: Optional[str] = None) -> str:
    """POSIX-sh shim git runs on every platform (Git for Windows ships sh). All logic is
    in Python; the shim only chains a pre-existing hook and execs the checker."""
    from . import install
    python = (python or sys.executable).replace("\\", "/")
    engine = (engine or install.engine_script("along_exec.py")).replace("\\", "/")
    return (
        "#!/bin/sh\n"
        f"{HOOK_MARKER} {name} (managed by `along hooks install --git`; do not edit)\n"
        f'if [ -x "$0{CHAINED_SUFFIX}" ]; then "$0{CHAINED_SUFFIX}" "$@" || exit $?; fi\n'
        f'exec "{python}" "{engine}" gates check --hook {name} "$@"\n'
    )


def _is_ours(path: str) -> bool:
    from . import textio
    return os.path.isfile(path) and HOOK_MARKER in textio.read_text(path, strict=False)[:400]


def install_hooks(repo_root: str, uninstall: bool = False, dry_run: bool = False) -> Dict[str, str]:
    """Install (or remove) the Along git hooks. Returns `{hook: status}`.

    A pre-existing foreign hook is moved to `<hook>.pre-along` and chained first, and
    restored on uninstall. When `core.hooksPath` points at a hook manager's directory
    (husky, lefthook), nothing is written: the report tells the user which command to
    add to their manager instead.
    """
    from . import textio

    directory, custom = hooks_dir(repo_root)
    if directory is None:
        return {name: "not-a-git-repo" for name in HOOK_NAMES}
    if custom and not uninstall:
        return {name: "skipped-core-hooksPath" for name in HOOK_NAMES}

    report: Dict[str, str] = {}
    for name in HOOK_NAMES:
        path = os.path.join(directory, name)
        chained = path + CHAINED_SUFFIX
        if uninstall:
            if not _is_ours(path):
                report[name] = "absent"
                continue
            report[name] = "removed"
            if not dry_run:
                os.remove(path)
                if os.path.isfile(chained):
                    os.replace(chained, path)
                    report[name] = "removed-restored-previous"
            continue

        wanted = hook_script(name)
        if _is_ours(path):
            if textio.read_text(path, strict=False) == wanted:
                report[name] = "present"
                continue
            report[name] = "updated"
        elif os.path.isfile(path):
            report[name] = "installed-chained-previous"
            if not dry_run:
                os.replace(path, chained)
        else:
            report[name] = "installed"
        if not dry_run:
            os.makedirs(directory, exist_ok=True)
            textio.write_text(path, wanted, newline="\n")
            mode = os.stat(path).st_mode
            os.chmod(path, mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    return report


def hooks_status(repo_root: str) -> Dict[str, bool]:
    directory, _ = hooks_dir(repo_root)
    if directory is None:
        return {name: False for name in HOOK_NAMES}
    return {name: _is_ours(os.path.join(directory, name)) for name in HOOK_NAMES}


__all__: Sequence[str] = (
    "Violation", "added_lines", "check_diff", "check_message", "check_projections",
    "check_pre_commit", "check_commit_msg", "check_ci", "default_ci_range",
    "enforcement_matrix", "format_report", "hook_script", "install_hooks", "hooks_status",
    "hooks_dir", "along_roots", "stale_projections", "check_entity_references",
    "entity_problems", "touches_entities",
)
