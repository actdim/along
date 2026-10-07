#!/usr/bin/env python3
"""
alongkit.hooks.shellparse - Segment-aware classification of shell commands as read-only.

The inquiry/plan-approval gate lets read-only inspection and test commands through in every
session phase. It used to decide that by matching the whole command line against prefix or
substring patterns, so `ls && rm -rf src`, `rm -rf src; pytest` and `echo hi > src/a.py`
were all classified as safe reads. This module classifies a command as read-only only when
every segment of it is read-only:

1. The command is split on `;`, `&&`, `||`, `|`, a single `&` (background in POSIX shells,
   a command separator in cmd.exe) and newlines outside quotes. An `&` that belongs to a
   redirection (`2>&1`, `&>file`) does not split.
2. Command substitution (`$(...)` or backticks outside single quotes) is never read-only.
3. An output redirection (`>`, `>>`) outside quotes is a write unless its target is a null
   device (`/dev/null`, `NUL`, `$null`) or a descriptor duplication such as `2>&1`.
4. Each segment, after stripping runner wrappers (`uv run ...`, `poetry run`, `pipenv run`,
   `pdm run`, `hatch run`, `npx`), must start with a known read-only command or test runner.
5. `git` read subcommands are read-only only without flags that write: `--output` on
   `diff`/`log`/`show`, and anything that creates, deletes, renames or reconfigures a branch.
   Subcommands with read and write forms (`tag`, `remote`, `stash`, `config`, `reflog`,
   `worktree`, `notes`) pass only in their listing forms. Global options pass only when they
   neither run nor write (`--no-pager`, `-C <dir>`); `-c` can set a pager or alias and does
   not. See [bug--plan-gate-blocks-readonly-git].
6. `python -c` is read-only only for a single `print(...)` call with no other call inside.

See [bug--safe-command-prefix-bypass] and [bug--shell-classifier-residual-bypasses].
"""

from __future__ import annotations

import ast
import re
import shlex
from typing import List, Optional, Tuple

_NULL_TARGETS = ("/dev/null", "nul", "$null")

#: First words that only read (POSIX and PowerShell/cmd spellings).
_READ_COMMANDS = frozenset({
    "echo", "printf", "cat", "dir", "ls", "type", "head", "tail", "grep", "rg", "which",
    "where", "pwd", "cd", "wc", "stat", "file", "true",
    "cut", "tr", "nl", "basename", "dirname", "realpath", "du", "df", "test", "[", "diff", "cmp",
    "comm", "false",
    "get-childitem", "get-content", "select-string", "get-location", "set-location",
    "write-output", "write-host",
})

#: Subcommands that only read in every form (`--output` aside, checked separately).
_GIT_READ = frozenset({
    "status", "diff", "log", "show", "rev-parse", "describe", "ls-remote", "ls-files", "ls-tree",
    "cat-file", "rev-list", "for-each-ref", "show-ref", "show-branch", "blame", "shortlog",
    "merge-base", "grep", "name-rev", "count-objects", "cherry", "check-ignore", "check-attr",
    "whatchanged", "version",
})
#: Subcommands that read in some forms and write in others; `_GIT_MODAL` decides per form.
_GIT_MODAL = frozenset({"branch", "tag", "remote", "stash", "config", "reflog", "worktree", "notes"})
#: Flags that run a command or open files in a pager under any read subcommand (matched
#: case-sensitively: `git grep -O` runs a pager, `git grep -o` only prints matches).
_GIT_EXEC_FLAGS = ("--upload-pack", "-O", "--open-files-in-pager", "--ext-diff")
#: Global options before the subcommand that change neither what runs nor what is written.
#: `-c` is not among them: it can set `core.pager` or an alias to an arbitrary command.
_GIT_GLOBAL_FLAGS = frozenset({"--no-pager", "-P", "-p", "--paginate", "--no-optional-locks",
                               "--no-replace-objects", "--literal-pathspecs", "--bare"})
