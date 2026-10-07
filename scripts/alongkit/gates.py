#!/usr/bin/env python3
"""
alongkit.gates - Pre-commit and pre-release quality gates.

`along_commit.py` and `along_version_bump.py` each carried their own copy of
`run_precommit_tests` and `sanitize_typography`, differing only in the label they print.
The consequence is not hypothetical: the release engine's copy discarded the sanitizer's
output entirely, so a release could not report what it had rewritten, while the commit
engine detected changes by string-matching the tool's own stdout.

Whether the sanitizer may rewrite unattended is settled by
ADR-2026-09-01--typography-rule-scope and `[bug--typography-sanitizer-destroys-non-utf8-files]`:
it may not. `typography_gate` runs in check mode, reports what it found, and returns
False; the caller aborts and the human decides. Rewriting requires an explicit
`allow_fix`, which the engines expose as `--fix-typography`.

Gates run BEFORE the mutations they guard. The release engine used to bump the version,
rewrite the tree, and flip milestone files first, then run the tests, then print
"Release aborted" over a half-released tree with no way back. A gate that reports after
the fact is not a gate. See
`[bug--release-engine-mutates-before-tests-and-reinstalls-globals]` and
`alongkit.transaction`, which supplies the rollback for the mutations themselves.
"""


from __future__ import annotations
if __name__ == "__main__":
    import os
    raise SystemExit(
        f"{os.path.basename(__file__)} is a library module, not a command.\n"
        "Run: python .along/scripts/test.py"
    )


import ast
from dataclasses import dataclass
import json
import os
import sys
from typing import List, Optional, Tuple

from . import proc, repo, sanitizer, session, testruns


def detect_test_command(repo_root: str) -> Optional[List[str]]:
    """The command that runs this repository's tests, or None when there are none.

    Order of preference: the repository's own `.along/scripts/test.py` lifecycle hook, a
    `tests/` directory, then an npm `test` script.
    """
    hook = os.path.join(repo.state_dir(repo_root), "scripts", "test.py")
    if os.path.exists(hook):
        return [sys.executable, hook]

    if os.path.isdir(os.path.join(repo_root, "tests")):
        return [sys.executable, "-m", "unittest", "discover", "-s", "tests", "-p", "test_*.py"]

    manifest = os.path.join(repo_root, "package.json")
    if os.path.exists(manifest):
        try:
            with open(manifest, "r", encoding="utf-8") as handle:
                package = json.load(handle)
        except (OSError, ValueError) as exc:
            # Previously `json` was not even imported here and the NameError was swallowed
            # by a bare `except Exception: pass`, so a repository with a package.json
            # silently ran no tests at all.
            print(f"[Warning] cannot read package.json: {exc}", file=sys.stderr)
            return None
        if isinstance(package.get("scripts"), dict) and "test" in package["scripts"]:
            return ["npm", "test", "--", "--silent"]
    return None


UNCONFIGURED_MARKER = "# Status: unconfigured"


def is_unconfigured_hook(path: str) -> bool:
    """True when `path` is a lifecycle hook still rendered from the unconfigured template."""
    if not path.endswith(".py") or not os.path.isfile(path):
        return False
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as handle:
            return UNCONFIGURED_MARKER in handle.read(500)
    except OSError:
        return False


def run_repository_tests(repo_root: str, label: str = "Quality Gate") -> bool:
    """Run the repository's tests, printing the outcome. True when they passed or none exist."""
    cmd = detect_test_command(repo_root)
    if not cmd:
        return True
    if is_unconfigured_hook(cmd[-1]):
        # [bug--unconfigured-test-hook-reports-pass]: the placeholder exits 0 without
        # running anything, which must not read as a pass.
        print(f"[Warning] {label}: tests are not configured (.along/scripts/test.py is the "
              "unconfigured placeholder); nothing was verified.", file=sys.stderr)
        return True

    # [feat--parallel-session-closeout] REQ-8: one run per completion; a green run on the
    # same tree (Along state and KB projections aside) is reused.
    tree = testruns.tree_hash(repo_root)
    reused = testruns.green_run_for(repo_root, tree)
    if reused:
        print(f"-> [{label}] Tests passed on this tree at {reused.get('ts')} ({reused.get('source')}); "
              "not running them again.")
        return True

    print(f"-> [{label}] Running automated tests: {' '.join(cmd)}")
    # No anomaly classification: a failing suite prints fixture signatures such as
    # "bad signature" [bug--breaker-trips-on-test-output].
    res = proc.run_capture(cmd, cwd=repo_root, trip_on_anomaly=False)
    testruns.record_run(repo_root, res.ok, tree, label)
    session.trace_test_run(repo_root, res.ok, label)
    if res.ok:
        print(f"-> [{label}] All tests passed successfully.")
        return True

    print(f"[Error] {label}: automated tests failed.\n", file=sys.stderr)
    if res.stdout:
        print(res.stdout, file=sys.stderr)
    if res.stderr:
        print(res.stderr, file=sys.stderr)
    return False


