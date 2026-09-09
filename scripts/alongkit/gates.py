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
from typing import List, Optional

from . import proc, repo, sanitizer


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


def run_repository_tests(repo_root: str, label: str = "Quality Gate") -> bool:
    """Run the repository's tests, printing the outcome. True when they passed or none exist."""
    cmd = detect_test_command(repo_root)
    if not cmd:
        return True

    print(f"-> [{label}] Running automated tests: {' '.join(cmd)}")
    res = proc.run_capture(cmd, cwd=repo_root)
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
    res = proc.run_capture(cmd, cwd=repo_root)
    if res.ok:
        print(f"-> [{label}] Python syntax clean across {len(dirs_to_check)} target directory(ies).")
        return True

    print(f"[Error] {label}: Python syntax compilation failed.\n", file=sys.stderr)
    output = (res.stderr or "") + (res.stdout or "")
    if output.strip():
        print(output.strip(), file=sys.stderr)
    return False