_GIT_GLOBAL_VALUE_OPTS = frozenset({"-C"})
_GIT_GLOBAL_VALUE_PREFIXES = ("--git-dir=", "--work-tree=")
#: `git tag` flags that only list or verify; any of them also makes positionals patterns.
_GIT_TAG_LIST_FLAGS = frozenset({
    "-l", "--list", "-v", "--verify", "--contains", "--no-contains", "--merged", "--no-merged",
    "--points-at", "--column", "--no-column", "-i", "--ignore-case", "--color", "--omit-empty",
})
_GIT_TAG_LIST_VALUE_PREFIXES = ("-n", "--sort=", "--format=", "--color=", "--column=",
                                "--contains=", "--no-contains=", "--merged=", "--no-merged=",
                                "--points-at=")
#: `git tag` list options that take the next word as their value.
_GIT_TAG_VALUE_OPTS = frozenset({"--sort", "--format", "--points-at"})
#: `git config` options that only select or format what is read.
_GIT_CONFIG_READ_FLAGS = frozenset({
    "--get", "--get-all", "--get-regexp", "--get-urlmatch", "-l", "--list", "--show-origin",
    "--show-scope", "--name-only", "--global", "--system", "--local", "--worktree", "-z",
    "--null", "--includes", "--no-includes", "--bool", "--int", "--path", "--bool-or-int",
    "--all", "--regexp",
})
_GIT_CONFIG_READ_MODES = frozenset({"--get", "--get-all", "--get-regexp", "--get-urlmatch",
                                    "-l", "--list"})
#: `git config` read options that carry a value (`--type=bool`, `--file path`, ...).
_GIT_CONFIG_READ_VALUE_OPTS = frozenset({"--default", "--type", "--file", "-f", "--blob", "--url",
                                         "--value", "--fixed-value"})
#: `git branch` flags that only list; any other flag, or a bare name, may write.
_GIT_BRANCH_LIST_FLAGS = frozenset({
    "-a", "-r", "-v", "-vv", "-l", "--list", "--all", "--remotes", "--verbose",
    "--show-current", "--no-color", "--color", "--column", "--no-column",
})
_GIT_BRANCH_LIST_VALUE_PREFIXES = ("--format=", "--sort=", "--color=", "--column=")
_ALONG_READ = (
    "test", "status", "doctor", "budget", "context-budget", "kb-search", "scratch state",
    "worktree list", "worktree status", "hook verify",
)
#: `find` primaries that run commands or write files.
_FIND_WRITE = frozenset({
    "-exec", "-execdir", "-ok", "-okdir", "-delete", "-fprint", "-fprint0", "-fprintf", "-fls",
})
#: Shell keywords that open a clause; the command after them decides.
_SHELL_LEAD_KEYWORDS = frozenset({"do", "then", "else", "elif", "if", "while", "until", "{"})
#: Shell keywords that close a clause and run nothing themselves.
_SHELL_CLOSE_KEYWORDS = frozenset({"done", "fi", "}"})
#: A sed script command that writes a file (`w`, `W`) or executes one (`e`, `s///e`).
_SED_WRITE = re.compile(r"[wWe](\s|$|;|\})")
_WRAPPER_OPTS_WITH_VALUE = frozenset({
    "--with", "--python", "-p", "--project", "--directory", "--extra", "--group", "--env-file",
    "--from", "--package",
})


def _substitution(command: str, i: int) -> Optional[Tuple[str, int]]:
    """(inner command, index after it) for the `$(...)` or backquote starting at `i`; None when
    it is unterminated."""
    if command[i] == "`":
        end = command.find("`", i + 1)
        return (command[i + 1:end], end + 1) if end != -1 else None
    depth = 0
    quote = ""
    j = i + 1
    while j < len(command):
        ch = command[j]
        if quote:
            if ch == quote:
                quote = ""
        elif ch in ("'", '"'):
            quote = ch
        elif ch == "(":
            depth += 1
        elif ch == ")":
            depth -= 1
            if depth == 0:
                return command[i + 2:j], j + 1
        j += 1
    return None