def link_integrity_gate(repo_root: str, label: str = "Quality Gate", strict: bool = True) -> bool:
    """Verify that every relative Markdown link resolves. True when the caller may proceed.

    Delegates to the Knowledge Base engine in `--check` mode (`--strict` by default), which walks the
    whole tree, resolves links against disk, and exits non-zero on a broken one. `--check`
    is the engine's read-only mode: nothing is rewritten, no index is recompiled, so this
    is safe to run before a release has mutated anything.

    A repository without the engine (a consumer project with only the skills installed)
    passes: there is nothing to check with, and a missing optional tool must not block a
    release.
    """
    engine = repo.resolve_tool_script("along_kb_sync.py", repo_root)
    if not engine:
        return True

    print(f"-> [{label}] Verifying Markdown link integrity...")
    cmd = [engine, repo_root, "--check"]
    if strict:
        cmd.append("--strict")
    res = proc.run_python(cmd, cwd=repo_root)
    if res.ok:
        print(f"-> [{label}] Link integrity verified.")
        return True

    print(f"[Error] {label}: link integrity check failed.\n", file=sys.stderr)
    for stream in (res.stdout, res.stderr):
        if stream:
            print(stream, file=sys.stderr)
    return False


def run_sanitizer(repo_root: str, verbose: bool = True,
                  mode: str = sanitizer.Mode.CHECK,
                  **options) -> sanitizer.Report:
    """Inspect `repo_root` for banned typography and return the structured report.

    Runs in-process rather than shelling out to `sanitize_typography.py`: the policy
    lives in `alongkit.sanitizer`, so there is nothing a subprocess adds except a
    stdout string to parse. That string is exactly what the commit engine used to
    grep (`"Total files sanitized: 0" not in res.stdout`), and it is what
    `[bug--typography-sanitizer-destroys-non-utf8-files]` REQ-5 removes.

    Defaults to check mode, so calling this never modifies a file by accident.
    """
    report = sanitizer.run(repo_root, mode=mode, **options)
    if verbose and not report.clean:
        print(f"-> [Typography] {sanitizer.format_report(report)}")
    return report


def typography_gate(repo_root: str, label: str = "Quality Gate",
                    allow_fix: bool = False, **options) -> bool:
    """The pre-commit and pre-release typography gate. True when the caller may proceed.

    With `allow_fix` the banned characters are replaced and the gate passes; without
    it nothing is written and a finding fails the gate. An automated path must never
    rewrite a user's files without being told to: the previous behaviour was a
    repository-wide rewrite before every commit, with a lossy read that deleted the
    contents of any file that was not valid UTF-8.

    Files that could not be decoded are always reported, in both outcomes: they are
    the ones the old tool destroyed silently, so their names belong in the log even
    when the run is otherwise clean.
    """
    mode = sanitizer.Mode.WRITE if allow_fix else sanitizer.Mode.CHECK
    report = run_sanitizer(repo_root, verbose=False, mode=mode, **options)

    for skipped in report.skipped:
        print(f"-> [{label}] typography: skipped {skipped.path} ({skipped.reason})")

    if report.clean:
        print(f"-> [{label}] Typography clean ({report.files_scanned} files scanned).")
        return True

    if allow_fix:
        print(f"-> [{label}] Typography repaired:\n{sanitizer.format_report(report)}")
        return True

    print(f"[Error] {label}: banned typography found.\n"
          f"{sanitizer.format_report(report)}\n"
          "Re-run with --fix-typography to apply these replacements, or fix them by hand.",
          file=sys.stderr)
    return False


@dataclass(frozen=True)
class ExceptionViolation:
    """A violation of the exception-handling quality gate."""
    path: str
    line: int
    message: str


ENTITY_INTEGRITY_GATE = "entity_reference_integrity"


def entity_integrity_errors(repo_root: str) -> List[str]:
    """Dangling references and enum violations as "path: message" lines (empty when clean).

    The other `validate_entities` findings (missing dates, slug/filename drift) stay with
    `along doctor --entities`; this gate owns what the graph and the enums need.
    """
    from . import entities
    report = entities.validate_entities(repo_root)
    return [f"{repo.normalize_posix(rel)}: {msg}" for rel, msg in report["errors"]
            if entities.is_integrity_error(msg)]


def split_entity_integrity_errors(repo_root: str) -> Tuple[List[str], List[str]]:
    """`entity_integrity_errors` split into (new, pre-existing) against `HEAD`.

    A problem already present at `HEAD` is pre-existing: it was not introduced by the
    current change, so the gates report it without blocking. Without a `HEAD` every
    problem is new. [bug--entity-gate-blocks-preexisting-problems]
    """
    from . import gitgates
    problems = entity_integrity_errors(repo_root)
    if not problems:
        return [], []
    baseline = gitgates.baseline_entity_problems(repo_root)
    if not baseline:
        return problems, []
    known = {f"{location}: {message}" for location, message in baseline}
    return ([p for p in problems if p not in known], [p for p in problems if p in known])


def report_preexisting_entity_problems(old: List[str], label: str, limit: int = 10) -> None:
    """Print pre-existing entity problems as a non-blocking warning."""
    if not old:
        return
    print(f"[Warning] {label}: {len(old)} pre-existing entity graph problem(s) at HEAD, "
          "not blocking [gate: entity-reference-integrity]:", file=sys.stderr)
    for line in old[:limit]:
        print(f"   - {line}", file=sys.stderr)
    if len(old) > limit:
        print(f"   ... {len(old) - limit} more", file=sys.stderr)
    print("   Inspect them with `along doctor --entities` (`--fix` drops dangling milestone "
          "fields).", file=sys.stderr)


def entity_integrity_gate(repo_root: str, label: str = "Quality Gate") -> bool:
    """[gate: entity-reference-integrity] for the wrap and projection-sync stages.

    Dangling references and schema / enum violations the current change introduces fail
    the gate in `enforce` mode; in `shadow` mode (`.along/config.json` hooks mode or gate
    override) they are reported and the caller proceeds. Problems already present at
    `HEAD` are printed as a warning and never fail it. True when the caller may proceed.
    """
    from .hooks import config as hook_config

    problems, old = split_entity_integrity_errors(repo_root)
    report_preexisting_entity_problems(old, label)
    if not problems:
        return True
    enforcing = hook_config.load_config(repo_root).is_enforcing(ENTITY_INTEGRITY_GATE)
    level = "Error" if enforcing else "Warning"
    print(f"[{level}] {label}: entity graph has {len(problems)} new problem(s) "
          "[gate: entity-reference-integrity]:", file=sys.stderr)
    for line in problems:
        print(f"   - {line}", file=sys.stderr)
    print("   Fix the references, or use `along issue rename` / `along issue supersede` "
          "instead of deleting a referenced entity.", file=sys.stderr)
    return not enforcing


def _catches_generic_exception(node_type: Optional[ast.AST]) -> bool:
    if node_type is None:
        return False
    if isinstance(node_type, ast.Name) and node_type.id in ("Exception", "BaseException"):
        return True
    if isinstance(node_type, ast.Tuple):
        return any(_catches_generic_exception(elt) for elt in node_type.elts)
    return False