def split_segments(command: str) -> Optional[List[str]]:
    """Split on control operators outside quotes. Command substitutions are classified on their
    own and stand in as a plain word when read-only. None when the command is not simple
    enough to classify (unbalanced quotes, a substitution that may write)."""
    segments: List[str] = []
    buf: List[str] = []
    quote = ""
    i = 0
    n = len(command)
    while i < n:
        ch = command[i]
        if (ch == "`" or command.startswith("$(", i)) and quote != "'":
            sub = _substitution(command, i)
            if sub is None or not is_read_only_command(sub[0]):
                return None
            buf.append("SUBST")
            i = sub[1]
            continue
        if quote:
            if ch == quote:
                quote = ""
            buf.append(ch)
            i += 1
            continue
        if ch in ("'", '"'):
            quote = ch
            buf.append(ch)
            i += 1
            continue
        two = command[i:i + 2]
        if two in ("&&", "||"):
            segments.append("".join(buf))
            buf = []
            i += 2
            continue
        if ch in (";", "|", "\n", "\r"):
            segments.append("".join(buf))
            buf = []
            i += 1
            continue
        if ch == "&" and not (buf and buf[-1] == ">") and not command.startswith("&>", i):
            segments.append("".join(buf))
            buf = []
            i += 1
            continue
        buf.append(ch)
        i += 1
    if quote:
        return None
    segments.append("".join(buf))
    return [s.strip() for s in segments if s.strip()]


def _has_write_redirect(segment: str) -> bool:
    """True when the segment redirects output to a real file."""
    quote = ""
    i = 0
    n = len(segment)
    while i < n:
        ch = segment[i]
        if quote:
            if ch == quote:
                quote = ""
            i += 1
            continue
        if ch in ("'", '"'):
            quote = ch
            i += 1
            continue
        if ch == ">":
            j = i + 1
            if j < n and segment[j] == ">":
                j += 1
            if j < n and segment[j] == "&":
                i = j + 1
                continue
            rest = segment[j:].lstrip()
            target = rest.split()[0] if rest.split() else ""
            if target.strip("'\"").lower() not in _NULL_TARGETS:
                return True
            i = j
            continue
        i += 1
    return False


def _tokens(segment: str) -> Optional[List[str]]:
    try:
        raw = shlex.split(segment, posix=False)
    except ValueError:
        return None
    return [t.strip("'\"") for t in raw]


def _strip_wrappers(tokens: List[str]) -> List[str]:
    """Drop `uv run [opts]`, `poetry run`, `npx`, ... and environment assignments."""
    changed = True
    while changed and tokens:
        changed = False
        while tokens and re.match(r"^[A-Za-z_][A-Za-z0-9_]*=", tokens[0]):
            tokens = tokens[1:]
            changed = True
        if len(tokens) >= 2 and tokens[0].lower() in ("uv", "poetry", "pipenv", "pdm", "hatch") \
                and tokens[1].lower() == "run":
            tokens = tokens[2:]
            while tokens and tokens[0].startswith("-"):
                opt = tokens[0].split("=", 1)[0]
                tokens = tokens[2:] if (opt in _WRAPPER_OPTS_WITH_VALUE and "=" not in tokens[0]) else tokens[1:]
            changed = True
        elif tokens and tokens[0].lower() == "npx":
            tokens = tokens[1:]
            changed = True
    return tokens


def _is_python(word: str) -> bool:
    base = word.replace("\\", "/").rsplit("/", 1)[-1].lower()
    return bool(re.match(r"^(python\d*(\.\d+)?|py)(\.exe)?$", base))


def _strip_git_globals(words: List[str]) -> Optional[List[str]]:
    """`words` (original case) without the leading global options that neither run nor write
    anything; None when a global option is not one of them (`-c`, `--exec-path=...`)."""
    while words and words[0].startswith("-"):
        opt = words[0]
        if opt in _GIT_GLOBAL_FLAGS or opt.startswith(_GIT_GLOBAL_VALUE_PREFIXES):
            words = words[1:]
        elif opt in _GIT_GLOBAL_VALUE_OPTS and len(words) > 1:
            words = words[2:]
        else:
            return None
    return words


def _git_branch_is_read_only(args: List[str]) -> bool:
    listing = any(a in ("-l", "--list") for a in args)
    for a in args:
        if a in _GIT_BRANCH_LIST_FLAGS or a.startswith(_GIT_BRANCH_LIST_VALUE_PREFIXES):
            continue
        if not a.startswith("-") and listing:
            continue  # pattern for `--list`
        return False
    return True