def find_exception_violations_in_code(source: str, filename: str = "<unknown>") -> List[ExceptionViolation]:
    """Parse Python source and detect banned exception handling patterns:
    - Bare 'except:' clauses without exception types
    - Swallowed generic 'except Exception:' or 'except BaseException:' with pass/continue or no re-raise
    """
    try:
        tree = ast.parse(source, filename=filename)
    except SyntaxError:
        return []

    violations: List[ExceptionViolation] = []
    str_types = (ast.Constant, getattr(ast, "Str", ()))
    for node in ast.walk(tree):
        if isinstance(node, ast.ExceptHandler):
            # Check 1: bare except:
            if node.type is None:
                violations.append(
                    ExceptionViolation(
                        path=filename,
                        line=node.lineno,
                        message="bare 'except:' clause is forbidden; specify narrow exception types",
                    )
                )
            # Check 2: catch generic Exception / BaseException
            elif _catches_generic_exception(node.type):
                has_raise = any(isinstance(child, ast.Raise) for child in ast.walk(node))
                if not has_raise:
                    is_swallowed = all(
                        isinstance(stmt, (ast.Pass, ast.Continue)) or
                        (isinstance(stmt, ast.Expr) and isinstance(getattr(stmt, "value", None), str_types))
                        for stmt in node.body
                    )
                    reason = (
                        "swallowed generic exception (pass/continue)"
                        if is_swallowed
                        else "generic Exception caught without re-raising"
                    )
                    violations.append(
                        ExceptionViolation(
                            path=filename,
                            line=node.lineno,
                            message=f"{reason}; narrow to specific exceptions or re-raise",
                        )
                    )
    violations.sort(key=lambda v: v.line)
    return violations


def check_exception_handling(repo_root: str,
                             target_dirs: Optional[List[str]] = None) -> List[ExceptionViolation]:
    """Inspect Python files in target directories for banned exception handling.

    Defaults to scanning `scripts/` and `dashboard/`.
    """
    if target_dirs is None:
        target_dirs = ["scripts", "dashboard"]

    violations: List[ExceptionViolation] = []
    for target in target_dirs:
        target_path = os.path.join(repo_root, target)
        if not os.path.exists(target_path):
            continue
        if os.path.isfile(target_path) and target_path.endswith(".py"):
            rel_path = repo.safe_relpath(target_path, repo_root).replace("\\", "/")
            try:
                with open(target_path, "r", encoding="utf-8", errors="replace") as f:
                    code = f.read()
                violations.extend(find_exception_violations_in_code(code, rel_path))
            except (OSError, UnicodeDecodeError):
                pass
            continue

        for root, dirs, files in os.walk(target_path):
            dirs[:] = [d for d in dirs if d not in repo.IGNORED_DIRS and d != "__pycache__"]
            for file in sorted(files):
                if not file.endswith(".py"):
                    continue
                file_path = os.path.join(root, file)
                rel_path = repo.safe_relpath(file_path, repo_root).replace("\\", "/")
                try:
                    with open(file_path, "r", encoding="utf-8", errors="replace") as f:
                        code = f.read()
                    violations.extend(find_exception_violations_in_code(code, rel_path))
                except (OSError, UnicodeDecodeError):
                    pass

    return violations


def exception_handling_gate(repo_root: str, label: str = "Quality Gate") -> bool:
    """Quality gate enforcing clean exception handling across scripts/ and dashboard/."""
    violations = check_exception_handling(repo_root)
    if not violations:
        print(f"-> [{label}] Exception handling clean (zero swallowed generic exceptions).")
        return True

    print(f"[Error] {label}: banned exception handling detected ({len(violations)} violation(s)):", file=sys.stderr)
    for v in violations:
        print(f"   - {v.path}:{v.line}: {v.message}", file=sys.stderr)
    return False


def syntax_gate(repo_root: str, label: str = "Quality Gate",
                target_dirs: Optional[List[str]] = None) -> bool:
    """Pre-flight syntax validation gate.

    Compiles Python source files across target directories using compileall and halts
    if any syntax or indentation error is detected. Emits human- and agent-readable
    diagnostic output naming the exact file, line number, and error message.
    """
    if target_dirs is None:
        target_dirs = ["scripts", "tests", ".along/scripts"]

    dirs_to_check = [
        d for d in target_dirs
        if os.path.exists(os.path.join(repo_root, d))
    ]
    if not dirs_to_check:
        return True

    print(f"-> [{label}] Verifying Python syntax integrity across {', '.join(dirs_to_check)}...")
    cmd = [sys.executable, "-m", "compileall", "-q"] + dirs_to_check
    res = proc.run_capture(cmd, cwd=repo_root, trip_on_anomaly=False)
    if res.ok:
        print(f"-> [{label}] Python syntax clean across {len(dirs_to_check)} target directory(ies).")
        return True

    print(f"[Error] {label}: Python syntax compilation failed.\n", file=sys.stderr)
    output = (res.stderr or "") + (res.stdout or "")
    if output.strip():
        print(output.strip(), file=sys.stderr)
    return False