def _git_tag_is_read_only(args: List[str]) -> bool:
    """Bare `git tag` and its list/verify forms; a positional without them creates a tag."""
    listing = False
    positional = False
    i = 0
    while i < len(args):
        a = args[i]
        if a in _GIT_TAG_VALUE_OPTS:
            listing = True
            i += 2
            continue
        if a in _GIT_TAG_LIST_FLAGS or a.startswith(_GIT_TAG_LIST_VALUE_PREFIXES):
            listing = True
        elif a.startswith("-"):
            return False  # -a, -s, -m, -F, -d, -f, -e, -u: create, sign, delete, edit
        else:
            positional = True
        i += 1
    return listing or not positional


def _git_config_is_read_only(args: List[str]) -> bool:
    """`git config get|list ...` and the `--get*` / `--list` forms of the option syntax."""
    words = [a for a in args if not a.startswith("-")]
    flags = [a.split("=", 1)[0] for a in args if a.startswith("-")]
    if not (words and words[0] in ("get", "list")) \
            and not any(f in _GIT_CONFIG_READ_MODES for f in flags):
        return False  # `git config key value` sets; `git config key` alone is not worth parsing
    return all(f in _GIT_CONFIG_READ_FLAGS or f in _GIT_CONFIG_READ_VALUE_OPTS for f in flags)


def _git_modal_is_read_only(sub: str, args: List[str]) -> bool:
    words = [a for a in args if not a.startswith("-")]
    action = words[0] if words else ""
    if sub == "branch":
        return _git_branch_is_read_only(args)
    if sub == "tag":
        return _git_tag_is_read_only(args)
    if sub == "config":
        return _git_config_is_read_only(args)
    if sub == "remote":
        if not args:
            return True
        if args[0] in ("-v", "--verbose"):
            return len(args) == 1 or (args[1] in ("show", "get-url") and len(args) <= 4)
        return args[0] in ("show", "get-url")
    if sub == "stash":
        return action in ("list", "show")
    if sub == "reflog":
        # Bare `git reflog` is `git reflog show`; `expire` and `delete` rewrite the reflog.
        return action in ("", "show", "exists")
    if sub == "worktree":
        return action == "list"
    if sub == "notes":
        return action in ("list", "show")
    return False


def _git_is_read_only(words: List[str]) -> bool:
    """`words` are the words after `git` in their original case: `-C` and `-c`, `-O` and `-o`
    differ only in case."""
    stripped = _strip_git_globals(words)
    if not stripped:
        return False
    if any(a == flag or a.startswith(flag + "=") for a in stripped[1:] for flag in _GIT_EXEC_FLAGS):
        return False
    sub, args = stripped[0].lower(), [a.lower() for a in stripped[1:]]
    if any(a == "--output" or a.startswith("--output=") for a in args):
        return False
    if sub in _GIT_READ:
        return True
    if sub in _GIT_MODAL:
        return _git_modal_is_read_only(sub, args)
    return False


def _python_c_is_read_only(code: str) -> bool:
    """A single `print(...)` whose arguments call nothing else."""
    try:
        tree = ast.parse(code.strip(), mode="exec")
    except (SyntaxError, ValueError):
        return False
    if len(tree.body) != 1 or not isinstance(tree.body[0], ast.Expr):
        return False
    call = tree.body[0].value
    if not (isinstance(call, ast.Call) and isinstance(call.func, ast.Name) and call.func.id == "print"):
        return False
    return sum(isinstance(node, ast.Call) for node in ast.walk(call)) == 1


def _sed_is_read_only(args: List[str]) -> bool:
    """`sed` without in-place editing, script files, or write/execute script commands."""
    scripts: List[str] = []
    positional: List[str] = []
    i = 0
    while i < len(args):
        arg = args[i]
        if arg in ("-e", "--expression"):
            if i + 1 >= len(args):
                return False
            scripts.append(args[i + 1])
            i += 2
            continue
        if arg.startswith("--expression="):
            scripts.append(arg.split("=", 1)[1])
        elif arg.startswith("--in-place") or arg in ("-f", "--file") or arg.startswith("--file="):
            return False
        elif arg.startswith("-") and not arg.startswith("--") and len(arg) > 1:
            if "i" in arg or "f" in arg:
                return False
        elif not arg.startswith("-"):
            positional.append(arg)
        i += 1
    if not scripts:
        if not positional:
            return False
        scripts.append(positional[0])
    return not any(_SED_WRITE.search(s) for s in scripts)