def session_edited_files(repo_root: str) -> set:
    """Repository-relative POSIX paths the agent sessions recorded as edited.

    Union of `edited_files` over the shared and per-session activity traces in
    `.along/diagnostics/`.
    """
    diag = repo.diagnostics_dir(repo_root)
    traces = [os.path.join(diag, "activity_trace.json")]
    activity = os.path.join(diag, "activity")
    if os.path.isdir(activity):
        traces += [os.path.join(activity, f) for f in os.listdir(activity) if f.endswith(".json")]
    edited = set()
    for path in traces:
        try:
            with open(path, "r", encoding="utf-8") as handle:
                data = json.load(handle)
        except (OSError, ValueError):
            continue
        if isinstance(data, dict):
            edited.update(repo.normalize_posix(str(p)) for p in data.get("edited_files") or [])
    return edited


def _empty_changed_files(repo_root: str) -> Tuple[List[str], Optional[str]]:
    """0-byte modified or untracked files under `repo_root` (relative POSIX), and the git top.

    The git top is None when git cannot list changes; the whole tree is walked then.
    """
    def empty(path: str) -> bool:
        try:
            return os.path.isfile(path) and os.path.getsize(path) == 0
        except OSError:
            return False

    root = os.path.realpath(os.path.abspath(repo_root))
    res = proc.git(["status", "--porcelain", "-u", "--", "."], cwd=root)
    top_res = proc.git(["rev-parse", "--show-toplevel"], cwd=root) if res.ok else None
    top = os.path.realpath(top_res.out.strip()) if top_res is not None and top_res.ok else ""
    if not res.ok or not top:
        found = []
        for current, _, files in os.walk(root):
            if any(part in repo.IGNORED_DIRS for part in current.split(os.sep)):
                continue
            for f in files:
                p = os.path.join(current, f)
                if f != ".gitkeep" and empty(p):
                    found.append(repo.safe_relpath(p, root).replace("\\", "/"))
        return sorted(found), None

    found = []
    # Raw stdout: `out` strips the leading status column of the first line.
    for line in res.stdout.splitlines():
        if not line.strip():
            continue
        payload = line[3:].strip()
        if " -> " in payload:
            payload = payload.split(" -> ", 1)[1].strip()
        if payload.startswith('"') and payload.endswith('"'):
            payload = payload[1:-1]
        if os.path.basename(payload) == ".gitkeep":
            continue
        # Porcelain paths are relative to the git top, not to a subproject context.
        full_path = os.path.normpath(os.path.join(top, payload))
        rel = os.path.relpath(full_path, root).replace("\\", "/")
        if rel.startswith("../") or not empty(full_path):
            continue
        found.append(rel)
    return sorted(found), top


def zero_byte_working_tree_audit(repo_root: str) -> Tuple[List[str], List[str]]:
    """0-byte changed files as (blocking, warnings), relative POSIX paths.

    Blocking means likely corruption: a tracked file that was non-empty at `HEAD` and is
    now empty, or an empty file an agent session edited. Any other empty file (a
    placeholder elsewhere in the tree, an empty `__init__.py`) only warns.
    [bug--wrap-zero-byte-audit-unscoped]
    """
    found, top = _empty_changed_files(repo_root)
    if not found:
        return [], []
    edited = session_edited_files(repo_root)
    blocking, warnings = [], []
    root = os.path.realpath(repo_root)
    for rel in found:
        truncated = False
        if top:
            top_rel = os.path.relpath(os.path.join(root, rel), top).replace("\\", "/")
            size = proc.git(["cat-file", "-s", f"HEAD:{top_rel}"], cwd=root)
            truncated = size.ok and size.out.strip().isdigit() and int(size.out.strip()) > 0
        (blocking if truncated or rel in edited else warnings).append(rel)
    return blocking, warnings