_AWK_NAMES = frozenset({"awk", "gawk", "mawk", "nawk"})
#: An awk program that runs commands, or prints into a file or a pipe.
_AWK_WRITE = re.compile(r"\bsystem\s*\(|\|\s*getline\b|\bprintf?\b[^;{}]*?(?:>|\|)")
_AWK_OPTS_WITH_VALUE = frozenset({"-F", "-v", "--field-separator", "--assign"})


def _awk_is_read_only(args: List[str]) -> bool:
    """`awk` without in-place editing, program files, or writing/command-running programs."""
    program = None
    i = 0
    while i < len(args):
        arg = args[i]
        if arg in ("-i", "--include", "-f", "--file", "-E", "--exec") or arg.startswith(
                ("--include=", "--file=", "-f", "--exec=")):
            return False
        if arg in _AWK_OPTS_WITH_VALUE:
            i += 2
            continue
        if arg.startswith("-") and program is None:
            i += 1
            continue
        if program is None:
            program = arg
        i += 1
    return program is not None and not _AWK_WRITE.search(program)


def _segment_is_read_only(segment: str) -> bool:
    if _has_write_redirect(segment):
        return False
    tokens = _tokens(segment)
    if not tokens:
        return tokens is not None
    tokens = _strip_wrappers(tokens)
    while tokens and tokens[0].lower() in _SHELL_LEAD_KEYWORDS:
        tokens = _strip_wrappers(tokens[1:])
    if not tokens:
        return True
    first = tokens[0].lower()
    rest = [t.lower() for t in tokens[1:]]

    if first in _SHELL_CLOSE_KEYWORDS:
        return not rest
    if first == "for":
        # `for NAME in WORDS`: substitutions among the words were already classified.
        return len(rest) >= 1 and (len(rest) == 1 or rest[1] == "in")
    if first in _READ_COMMANDS:
        return True
    if first == "sed":
        return _sed_is_read_only(tokens[1:])
    if first in _AWK_NAMES:
        return _awk_is_read_only(tokens[1:])
    if first == "find":
        return not any(t in _FIND_WRITE for t in rest)
    if first == "sort":
        return not any(t.startswith("--output") or (t.startswith("-") and not t.startswith("--")
                                                    and "o" in t) for t in rest)
    if first == "uniq":
        return len([t for t in rest if not t.startswith("-")]) <= 1
    if first == "git":
        return _git_is_read_only(tokens[1:])
    if first == "along" or first.endswith("along_exec.py"):
        return _is_read_subcommand(" ".join(rest))
    if first in ("pytest", "along-test", "along_test"):
        return True
    if first in ("npm", "pnpm", "yarn"):
        return rest[:1] == ["test"] or rest[:2] == ["run", "test"] or rest[:2] == ["run", "test:quiet"]
    if first in ("cargo", "dotnet", "go"):
        return rest[:1] == ["test"]
    if _is_python(first):
        if not rest:
            return False
        if rest[0] in ("-v", "--version"):
            return True
        if rest[0] == "-c":
            return len(tokens) == 3 and _python_c_is_read_only(tokens[2])
        if rest[0] == "-m":
            return len(rest) > 1 and rest[1] in ("pytest", "unittest")
        script = rest[0].replace("\\", "/")
        if script.endswith(".along/scripts/test.py"):
            return True
        if script.endswith("along_exec.py"):
            return _is_read_subcommand(" ".join(rest[1:]))
        return False
    return False


def _is_read_subcommand(joined: str) -> bool:
    """True when the words after the Along CLI name a read-only subcommand.

    `doctor --fix` writes (it drops dangling milestone fields), so it is not read-only
    [bug--update-maintenance-friction] REQ-2.
    """
    if not any(joined == sub or joined.startswith(sub + " ") for sub in _ALONG_READ):
        return False
    return not (joined.split()[:1] == ["doctor"] and "--fix" in joined.split())


#: Along subcommands that only move Along's own state (entities, blackboards, projections).
#: The plan gate lets them through so an agent can create and start an issue before any plan
#: exists; `commit` and `bump` are not among them.
_ALONG_STATE = (
    "issue", "start", "scratch", "plan", "decision", "milestone", "session", "wrap",
    "kb-sync", "kb sync", "glossary", "risk", "spike", "checklist",
)

#: Along maintenance subcommands: they keep the installation itself current (protocol block,
#: migrations, hooks, merge drivers, rule packs), not a product change, so the plan gate lets
#: them through too. Removal (`uninstall`) is not maintenance. [bug--update-maintenance-friction]
_ALONG_MAINTENANCE = (
    "update", "init", "migrate", "doctor", "hook install", "git setup", "git sync",
    "rules attach", "rules restore",
)

#: `along commit` is not a state command: it passes the plan gate without an approval only for
#: an issue this session wrapped (a completion token), see `along_commit_issue`. A flag that
#: rewrites files takes the command out. See [bug--commit-blocked-after-wrap].
_COMMIT_REWRITE_FLAGS = ("--fix-typography",)


def _along_words(tokens: List[str]) -> Optional[List[str]]:
    """Lower-cased argument tokens after `along` / `along_exec.py`, or None if not the Along CLI."""
    tokens = _strip_wrappers(tokens)
    if not tokens:
        return None
    first = tokens[0].lower()
    if first == "along" or first.endswith("along_exec.py") or first.endswith("along.ps1"):
        return [t.lower() for t in tokens[1:]]
    if _is_python(first) and len(tokens) > 1 and tokens[1].replace("\\", "/").lower().endswith("along_exec.py"):
        return [t.lower() for t in tokens[2:]]
    return None


def _along_subcommand(tokens: List[str]) -> Optional[str]:
    """Words after `along` / `along_exec.py` when the segment invokes the Along CLI."""
    words = _along_words(tokens)
    return None if words is None else " ".join(words)


def along_subcommand(segment: str) -> Optional[str]:
    """Lower-cased words after the Along CLI in one command segment, or None if it is not one."""
    tokens = _tokens(segment)
    return _along_subcommand(tokens) if tokens else None


def _is_state_subcommand(sub: str) -> bool:
    return any(sub == s or sub.startswith(s + " ") for s in _ALONG_STATE)


def _is_maintenance_subcommand(sub: str) -> bool:
    words = sub.split()
    if "uninstall" in words or "--uninstall" in words:
        return False
    return any(sub == s or sub.startswith(s + " ") for s in _ALONG_MAINTENANCE)


def is_along_state_command(command: str) -> bool:
    """True when every segment runs an Along state or maintenance subcommand (or is read-only)."""
    segments = split_segments(command or "")
    if not segments:
        return False
    for seg in segments:
        if _has_write_redirect(seg):
            return False
        tokens = _tokens(seg)
        sub = _along_subcommand(tokens) if tokens else None
        if sub is not None and (_is_state_subcommand(sub) or _is_maintenance_subcommand(sub)):
            continue
        if not _segment_is_read_only(seg):
            return False
    return True


def _commit_issue_value(words: List[str]) -> str:
    """The `-i x` / `--issue x` / `--issue=x` value among `along commit` words, else ''."""
    for i, word in enumerate(words):
        if word in ("-i", "--issue") and i + 1 < len(words):
            return words[i + 1]
        if word.startswith("--issue="):
            return word.split("=", 1)[1]
    return ""


def is_along_commit(command: str) -> bool:
    """True when some segment of `command` runs `along commit`."""
    for seg in split_segments(command or "") or []:
        sub = along_subcommand(seg)
        if sub is not None and (sub == "commit" or sub.startswith("commit ")):
            return True
    return False


def along_commit_issue(command: str) -> Optional[str]:
    """Issue of a plain `along commit` the plan gate may pass on a completion token.

    The `-i/--issue` value (lower-cased) when exactly one segment runs `along commit`, without
    a file-rewriting flag or a write redirect, and every other segment is an Along state
    command or read-only; '' for such a commit without `-i`; None for anything else.
    See [bug--commit-blocked-after-wrap].
    """
    segments = split_segments(command or "")
    if not segments:
        return None
    issue: Optional[str] = None
    for seg in segments:
        if _has_write_redirect(seg):
            return None
        tokens = _tokens(seg)
        words = _along_words(tokens) if tokens else None
        if words and words[0] == "commit":
            # Tokens, not the joined words: a quoted message may itself contain "-i".
            if issue is not None or any(flag in words for flag in _COMMIT_REWRITE_FLAGS):
                return None
            issue = _commit_issue_value(words[1:])
            continue
        sub = None if words is None else " ".join(words)
        if sub is not None and _is_state_subcommand(sub):
            continue
        if not _segment_is_read_only(seg):
            return None
    return issue


def is_read_only_command(command: str) -> bool:
    """True only when every segment of `command` is a read-only inspection or a test run."""
    if not command or not command.strip():
        return True
    segments = split_segments(command)
    if segments is None:
        return False
    return all(_segment_is_read_only(seg) for seg in segments)


#: Flags that turn a checker into a rewriter.
_FIX_FLAGS = frozenset({"--fix", "--fix-only", "--write", "-w", "--unsafe-fixes", "--allow-dirty",
                        "--allow-staged"})
#: Package-script names that verify (`npm run <name>`): build output is not source.
_SCRIPT_VERIFY = frozenset({"build", "test", "lint", "typecheck", "type-check", "check", "tsc",
                            "test:quiet", "test:ci", "verify"})


def _segment_is_verification(segment: str) -> bool:
    """A build, test, lint or typecheck run: writes build output, never sources."""
    if _has_write_redirect(segment):
        return False
    tokens = _tokens(segment)
    if not tokens:
        return False
    tokens = _strip_wrappers(tokens)
    if not tokens:
        return False
    first = tokens[0].lower()
    if first.endswith(".exe"):
        first = first[:-4]
    rest = [t.lower() for t in tokens[1:]]
    if any(t in _FIX_FLAGS or t.startswith("--fix=") for t in rest):
        return False
    sub = rest[0] if rest else ""
    if first == "dotnet":
        return sub in ("build", "test", "msbuild")
    if first == "cargo":
        return sub in ("build", "check", "test", "clippy", "doc")
    if first == "go":
        return sub in ("build", "vet", "test")
    if first in ("npm", "pnpm", "yarn", "bun"):
        name = rest[1] if sub == "run" and len(rest) > 1 else sub
        return name in _SCRIPT_VERIFY
    if first in ("tsc", "vue-tsc", "mypy", "pyright", "eslint", "pytest", "vitest", "jest"):
        # Snapshot updates rewrite test files.
        return first not in ("vitest", "jest") or ("-u" not in rest and "--updatesnapshot" not in rest)
    if first == "ruff":
        return sub == "check"
    if first in ("mvn", "mvnw", "./mvnw"):
        return bool(rest) and all(t in ("test", "verify", "compile", "-q", "--quiet", "-b", "--batch-mode")
                                  for t in rest)
    if first in ("gradle", "gradlew", "./gradlew"):
        return bool(rest) and all(t in ("test", "build", "check", "-q", "--quiet") for t in rest)
    sub_along = _along_subcommand(tokens)
    if sub_along is not None:
        return sub_along.split(" ", 1)[0] in ("build", "test")
    if _is_python(first) and rest:
        script = rest[0].replace("\\", "/")
        return script.endswith((".along/scripts/build.py", ".along/scripts/test.py"))
    return False


def is_verification_command(command: str) -> bool:
    """True when every segment is read-only or a verification run (build, test, lint, typecheck).

    These change no sources, so the plan gate lets them through in every session phase;
    test-before-stop could otherwise demand a test run the plan gate forbids.
    See [bug--hook-activation-and-gate-deadlock].
    """
    segments = split_segments(command or "")
    if not segments:
        return False
    return all(_segment_is_read_only(seg) or _segment_is_verification(seg) for seg in segments)


def classify(command: str) -> Tuple[bool, List[str]]:
    """(read_only, segments) - for diagnostics and tests."""
    segments = split_segments(command) or []
    return is_read_only_command(command), segments
