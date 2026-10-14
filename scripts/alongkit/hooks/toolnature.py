#!/usr/bin/env python3
"""
alongkit.hooks.toolnature - Tool nature classification engine.

Classifies agent tools and shell commands by their operational nature:
- read-only: Allowed in every phase.
- verification: Build, test, lint, typecheck - allowed in every phase.
- workspace-write: File generators, formatters, code edits - after plan approval.
- external: gh pr merge, push, deploy, send - after plan approval (asked every time).
- destructive: deletes outside repo, drop db, run arbitrary code - always asked.
- unknown: Unclassified tools held with reason to prompt user and classify.

Layers (nearest wins):
1. Repository: .along/rules/gates.yaml (tools: section) or .along/tool_rules.yaml
2. Global user pack: ~/.along/user-pack/tool_rules.yaml
3. Rule packs: .along/rules/*.yaml
4. Built-in defaults: alongkit.hooks.toolnature
"""

from __future__ import annotations

from dataclasses import dataclass, field
import fnmatch
import os
import re
import shlex
import tempfile
from typing import Any, Callable, Dict, List, Optional, Set, Tuple

from .. import bootstrap, proc, repo, textio
from . import shellparse


class ToolClass:
    READ_ONLY = "read-only"
    VERIFICATION = "verification"
    WORKSPACE_WRITE = "workspace-write"
    EXTERNAL = "external"
    DESTRUCTIVE = "destructive"
    UNKNOWN = "unknown"

    ALL = (READ_ONLY, VERIFICATION, WORKSPACE_WRITE, EXTERNAL, DESTRUCTIVE, UNKNOWN)
    VALID_CLASSES = (READ_ONLY, VERIFICATION, WORKSPACE_WRITE, EXTERNAL, DESTRUCTIVE)


DANGER_RANK: Dict[str, int] = {
    ToolClass.READ_ONLY: 0,
    ToolClass.VERIFICATION: 1,
    ToolClass.WORKSPACE_WRITE: 2,
    ToolClass.EXTERNAL: 3,
    ToolClass.DESTRUCTIVE: 4,
}


@dataclass
class NormalizedCall:
    tool: str
    subcommand: str = ""
    flags: List[str] = field(default_factory=list)
    flag_values: Dict[str, str] = field(default_factory=dict)
    args: List[str] = field(default_factory=list)
    raw_args: Dict[str, Any] = field(default_factory=dict)
    raw_cmd: str = ""
    write_redirect: bool = False


@dataclass
class ClassificationResult:
    tool_class: str
    rule_desc: str = ""
    layer: str = ""
    unclassified_pattern: str = ""
    segments: List[ClassificationResult] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        d: Dict[str, Any] = {
            "class": self.tool_class,
            "rule": self.rule_desc,
            "layer": self.layer,
        }
        if self.unclassified_pattern:
            d["unclassified_pattern"] = self.unclassified_pattern
        if self.segments:
            d["segments"] = [s.to_dict() for s in self.segments]
        return d


# ---------------------------------------------------------------------------
# Code Classifiers Registry (REQ-3 & REQ-6)
# ---------------------------------------------------------------------------

_CODE_CLASSIFIERS: Dict[str, Callable[[NormalizedCall], Optional[str]]] = {}


def register_classifier(tool_name: str, fn: Callable[[NormalizedCall], Optional[str]]) -> None:
    _CODE_CLASSIFIERS[tool_name.lower()] = fn


# ---------------------------------------------------------------------------
# Built-in Default Rules (REQ-3 & REQ-5)
# ---------------------------------------------------------------------------

BUILTIN_TOOL_RULES: Dict[str, Dict[str, Any]] = {
    # Standard Agent Tools
    "view_file": {"default": ToolClass.READ_ONLY},
    "read_file": {"default": ToolClass.READ_ONLY},
    "view_image": {"default": ToolClass.READ_ONLY},
    "grep_search": {"default": ToolClass.READ_ONLY},
    "find_by_name": {"default": ToolClass.READ_ONLY},
    "list_dir": {"default": ToolClass.READ_ONLY},
    "list_directory": {"default": ToolClass.READ_ONLY},
    "read_url_content": {"default": ToolClass.READ_ONLY},
    "search_web": {"default": ToolClass.READ_ONLY},
    "manage_task": {"default": ToolClass.READ_ONLY},
    "schedule": {"default": ToolClass.READ_ONLY},
    "send_message": {"default": ToolClass.READ_ONLY},
    "ask_question": {"default": ToolClass.READ_ONLY},
    "list_resources": {"default": ToolClass.READ_ONLY},
    "read_resource": {"default": ToolClass.READ_ONLY},
    "grep": {"default": ToolClass.READ_ONLY},
    "find_files": {"default": ToolClass.READ_ONLY},
    "file_search": {"default": ToolClass.READ_ONLY},
    "write_to_file": {"default": ToolClass.WORKSPACE_WRITE},
    "write_file": {"default": ToolClass.WORKSPACE_WRITE},
    "create_file": {"default": ToolClass.WORKSPACE_WRITE},
    "replace_file_content": {"default": ToolClass.WORKSPACE_WRITE},
    "edit_file": {"default": ToolClass.WORKSPACE_WRITE},
    "patch_file": {"default": ToolClass.WORKSPACE_WRITE},
    "delete_file": {"default": ToolClass.DESTRUCTIVE},
    "remove_file": {"default": ToolClass.DESTRUCTIVE},
    "unlink": {"default": ToolClass.DESTRUCTIVE},
    "delete": {"default": ToolClass.DESTRUCTIVE},
    "file_delete": {"default": ToolClass.DESTRUCTIVE},
    "remove": {"default": ToolClass.DESTRUCTIVE},

    # Common POSIX & Windows Utilities (Read-only)
    "echo": {"default": ToolClass.READ_ONLY},
    "printf": {"default": ToolClass.READ_ONLY},
    "cat": {"default": ToolClass.READ_ONLY},
    "dir": {"default": ToolClass.READ_ONLY},
    "ls": {"default": ToolClass.READ_ONLY},
    "type": {"default": ToolClass.READ_ONLY},
    "head": {"default": ToolClass.READ_ONLY},
    "tail": {"default": ToolClass.READ_ONLY},
    "rg": {"default": ToolClass.READ_ONLY},
    "ag": {"default": ToolClass.READ_ONLY},
    "ack": {"default": ToolClass.READ_ONLY},
    "which": {"default": ToolClass.READ_ONLY},
    "where": {"default": ToolClass.READ_ONLY},
    "pwd": {"default": ToolClass.READ_ONLY},
    "cd": {"default": ToolClass.READ_ONLY},
    "wc": {"default": ToolClass.READ_ONLY},
    "stat": {"default": ToolClass.READ_ONLY},
    "file": {"default": ToolClass.READ_ONLY},
    "true": {"default": ToolClass.READ_ONLY},
    "false": {"default": ToolClass.READ_ONLY},
    "cut": {"default": ToolClass.READ_ONLY},
    "tr": {"default": ToolClass.READ_ONLY},
    "nl": {"default": ToolClass.READ_ONLY},
    "basename": {"default": ToolClass.READ_ONLY},
    "dirname": {"default": ToolClass.READ_ONLY},
    "realpath": {"default": ToolClass.READ_ONLY},
    "du": {"default": ToolClass.READ_ONLY},
    "df": {"default": ToolClass.READ_ONLY},
    "test": {"default": ToolClass.READ_ONLY},
    "[": {"default": ToolClass.READ_ONLY},
    "diff": {"default": ToolClass.READ_ONLY},
    "cmp": {"default": ToolClass.READ_ONLY},
    "comm": {"default": ToolClass.READ_ONLY},
    "od": {"default": ToolClass.READ_ONLY},
    "date": {"default": ToolClass.READ_ONLY},
    "column": {"default": ToolClass.READ_ONLY},
    "tree": {"default": ToolClass.READ_ONLY},
    "env": {"default": ToolClass.READ_ONLY},
    "printenv": {"default": ToolClass.READ_ONLY},
    "uname": {"default": ToolClass.READ_ONLY},
    "whoami": {"default": ToolClass.READ_ONLY},
    "id": {"default": ToolClass.READ_ONLY},
    "ps": {"default": ToolClass.READ_ONLY},
    "top": {"default": ToolClass.READ_ONLY},
    "uptime": {"default": ToolClass.READ_ONLY},

    # PowerShell Read Utilities
    "get-childitem": {"default": ToolClass.READ_ONLY},
    "get-content": {"default": ToolClass.READ_ONLY},
    "select-string": {"default": ToolClass.READ_ONLY},
    "get-location": {"default": ToolClass.READ_ONLY},
    "set-location": {"default": ToolClass.READ_ONLY},
    "write-output": {"default": ToolClass.READ_ONLY},
    "write-host": {"default": ToolClass.READ_ONLY},
    "test-path": {"default": ToolClass.READ_ONLY},
    "select-object": {"default": ToolClass.READ_ONLY},
    "select": {"default": ToolClass.READ_ONLY},
    "measure-object": {"default": ToolClass.READ_ONLY},
    "measure": {"default": ToolClass.READ_ONLY},
    "compare-object": {"default": ToolClass.READ_ONLY},
    "out-string": {"default": ToolClass.READ_ONLY},
    "out-null": {"default": ToolClass.READ_ONLY},
    "out-host": {"default": ToolClass.READ_ONLY},
    "get-command": {"default": ToolClass.READ_ONLY},
    "gcm": {"default": ToolClass.READ_ONLY},
    "get-member": {"default": ToolClass.READ_ONLY},
    "gm": {"default": ToolClass.READ_ONLY},

    # Filesystem Mutation Utilities
    "touch": {"default": ToolClass.WORKSPACE_WRITE},
    "mkdir": {"default": ToolClass.WORKSPACE_WRITE},
    "md": {"default": ToolClass.WORKSPACE_WRITE},
    "cp": {"default": ToolClass.WORKSPACE_WRITE},
    "copy": {"default": ToolClass.WORKSPACE_WRITE},
    "mv": {"default": ToolClass.WORKSPACE_WRITE},
    "move": {"default": ToolClass.WORKSPACE_WRITE},
    "chmod": {"default": ToolClass.WORKSPACE_WRITE},
    "chown": {"default": ToolClass.WORKSPACE_WRITE},
    "ln": {"default": ToolClass.WORKSPACE_WRITE},
    "new-item": {"default": ToolClass.WORKSPACE_WRITE},
    "set-content": {"default": ToolClass.WORKSPACE_WRITE},
    "add-content": {"default": ToolClass.WORKSPACE_WRITE},
    "copy-item": {"default": ToolClass.WORKSPACE_WRITE},
    "move-item": {"default": ToolClass.WORKSPACE_WRITE},
    "out-file": {"default": ToolClass.WORKSPACE_WRITE},
    "del": {
        "default": ToolClass.WORKSPACE_WRITE,
        "rules": [
            {"match": {"arg_regex": r"(?:^|\s)(?:~|[/\\]|\.\.|\*|[a-zA-Z]:[/\\]|\$HOME|%USERPROFILE%)(?:\s|$)"}, "class": ToolClass.DESTRUCTIVE},
        ],
    },
    "erase": {
        "default": ToolClass.WORKSPACE_WRITE,
        "rules": [
            {"match": {"arg_regex": r"(?:^|\s)(?:~|[/\\]|\.\.|\*|[a-zA-Z]:[/\\]|\$HOME|%USERPROFILE%)(?:\s|$)"}, "class": ToolClass.DESTRUCTIVE},
        ],
    },
    "rm": {
        "default": ToolClass.WORKSPACE_WRITE,
        "rules": [
            {"match": {"arg_regex": r"(?:^|\s)(?:~|[/\\]|\.\.|\*|[a-zA-Z]:[/\\]|\$HOME|%USERPROFILE%)(?:\s|$)"}, "class": ToolClass.DESTRUCTIVE},
            {"match": {"any_flags": ["-rf", "-fr", "-r", "-R", "--recursive"], "arg_regex": r"(?:^|\s)(?:~|\$HOME|%USERPROFILE%|[/\\]|\.\.|[a-zA-Z]:[/\\]|\*|\.)(?:\s|$)"}, "class": ToolClass.DESTRUCTIVE},
        ],
    },
    "rmdir": {
        "default": ToolClass.WORKSPACE_WRITE,
        "rules": [
            {"match": {"arg_regex": r"(?:^|\s)(?:~|[/\\]|\.\.|\*|[a-zA-Z]:[/\\]|\$HOME|%USERPROFILE%)(?:\s|$)"}, "class": ToolClass.DESTRUCTIVE},
        ],
    },
    "remove-item": {
        "default": ToolClass.WORKSPACE_WRITE,
        "rules": [
            {"match": {"arg_regex": r"(?:^|\s)(?:~|[/\\]|\.\.|\*|[a-zA-Z]:[/\\]|\$HOME|%USERPROFILE%)(?:\s|$)"}, "class": ToolClass.DESTRUCTIVE},
        ],
    },
    "sudo": {"default": ToolClass.DESTRUCTIVE},
    "jq": {"default": ToolClass.READ_ONLY},
    "yq": {
        "default": ToolClass.READ_ONLY,
        "rules": [
            {"match": {"any_flags": ["-i", "--in-place"]}, "class": ToolClass.WORKSPACE_WRITE},
        ],
    },

    # gh (GitHub CLI)
    "gh": {
        "default": ToolClass.DESTRUCTIVE,
        "rules": [
            {"match": {"subcommand": "pr review"}, "class": ToolClass.EXTERNAL},
            {"match": {"subcommand": "* list|* view|* status|* diff|* checks"}, "class": ToolClass.READ_ONLY},
            {"match": {"subcommand": "api", "no_flags": ["-X", "--method", "-f", "-F", "--field", "--raw-field", "--input"]}, "class": ToolClass.READ_ONLY},
            {"match": {"subcommand": "api", "flag_value": {"-X": "GET"}}, "class": ToolClass.READ_ONLY},
            {"match": {"subcommand": "api", "flag_value": {"--method": "GET"}}, "class": ToolClass.READ_ONLY},
            {"match": {"subcommand": "api", "flag_value": {"-X": "DELETE"}}, "class": ToolClass.DESTRUCTIVE},
            {"match": {"subcommand": "api", "flag_value": {"--method": "DELETE"}}, "class": ToolClass.DESTRUCTIVE},
            {"match": {"subcommand": "api", "any_flags": ["-f", "-F", "--field", "--raw-field", "--input", "-X", "--method"]}, "class": ToolClass.EXTERNAL},
            {"match": {"subcommand": "api"}, "class": ToolClass.EXTERNAL},
            {"match": {"subcommand": "api graphql"}, "class": ToolClass.EXTERNAL},
            {"match": {"subcommand": "pr create|pr merge|issue create|pr close|issue close|pr comment|issue comment"}, "class": ToolClass.EXTERNAL},
            {"match": {"subcommand": "release create|release delete|repo create|repo fork|repo delete"}, "class": ToolClass.EXTERNAL},
            {"match": {"subcommand": "auth status"}, "class": ToolClass.READ_ONLY},
            {"match": {"subcommand": "extension exec|alias set"}, "class": ToolClass.DESTRUCTIVE},
        ],
    },

    # kubectl (Kubernetes CLI)
    "kubectl": {
        "default": ToolClass.DESTRUCTIVE,
        "rules": [
            {"match": {"subcommand": "get|describe|logs|explain|version|api-resources|api-versions|cluster-info"}, "class": ToolClass.READ_ONLY},
            {"match": {"subcommand": "diff"}, "class": ToolClass.READ_ONLY},
            {"match": {"subcommand": "apply|create|replace|patch|scale|autoscale"}, "class": ToolClass.WORKSPACE_WRITE},
            {"match": {"subcommand": "delete|drain|cordon"}, "class": ToolClass.DESTRUCTIVE},
            {"match": {"subcommand": "exec|run"}, "class": ToolClass.DESTRUCTIVE},
        ],
    },

    # docker
    "docker": {
        "default": ToolClass.DESTRUCTIVE,
        "rules": [
            {"match": {"subcommand": "ps|images|image ls|container ls|version|info|inspect|logs|history|top|port"}, "class": ToolClass.READ_ONLY},
            {"match": {"subcommand": "build|image build"}, "class": ToolClass.VERIFICATION},
            {"match": {"subcommand": "push|pull"}, "class": ToolClass.EXTERNAL},
            {"match": {"subcommand": "run|exec|stop|start|restart|kill|rm|rmi|container rm|image rm|system prune"}, "class": ToolClass.DESTRUCTIVE},
        ],
    },

    # npm / pnpm / yarn / bun
    "npm": {
        "default": ToolClass.WORKSPACE_WRITE,
        "rules": [
            {"match": {"subcommand": "test|run test|run test:quiet|run test:ci"}, "class": ToolClass.VERIFICATION},
            {"match": {"subcommand": "run build|run compile|run lint|run typecheck|run type-check|run check|run tsc|run verify"}, "class": ToolClass.VERIFICATION},
            {"match": {"subcommand": "audit|outdated|list|ls|view|info|whoami"}, "class": ToolClass.READ_ONLY},
            {"match": {"subcommand": "publish"}, "class": ToolClass.EXTERNAL},
        ],
    },
    "pnpm": {
        "default": ToolClass.WORKSPACE_WRITE,
        "rules": [
            {"match": {"subcommand": "test|run test|run test:quiet|run test:ci"}, "class": ToolClass.VERIFICATION},
            {"match": {"subcommand": "run build|run compile|run lint|run typecheck|run type-check|run check|run tsc|run verify"}, "class": ToolClass.VERIFICATION},
            {"match": {"subcommand": "audit|outdated|list|ls|view|info|whoami"}, "class": ToolClass.READ_ONLY},
            {"match": {"subcommand": "publish"}, "class": ToolClass.EXTERNAL},
        ],
    },
    "yarn": {
        "default": ToolClass.WORKSPACE_WRITE,
        "rules": [
            {"match": {"subcommand": "test|run test|run test:quiet|run test:ci"}, "class": ToolClass.VERIFICATION},
            {"match": {"subcommand": "run build|run compile|run lint|run typecheck|run type-check|run check|run tsc|run verify"}, "class": ToolClass.VERIFICATION},
            {"match": {"subcommand": "audit|outdated|list|ls|view|info|whoami"}, "class": ToolClass.READ_ONLY},
            {"match": {"subcommand": "publish"}, "class": ToolClass.EXTERNAL},
        ],
    },
    "bun": {
        "default": ToolClass.WORKSPACE_WRITE,
        "rules": [
            {"match": {"subcommand": "test|run test|run test:quiet|run test:ci"}, "class": ToolClass.VERIFICATION},
            {"match": {"subcommand": "run build|run compile|run lint|run typecheck|run type-check|run check|run tsc|run verify"}, "class": ToolClass.VERIFICATION},
            {"match": {"subcommand": "publish"}, "class": ToolClass.EXTERNAL},
        ],
    },

    # cargo
    "cargo": {
        "default": ToolClass.WORKSPACE_WRITE,
        "rules": [
            {"match": {"subcommand": "test|check|clippy|build|doc"}, "class": ToolClass.VERIFICATION},
            {"match": {"subcommand": "run"}, "class": ToolClass.DESTRUCTIVE},
            {"match": {"subcommand": "publish"}, "class": ToolClass.EXTERNAL},
        ],
    },

    # dotnet
    "dotnet": {
        "default": ToolClass.WORKSPACE_WRITE,
        "rules": [
            {"match": {"subcommand": "build|test|msbuild"}, "class": ToolClass.VERIFICATION},
            {"match": {"subcommand": "run"}, "class": ToolClass.DESTRUCTIVE},
            {"match": {"subcommand": "publish|nuget push"}, "class": ToolClass.EXTERNAL},
        ],
    },

    # go
    "go": {
        "default": ToolClass.WORKSPACE_WRITE,
        "rules": [
            {"match": {"subcommand": "build|vet|test"}, "class": ToolClass.VERIFICATION},
            {"match": {"subcommand": "run"}, "class": ToolClass.DESTRUCTIVE},
        ],
    },

    # Linters / typecheckers / test runners
    "pytest": {"default": ToolClass.VERIFICATION},
    "vitest": {
        "default": ToolClass.VERIFICATION,
        "rules": [
            {"match": {"any_flags": ["-u", "--updatesnapshot"]}, "class": ToolClass.WORKSPACE_WRITE},
        ],
    },
    "jest": {
        "default": ToolClass.VERIFICATION,
        "rules": [
            {"match": {"any_flags": ["-u", "--updatesnapshot"]}, "class": ToolClass.WORKSPACE_WRITE},
        ],
    },
    "ruff": {
        "default": ToolClass.VERIFICATION,
        "rules": [
            {"match": {"any_flags": ["--fix", "--fix-only"]}, "class": ToolClass.WORKSPACE_WRITE},
        ],
    },
    "eslint": {
        "default": ToolClass.VERIFICATION,
        "rules": [
            {"match": {"any_flags": ["--fix"]}, "class": ToolClass.WORKSPACE_WRITE},
        ],
    },
    "mypy": {"default": ToolClass.VERIFICATION},
    "pyright": {"default": ToolClass.VERIFICATION},
    "tsc": {"default": ToolClass.VERIFICATION},
    "vue-tsc": {"default": ToolClass.VERIFICATION},
}


# ---------------------------------------------------------------------------
# Built-in Code Classifier Implementations
# ---------------------------------------------------------------------------

_SAFE_GIT_CONFIG_KEYS = frozenset({
    "user.name",
    "user.email",
    "user.signingkey",
    "core.quotepath",
    "core.autocrlf",
    "core.safecrlf",
    "core.eol",
    "core.ignorecase",
    "core.filemode",
    "core.precomposeunicode",
    "diff.algorithm",
    "diff.renames",
    "diff.mnemonicprefix",
    "diff.noprefix",
    "diff.color",
    "rebase.autostash",
    "rebase.autosquash",
    "pull.rebase",
    "pull.ff",
    "merge.ff",
    "push.default",
    "init.defaultbranch",
    "status.submodulesummary",
    "status.showuntrackedfiles",
    "log.date",
    "log.decorate",
    "i18n.commitencoding",
    "i18n.logoutputencoding",
})


def _is_safe_git_c_key(key: str) -> bool:
    k = key.lower().strip()
    if not k:
        return False
    if k in _SAFE_GIT_CONFIG_KEYS:
        return True
    if k.startswith("color.") or k.startswith("advice."):
        return True
    return False


def _extract_git_global_options(raw_cmd: str) -> List[Tuple[str, Optional[str]]]:
    """Extract (opt_name, opt_val) for git global options preceding the git subcommand."""
    raw_toks = shellparse._tokens(raw_cmd) or []
    toks = shellparse._strip_wrappers(raw_toks)
    git_idx = -1
    for idx, t in enumerate(toks):
        t_base = os.path.basename(t.lower())
        if t_base.endswith(".exe"):
            t_base = t_base[:-4]
        if t_base == "git":
            git_idx = idx
            break
    if git_idx < 0:
        return []

    global_opts: List[Tuple[str, Optional[str]]] = []
    opts_with_val = {"-c", "--config-env", "--git-dir", "--work-tree", "--namespace", "--exec-path", "--upload-pack", "--receive-pack"}

    i = git_idx + 1
    n = len(toks)
    while i < n:
        tok = toks[i]
        if not tok.startswith("-"):
            # First non-flag token after git is the subcommand! Stop here.
            break
        if "=" in tok:
            opt_name, opt_val = tok.split("=", 1)
            global_opts.append((opt_name, opt_val))
        elif tok.startswith("-c") and len(tok) > 2:
            global_opts.append(("-c", tok[2:]))
        elif tok.lower() in opts_with_val:
            opt_val = toks[i + 1] if i + 1 < n and not toks[i + 1].startswith("-") else None
            global_opts.append((tok, opt_val))
            if opt_val is not None:
                i += 1
        else:
            global_opts.append((tok, None))
        i += 1

    return global_opts


def _classify_git(call: NormalizedCall) -> Optional[str]:
    """Git code classifier handling complex modal subcommands, global flags and destructive commands."""
    # Check ONLY git global options preceding the subcommand
    for opt_name, opt_val in _extract_git_global_options(call.raw_cmd):
        opt_l = opt_name.lower()
        if opt_l == "-c":
            cfg_k = (opt_val or "").split("=", 1)[0].strip()
            if not _is_safe_git_c_key(cfg_k):
                return ToolClass.DESTRUCTIVE
        elif opt_l in ("--upload-pack", "--receive-pack") or opt_l.startswith(("--upload-pack", "--receive-pack", "--config-env")):
            return ToolClass.DESTRUCTIVE

    sub = (call.subcommand or "").split()
    subcmd = sub[0] if sub else ""

    if subcmd in ("status", "diff", "log", "show", "rev-parse", "describe", "ls-remote", "ls-files",
                  "ls-tree", "cat-file", "rev-list", "for-each-ref", "show-ref", "show-branch", "blame",
                  "shortlog", "merge-base", "grep", "name-rev", "count-objects", "cherry", "check-ignore",
                  "check-attr", "whatchanged", "version"):
        if any(f in ("--output", "-o") for f in call.flags) or any(k.startswith("--output=") for k in call.flag_values):
            return ToolClass.WORKSPACE_WRITE
        return ToolClass.READ_ONLY

    if subcmd in ("push", "fetch", "pull"):
        return ToolClass.EXTERNAL

    if subcmd == "reset" and "--hard" in call.flags:
        return ToolClass.DESTRUCTIVE

    if subcmd == "clean" and any(f in ("-f", "-fd", "-df") or "f" in f for f in call.flags if f.startswith("-")):
        return ToolClass.DESTRUCTIVE

    # Modal subcommands
    args = call.args[1:] if len(call.args) > 1 else []
    if subcmd == "branch":
        if shellparse._git_branch_is_read_only(args + call.flags):
            return ToolClass.READ_ONLY
        return ToolClass.WORKSPACE_WRITE

    if subcmd == "tag":
        if shellparse._git_tag_is_read_only(args + call.flags):
            return ToolClass.READ_ONLY
        return ToolClass.WORKSPACE_WRITE

    if subcmd == "config":
        if shellparse._git_config_is_read_only(args + call.flags):
            return ToolClass.READ_ONLY
        return ToolClass.WORKSPACE_WRITE

    if subcmd == "remote":
        if not args or args[0] in ("-v", "--verbose") or args[0] in ("show", "get-url"):
            return ToolClass.READ_ONLY
        return ToolClass.WORKSPACE_WRITE

    if subcmd in ("stash", "notes"):
        action = args[0] if args else ""
        if action in ("list", "show") or (not action and subcmd == "notes"):
            return ToolClass.READ_ONLY
        return ToolClass.WORKSPACE_WRITE

    if subcmd == "reflog":
        action = args[0] if args else ""
        if action in ("", "show", "exists"):
            return ToolClass.READ_ONLY
        return ToolClass.WORKSPACE_WRITE

    if subcmd == "worktree":
        action = args[0] if args else ""
        if action == "list":
            return ToolClass.READ_ONLY
        return ToolClass.WORKSPACE_WRITE

    if subcmd in ("commit", "add", "rm", "checkout", "switch", "merge", "rebase", "cherry-pick", "clone"):
        return ToolClass.WORKSPACE_WRITE

    return None


def _classify_python(call: NormalizedCall, repo_root: Optional[str] = None) -> Optional[str]:
    """Python code classifier checking print vs arbitrary scripts."""
    if call.subcommand in ("-v", "--version") or any(f in ("-v", "--version") for f in call.flags):
        return ToolClass.READ_ONLY

    mod = call.flag_values.get("-m", "").lower()
    if mod in ("pytest", "unittest") or call.subcommand in ("-m pytest", "-m unittest"):
        return ToolClass.VERIFICATION

    if call.subcommand == "-c" and call.args:
        code = call.args[0]
        if shellparse._python_c_is_read_only(code):
            return ToolClass.READ_ONLY
        return ToolClass.DESTRUCTIVE

    if call.subcommand in (".along/scripts/test.py", ".along/scripts/build.py"):
        return ToolClass.VERIFICATION

    if any(a.endswith((".along/scripts/test.py", ".along/scripts/build.py")) for a in call.args):
        return ToolClass.VERIFICATION

    root = repo_root or repo.find_repo_root() or os.getcwd()
    root_norm = os.path.normcase(os.path.abspath(root))

    if call.args and not call.subcommand.startswith("-"):
        first_arg = call.args[0].strip("\"'")
        try:
            exp_arg = os.path.expanduser(os.path.expandvars(first_arg))
            abs_arg = os.path.normcase(os.path.abspath(os.path.join(root, exp_arg)))
        except (ValueError, OSError):
            abs_arg = ""

        # Script outside workspace is DESTRUCTIVE
        if not abs_arg or not repo.is_within(abs_arg, root_norm):
            return ToolClass.DESTRUCTIVE

        first_norm = first_arg.replace("\\", "/")
        if first_norm.startswith(("tests/", "test_", "scripts/", ".along/scripts/")) or first_norm.endswith((".py",)):
            return ToolClass.WORKSPACE_WRITE

    return ToolClass.DESTRUCTIVE


_CMD_FLAG_RE = re.compile(r"^/[a-zA-Z](?::\w+)?$")


def _expand_system_path(raw_path: str) -> str:
    """Expand PowerShell $env:NAME, standard %VAR% / $VAR, and user home ~ in paths."""
    p = raw_path.strip("\"'")
    p = re.sub(
        r"\$env:([A-Za-z_][A-Za-z0-9_]*)",
        lambda m: os.environ.get(m.group(1), os.environ.get(m.group(1).upper(), m.group(0))),
        p,
        flags=re.IGNORECASE,
    )
    p = os.path.expandvars(p)
    p = os.path.expanduser(p)
    return p


def _is_temp_dir_path(target_path: str) -> bool:
    """True when target_path resolves to a file or folder inside a system temporary directory."""
    if not target_path:
        return False
    try:
        t_norm = os.path.normcase(os.path.abspath(target_path))
    except (ValueError, OSError):
        return False

    temp_roots: Set[str] = set()
    for cand in (
        tempfile.gettempdir(),
        os.environ.get("TEMP"),
        os.environ.get("TMP"),
        os.environ.get("TMPDIR"),
        "/tmp",
        "/var/tmp",
    ):
        if cand:
            try:
                temp_roots.add(os.path.normcase(os.path.abspath(cand)))
            except (ValueError, OSError):
                pass

    for tr in temp_roots:
        if t_norm == tr:
            # Targeting the temp root itself (e.g. rm -rf /tmp) is dangerous
            return False
        if repo.is_within(t_norm, tr):
            return True
    return False


def _classify_deletion(call: NormalizedCall, repo_root: Optional[str] = None) -> Optional[str]:
    """Deletion classifier checking normalized target paths against repository root."""
    args: List[str] = []
    for a in call.args:
        if a.startswith("-"):
            continue
        if call.tool in ("del", "erase", "rmdir", "rd") and _CMD_FLAG_RE.match(a):
            continue
        args.append(a)

    targets = list(args)
    for opt in ("-path", "-literalpath"):
        val = call.flag_values.get(opt)
        if val:
            targets.append(val)

    if not targets:
        return ToolClass.WORKSPACE_WRITE

    root = repo_root or repo.find_repo_root() or os.getcwd()
    root_norm = os.path.normcase(os.path.abspath(root))
    user_home = os.path.normcase(os.path.abspath(os.path.expanduser("~")))
    git_dir = os.path.normcase(os.path.abspath(os.path.join(root, ".git")))
    along_dir = os.path.normcase(os.path.abspath(os.path.join(root, ".along")))

    has_recurse = any(f.lower() in ("-r", "-rf", "-fr", "--recursive", "-recurse", "/s") for f in call.flags) or \
                  any(f.lower().startswith("-r") or "recurse" in f.lower() for f in call.flags)

    for t in targets:
        t_raw = t.strip("\"'")
        if not t_raw:
            continue

        exp_t = _expand_system_path(t_raw)
        if _is_temp_dir_path(exp_t):
            continue

        # Wildcards
        if t_raw in ("*", ".*", "/*", "\\*"):
            return ToolClass.DESTRUCTIVE

        if t_raw.endswith(("/*", "\\*")):
            prefix = t_raw[:-2].rstrip("/\\")
            if not prefix or prefix in (".", "./", ".\\"):
                return ToolClass.DESTRUCTIVE
            try:
                abs_pref = os.path.normcase(os.path.abspath(os.path.join(root, prefix)))
            except (ValueError, OSError):
                return ToolClass.DESTRUCTIVE
            if abs_pref == root_norm or not repo.is_within(abs_pref, root_norm):
                return ToolClass.DESTRUCTIVE
            if abs_pref == git_dir or repo.is_within(abs_pref, git_dir):
                return ToolClass.DESTRUCTIVE
            if abs_pref == along_dir or repo.is_within(abs_pref, along_dir):
                return ToolClass.DESTRUCTIVE
            # Wildcard targeting contents of a repository subfolder (dist/*, build/*, etc.)
            continue

        if t_raw in ("/", "\\", ".") or (len(t_raw) >= 2 and t_raw[1] == ":" and len(t_raw) <= 3):
            return ToolClass.DESTRUCTIVE

        if re.match(r"^[a-zA-Z]:", t_raw) and os.name != "nt":
            return ToolClass.DESTRUCTIVE

        if t_raw in ("~", "$HOME", "%USERPROFILE%") or t_raw.startswith(("~/", "~\\", "$HOME/", "$HOME\\", "%USERPROFILE%\\")):
            exp = os.path.normcase(os.path.abspath(os.path.expanduser(os.path.expandvars(t_raw))))
            if exp == user_home or not repo.is_within(exp, root_norm):
                return ToolClass.DESTRUCTIVE

        try:
            exp_t = os.path.expanduser(os.path.expandvars(t_raw))
            abs_t = os.path.normcase(os.path.abspath(os.path.join(root, exp_t)))
        except (ValueError, OSError):
            return ToolClass.DESTRUCTIVE

        if not repo.is_within(abs_t, root_norm) and abs_t != root_norm:
            return ToolClass.DESTRUCTIVE

        if abs_t == root_norm:
            return ToolClass.DESTRUCTIVE

        # Internal critical protocol and VCS targets
        if abs_t == git_dir or repo.is_within(abs_t, git_dir):
            return ToolClass.DESTRUCTIVE

        if abs_t == along_dir or repo.is_within(abs_t, along_dir):
            return ToolClass.DESTRUCTIVE

        if has_recurse and (t_raw in (".", "./", ".\\", "*") or abs_t == root_norm):
            return ToolClass.DESTRUCTIVE

    return ToolClass.WORKSPACE_WRITE


def _classify_sed(call: NormalizedCall) -> Optional[str]:
    """Sed classifier inspecting expressions and in-place writes."""
    raw_args = call.args + call.flags
    if shellparse._sed_is_read_only(raw_args):
        return ToolClass.READ_ONLY
    return ToolClass.WORKSPACE_WRITE


def _classify_awk(call: NormalizedCall) -> Optional[str]:
    """Awk classifier inspecting scripts and system/file writers."""
    raw_args = call.args + call.flags
    if shellparse._awk_is_read_only(raw_args):
        return ToolClass.READ_ONLY
    return ToolClass.DESTRUCTIVE


def _classify_find(call: NormalizedCall) -> Optional[str]:
    """Find classifier identifying exec and delete flags."""
    raw_args = call.args + call.flags
    if any(a in shellparse._FIND_WRITE for a in raw_args):
        return ToolClass.DESTRUCTIVE
    return ToolClass.READ_ONLY


def _classify_along(call: NormalizedCall) -> Optional[str]:
    """Along CLI classifier distinguishing read-only, verification and state actions."""
    sub = (call.subcommand or "").strip()
    words = sub.split()
    if not words:
        return ToolClass.READ_ONLY

    first = words[0].lower()
    if first in ("--help", "-h", "help") or any(f in ("--help", "-h") for f in call.flags):
        return ToolClass.READ_ONLY

    if first in ("tool", "tools"):
        sub_tool = words[1].lower() if len(words) > 1 else ""
        if sub_tool in ("list", "explain"):
            return ToolClass.READ_ONLY
        return ToolClass.WORKSPACE_WRITE

    all_flags_and_words = set(call.flags) | set(words) | set(call.flag_values.keys())

    if first == "sanitize":
        if any(w in shellparse._SANITIZE_WRITE_FLAGS for w in all_flags_and_words):
            return ToolClass.WORKSPACE_WRITE
        return ToolClass.READ_ONLY

    if first == "doctor" and any(w in ("--fix", "-f") for w in all_flags_and_words):
        return ToolClass.WORKSPACE_WRITE

    if first in ("build", "test"):
        return ToolClass.VERIFICATION

    full_cmd = " ".join([first] + call.args[1:] + call.flags)
    if shellparse._is_read_subcommand(full_cmd) or shellparse._is_read_subcommand(sub):
        return ToolClass.READ_ONLY

    # State and maintenance commands are allowed in inquiry phase
    if shellparse._is_state_subcommand(sub) or shellparse._is_maintenance_subcommand(sub):
        return ToolClass.READ_ONLY

    if first in ("commit", "version-bump", "bump"):
        return ToolClass.WORKSPACE_WRITE

    return ToolClass.WORKSPACE_WRITE


def _classify_out_file(call: NormalizedCall, repo_root: Optional[str] = None) -> Optional[str]:
    """Out-File classifier verifying destination path safety."""
    targets: List[str] = []
    fv_lower = {k.lower(): v for k, v in call.flag_values.items()}
    for opt in ("-filepath", "-literalpath", "-path"):
        val = fv_lower.get(opt)
        if val:
            targets.append(val)
    if not targets and call.args:
        targets.extend(call.args)

    if not targets:
        return ToolClass.WORKSPACE_WRITE

    root = repo_root or repo.find_repo_root() or os.getcwd()
    root_norm = os.path.normcase(os.path.abspath(root))
    user_home = os.path.normcase(os.path.abspath(os.path.expanduser("~")))
    git_dir = os.path.normcase(os.path.abspath(os.path.join(root, ".git")))
    along_dir = os.path.normcase(os.path.abspath(os.path.join(root, ".along")))

    for t in targets:
        t_raw = t.strip("\"'")
        if not t_raw:
            continue
        tl = t_raw.replace("\\", "/").lower()
        if tl in ("/dev/null", "nul", "$null"):
            return ToolClass.READ_ONLY
        exp_t = _expand_system_path(t_raw)
        if _is_temp_dir_path(exp_t):
            continue

        if re.match(r"^[a-zA-Z]:", t_raw) and os.name != "nt":
            return ToolClass.DESTRUCTIVE

        if t_raw in ("~", "$HOME", "%USERPROFILE%") or t_raw.startswith(("~/", "~\\", "$HOME/", "$HOME\\", "%USERPROFILE%\\")):
            exp_home = os.path.normcase(os.path.abspath(exp_t))
            if exp_home == user_home or not repo.is_within(exp_home, root_norm):
                return ToolClass.DESTRUCTIVE
        try:
            abs_t = os.path.normcase(os.path.abspath(os.path.join(root, exp_t)))
        except (ValueError, OSError):
            return ToolClass.DESTRUCTIVE
        if abs_t == root_norm or not repo.is_within(abs_t, root_norm):
            return ToolClass.DESTRUCTIVE
        if abs_t == git_dir or repo.is_within(abs_t, git_dir):
            return ToolClass.DESTRUCTIVE
        if abs_t == along_dir or repo.is_within(abs_t, along_dir):
            return ToolClass.DESTRUCTIVE

    return ToolClass.WORKSPACE_WRITE


register_classifier("git", _classify_git)
register_classifier("python", _classify_python)
register_classifier("rm", _classify_deletion)
register_classifier("del", _classify_deletion)
register_classifier("erase", _classify_deletion)
register_classifier("rmdir", _classify_deletion)
register_classifier("remove-item", _classify_deletion)
register_classifier("sed", _classify_sed)
register_classifier("awk", _classify_awk)
register_classifier("find", _classify_find)
register_classifier("along", _classify_along)
register_classifier("out-file", _classify_out_file)


# ---------------------------------------------------------------------------
# Call Normalization (REQ-2)
# ---------------------------------------------------------------------------

def normalize_segment(segment: str) -> NormalizedCall:
    """Normalize a shell command segment into structured NormalizedCall."""
    seg = segment.strip()
    write_redir = shellparse._has_write_redirect(seg)
    raw_tokens = shellparse._tokens(seg) or []
    tokens = shellparse._strip_wrappers(raw_tokens)

    while tokens and tokens[0].lower() in shellparse._SHELL_LEAD_KEYWORDS:
        tokens = shellparse._strip_wrappers(tokens[1:])

    if not tokens:
        return NormalizedCall(tool="", raw_cmd=seg, write_redirect=write_redir)

    first = tokens[0].lower()
    if first.endswith(".exe"):
        first = first[:-4]

    along_words = shellparse._along_words(tokens)
    if along_words is not None:
        return _parse_tokens_into_call("along", along_words, raw_cmd=seg, write_redir=write_redir)

    if shellparse._is_python(first):
        if len(tokens) > 1:
            if tokens[1] in ("-v", "--version"):
                return NormalizedCall(tool="python", subcommand=tokens[1], raw_cmd=seg, write_redirect=write_redir)
            if tokens[1] == "-c":
                code = tokens[2] if len(tokens) > 2 else ""
                return NormalizedCall(tool="python", subcommand="-c", args=[code], raw_cmd=seg, write_redirect=write_redir)
            if tokens[1] == "-m":
                mod = tokens[2] if len(tokens) > 2 else ""
                return NormalizedCall(
                    tool="python",
                    subcommand=f"-m {mod}",
                    flags=["-m"],
                    flag_values={"-m": mod},
                    args=tokens[3:],
                    raw_cmd=seg,
                    write_redirect=write_redir,
                )
            script = tokens[1].replace("\\", "/")
            if script.endswith(".along/scripts/test.py"):
                return NormalizedCall(tool="python", subcommand=".along/scripts/test.py", raw_cmd=seg, write_redirect=write_redir)
            if script.endswith(".along/scripts/build.py"):
                return NormalizedCall(tool="python", subcommand=".along/scripts/build.py", raw_cmd=seg, write_redirect=write_redir)

    tool = os.path.basename(first).lower()
    return _parse_tokens_into_call(tool, tokens[1:], raw_cmd=seg, write_redir=write_redir)


_GENERIC_VAL_OPTIONS = frozenset({
    "-x", "--method", "-o", "--output", "-u", "--url",
    "-i", "--issue", "-t", "--type", "--field-separator", "--file", "--input",
})

_POWERSHELL_VAL_OPTIONS = frozenset({
    "-encoding", "-filepath", "-literalpath", "-path", "-destination", "-width", "-inputobject",
    "-delimiter", "-pattern", "-filter", "-include", "-exclude", "-name", "-value",
})

_FIND_VAL_OPTIONS = frozenset({
    "-name", "-iname", "-path", "-ipath", "-regex", "-type", "-perm", "-size", "-mtime", "-atime", "-ctime",
})

_GH_VAL_OPTIONS = frozenset({
    "-x", "--method", "-f", "-F", "--field", "--raw-field", "--input", "-r", "--repo", "-q", "--jq", "-t", "--template",
})

_GIT_VAL_OPTIONS = frozenset({
    "-m", "--message", "-f", "--file", "--author",
})


def _tool_val_options(tool: str) -> Set[str]:
    opts = set(_GENERIC_VAL_OPTIONS)
    tl = tool.lower()
    if tl in ("gh",):
        opts |= _GH_VAL_OPTIONS
    elif tl in ("git",):
        opts |= _GIT_VAL_OPTIONS
    elif tl in ("find",):
        opts |= _FIND_VAL_OPTIONS
    elif tl in (
        "out-file", "set-content", "add-content", "get-content", "remove-item",
        "copy-item", "move-item", "new-item", "select-string", "where-object",
        "select-object", "measure-object", "get-childitem",
    ) or "-" in tl:
        opts |= _POWERSHELL_VAL_OPTIONS
    return opts


def _parse_tokens_into_call(tool: str, rest_tokens: List[str], raw_cmd: str, write_redir: bool) -> NormalizedCall:
    flags: List[str] = []
    flag_values: Dict[str, str] = {}
    positionals: List[str] = []

    val_options = _tool_val_options(tool)

    i = 0
    n = len(rest_tokens)
    while i < n:
        tok = rest_tokens[i]
        if tok == "--":
            positionals.extend(rest_tokens[i + 1:])
            break
        if tok.startswith("-"):
            if "=" in tok:
                flag_name, val = tok.split("=", 1)
                flags.append(flag_name)
                flag_values[flag_name] = val
            elif tok.startswith("-X") and len(tok) > 2:
                flags.append("-X")
                flag_values["-X"] = tok[2:]
            else:
                flags.append(tok)
                if i + 1 < n and not rest_tokens[i + 1].startswith("-"):
                    flag_values[tok] = rest_tokens[i + 1]
                    takes_value = tok.lower() in val_options
                    if not takes_value and tool == "git" and len(positionals) == 0:
                        if tok.lower() in ("-c", "--config-env", "--git-dir", "--work-tree", "--namespace", "--exec-path"):
                            takes_value = True
                    if takes_value:
                        i += 1
        else:
            positionals.append(tok)
        i += 1

    subcommand = ""
    args: List[str] = list(positionals)
    if positionals:
        if len(positionals) >= 2 and tool in ("gh", "git", "docker", "kubectl", "npm", "pnpm", "yarn", "bun"):
            subcommand = f"{positionals[0]} {positionals[1]}"
        elif tool not in (
            "rm", "del", "erase", "rmdir", "rd", "remove-item",
            "out-file", "set-content", "add-content", "get-content",
            "cat", "type", "touch", "mkdir", "md", "cp", "mv", "copy", "move",
        ):
            subcommand = positionals[0]

    return NormalizedCall(
        tool=tool,
        subcommand=subcommand,
        flags=flags,
        flag_values=flag_values,
        args=args,
        raw_cmd=raw_cmd,
        write_redirect=write_redir,
    )


def normalize_tool_call(tool_name: str, tool_args: Dict[str, Any]) -> NormalizedCall:
    """Normalize agent or MCP tool calls into a NormalizedCall."""
    tool = tool_name.lower()
    raw_args = dict(tool_args or {})
    subcommand = ""

    if tool == "call_mcp_tool":
        mcp_name = (raw_args.get("name") or raw_args.get("tool_name") or "").lower()
        if mcp_name:
            tool = mcp_name
            subcommand = str(raw_args.get("action") or raw_args.get("subcommand") or "")
    else:
        subcommand = str(raw_args.get("action") or raw_args.get("subcommand") or raw_args.get("command") or "")

    return NormalizedCall(
        tool=tool,
        subcommand=subcommand,
        raw_args=raw_args,
    )


# ---------------------------------------------------------------------------
# Rule Matching Logic (REQ-2)
# ---------------------------------------------------------------------------

def _match_subcommand(call: NormalizedCall, pat: str) -> bool:
    """Match candidate subcommands against a pattern with wildcards and alternatives."""
    candidates = []
    if call.subcommand:
        candidates.append(call.subcommand.lower())
    if call.args:
        accum = []
        for a in call.args:
            accum.append(a.lower())
            sub_cand = " ".join(accum)
            if sub_cand not in candidates:
                candidates.append(sub_cand)
    if not candidates:
        candidates = [""]

    raw_alts = [a.strip() for a in pat.split("|") if a.strip()]
    distribute_wildcard = pat.strip().startswith("* ")

    for alt in raw_alts:
        alt_lower = alt.lower()
        has_star = "*" in alt_lower
        for cand in candidates:
            if cand == alt_lower:
                return True
            if cand.startswith(alt_lower + " "):
                return True
            if has_star and fnmatch.fnmatch(cand, alt_lower):
                return True
            if distribute_wildcard and not has_star:
                if fnmatch.fnmatch(cand, f"* {alt_lower}") or cand == alt_lower:
                    return True

    return False


def match_rule(call: NormalizedCall, rule: Dict[str, Any]) -> bool:
    """Evaluate whether NormalizedCall satisfies declarative rule match conditions."""
    match_crit = rule.get("match", {})
    if not match_crit:
        return True

    if "subcommand" in match_crit:
        pat = match_crit["subcommand"]
        if not _match_subcommand(call, pat):
            return False

    if "flags" in match_crit:
        req = match_crit["flags"]
        if isinstance(req, str):
            req = [req]
        if not all(f in call.flags for f in req):
            return False

    if "any_flags" in match_crit:
        req = match_crit["any_flags"]
        if isinstance(req, str):
            req = [req]
        if not any(f in call.flags for f in req):
            return False

    if "no_flags" in match_crit:
        forbidden = match_crit["no_flags"]
        if isinstance(forbidden, str):
            forbidden = [forbidden]
        if any(f in call.flags or f in call.flag_values for f in forbidden):
            return False

    if "flag_value" in match_crit:
        fv = match_crit["flag_value"]
        for flag, exp_val in fv.items():
            actual = call.flag_values.get(flag)
            if actual is None:
                return False
            if str(actual).lower() != str(exp_val).lower():
                return False

    if "arg_regex" in match_crit:
        pat = match_crit["arg_regex"]
        search_targets = [call.raw_cmd] + call.args + list(call.flag_values.values())
        if not any(re.search(pat, str(t)) for t in search_targets):
            return False

    if "args_empty" in match_crit:
        if bool(match_crit["args_empty"]) != (len(call.args) == 0):
            return False

    if "args" in match_crit:
        for k, exp in match_crit["args"].items():
            act = call.raw_args.get(k)
            if act is None:
                return False
            if isinstance(exp, str) and exp.startswith("^"):
                if not re.search(exp, str(act)):
                    return False
            elif str(act) != str(exp):
                return False

    return True


# ---------------------------------------------------------------------------
# Layer Loading (REQ-5)
# ---------------------------------------------------------------------------

def load_tool_config_from_file(path: str) -> Dict[str, Any]:
    """Parse YAML tool rules from gates.yaml or tool_rules.yaml."""
    if not os.path.isfile(path):
        return {}
    try:
        raw = textio.read_text(path, strict=False)
        module = bootstrap.require("ruamel.yaml")
        yaml = module.YAML(typ="safe")
        data = yaml.load(raw)
        if isinstance(data, dict):
            if "tools" in data and isinstance(data["tools"], dict):
                return data["tools"]
            return data
    except (OSError, ValueError, KeyError, AttributeError):
        pass
    return {}


def get_layers(repo_root: Optional[str] = None) -> List[Tuple[str, Dict[str, Any]]]:
    """Return ordered list of layers: repo -> global -> rule_pack -> builtin."""
    layers: List[Tuple[str, Dict[str, Any]]] = []

    if not repo_root:
        repo_root = repo.find_repo_root()

    # 1. Repository layer
    if repo_root:
        repo_tools: Dict[str, Any] = {}
        tool_rules_path = os.path.join(repo_root, ".along", "tool_rules.yaml")
        if os.path.isfile(tool_rules_path):
            repo_tools.update(load_tool_config_from_file(tool_rules_path))

        gates_path = os.path.join(repo_root, ".along", "rules", "gates.yaml")
        if os.path.isfile(gates_path):
            repo_tools.update(load_tool_config_from_file(gates_path))

        if repo_tools:
            layers.append(("repo", repo_tools))

    # 2. Global user pack layer (~/.along/user-pack/)
    user_pack_dir = os.path.expanduser("~/.along/user-pack")
    global_tools: Dict[str, Any] = {}
    if os.path.isdir(user_pack_dir):
        up_rules = os.path.join(user_pack_dir, "tool_rules.yaml")
        if os.path.isfile(up_rules):
            global_tools.update(load_tool_config_from_file(up_rules))
        up_gates = os.path.join(user_pack_dir, "gates.yaml")
        if os.path.isfile(up_gates):
            global_tools.update(load_tool_config_from_file(up_gates))
    if global_tools:
        layers.append(("global", global_tools))

    # 3. Rule packs in repository (.along/rules/*.yaml)
    if repo_root:
        rules_dir = os.path.join(repo_root, ".along", "rules")
        if os.path.isdir(rules_dir):
            pack_tools: Dict[str, Any] = {}
            for fname in os.listdir(rules_dir):
                if fname.endswith(".yaml") and fname != "gates.yaml":
                    pack_tools.update(load_tool_config_from_file(os.path.join(rules_dir, fname)))
            if pack_tools:
                layers.append(("rule_pack", pack_tools))

    # 4. Built-in defaults
    layers.append(("builtin", BUILTIN_TOOL_RULES))

    return layers


# ---------------------------------------------------------------------------
# Classification Engine (REQ-1, REQ-2, REQ-4)
# ---------------------------------------------------------------------------

def _safe_rule_class(layer_name: str, candidate_class: str, builtin_class: str) -> str:
    """Anti-tamper: untrusted repository rules cannot downgrade destructive commands or downgrade writes to read-only."""
    if layer_name in ("repo", "rule_pack") and builtin_class in ToolClass.ALL:
        if builtin_class == ToolClass.DESTRUCTIVE and candidate_class != ToolClass.DESTRUCTIVE:
            return builtin_class
        if builtin_class in (ToolClass.DESTRUCTIVE, ToolClass.EXTERNAL, ToolClass.WORKSPACE_WRITE):
            if candidate_class in (ToolClass.READ_ONLY, ToolClass.VERIFICATION):
                return builtin_class
    return candidate_class


def extract_dangerous_env_overrides(segment: str, raw_tokens: Optional[List[str]] = None) -> List[str]:
    """Identify dangerous execution-hijacking environment variables set or passed in a command segment.

    Dangerous environment variables are checked ONLY in assignment positions before the command:
    - POSIX leading assignments: VAR=val ... cmd
    - env command arguments: env [opts] VAR=val ... cmd
    - export / set commands: export VAR=val, set VAR=val
    - PowerShell env assignments: $env:VAR = val
    """
    dangerous: List[str] = []
    seg_stripped = segment.strip()

    # 1. PowerShell assignment statement: $env:VAR = val or $env:VAR='val'
    pwsh_m = re.match(r"^\$env:([A-Za-z_][A-Za-z0-9_]*)\s*=", seg_stripped, re.IGNORECASE)
    if pwsh_m:
        var_name = pwsh_m.group(1)
        if shellparse.is_dangerous_env_var(var_name):
            dangerous.append(f"$env:{var_name}")
        return dangerous

    tokens = raw_tokens if raw_tokens is not None else (shellparse._tokens(segment) or [])
    if not tokens:
        return dangerous

    # 2. POSIX leading assignments before the command: VAR=val ... cmd
    i = 0
    while i < len(tokens):
        tok = tokens[i]
        if re.match(r"^[A-Za-z_][A-Za-z0-9_]*=", tok):
            var_name = tok.split("=", 1)[0]
            if shellparse.is_dangerous_env_var(var_name):
                dangerous.append(var_name)
            i += 1
        else:
            break

    # If we reached a command name after any leading assignments:
    if i < len(tokens):
        first_cmd = tokens[i].lower()
        if first_cmd.endswith(".exe"):
            first_cmd = first_cmd[:-4]

        # 3. env command: env [-i] [-u var] VAR=val ... cmd
        if first_cmd == "env":
            j = i + 1
            while j < len(tokens):
                tok = tokens[j]
                if tok.startswith("-"):
                    if tok in ("-u", "--unset") and j + 1 < len(tokens) and not tokens[j + 1].startswith("-"):
                        j += 2
                    else:
                        j += 1
                    continue
                if re.match(r"^[A-Za-z_][A-Za-z0-9_]*=", tok):
                    var_name = tok.split("=", 1)[0]
                    if shellparse.is_dangerous_env_var(var_name):
                        dangerous.append(var_name)
                    j += 1
                else:
                    break
        # 4. export / set builtin commands: export VAR=val, set VAR=val
        elif first_cmd in ("export", "set"):
            for tok in tokens[i + 1:]:
                clean_tok = tok.strip("\"'")
                if clean_tok.startswith("-"):
                    continue
                if "=" in clean_tok:
                    var_name = clean_tok.split("=", 1)[0].strip()
                else:
                    var_name = clean_tok.strip()
                if re.match(r"^[A-Za-z_][A-Za-z0-9_]*$", var_name):
                    if shellparse.is_dangerous_env_var(var_name):
                        dangerous.append(var_name)

    return dangerous


def classify_segment(segment: str, repo_root: Optional[str] = None) -> ClassificationResult:
    """Classify an individual shell command segment."""
    dangerous_envs = extract_dangerous_env_overrides(segment)
    if dangerous_envs:
        return ClassificationResult(
            tool_class=ToolClass.DESTRUCTIVE,
            rule_desc=f"dangerous environment variable override ({', '.join(dangerous_envs)}) -> destructive",
            layer="shell",
        )

    call = normalize_segment(segment)
    if not call.tool:
        return ClassificationResult(
            tool_class=ToolClass.READ_ONLY,
            rule_desc="empty or shell control segment",
            layer="shell",
        )

    # 1. Code classifiers (built-in or trusted plugins)
    if call.tool in _CODE_CLASSIFIERS:
        try:
            clf = _CODE_CLASSIFIERS[call.tool]
            try:
                custom_res = clf(call, repo_root=repo_root)
            except TypeError:
                custom_res = clf(call)
            if custom_res in ToolClass.ALL:
                final_class = custom_res
                desc = f"classifier: {call.tool} -> {custom_res}"
                if call.write_redirect and DANGER_RANK.get(final_class, 0) < DANGER_RANK[ToolClass.WORKSPACE_WRITE]:
                    final_class = ToolClass.WORKSPACE_WRITE
                    desc += " (write redirection -> workspace-write)"
                return ClassificationResult(
                    tool_class=final_class,
                    rule_desc=desc,
                    layer="builtin",
                )
        except (RuntimeError, ValueError, TypeError, KeyError, AttributeError, OSError, IndexError) as e:
            return ClassificationResult(
                tool_class=ToolClass.UNKNOWN,
                rule_desc=f"classifier {call.tool} error: {e}",
                layer="classifier",
                unclassified_pattern=call.tool,
            )

    # 2. Declarative layers (repo -> global -> rule_pack -> builtin)
    # Determine built-in baseline to prevent repository rule privilege escalation
    builtin_class = ToolClass.UNKNOWN
    if call.tool in BUILTIN_TOOL_RULES:
        b_cfg = BUILTIN_TOOL_RULES[call.tool]
        if isinstance(b_cfg, dict):
            for r in b_cfg.get("rules", []):
                if match_rule(call, r):
                    builtin_class = r.get("class", ToolClass.UNKNOWN)
                    break
            if builtin_class == ToolClass.UNKNOWN and "default" in b_cfg:
                builtin_class = b_cfg["default"]

    layers = get_layers(repo_root=repo_root)
    highest_default: Optional[str] = None
    highest_default_layer = ""

    for layer_name, tools_dict in layers:
        if call.tool in tools_dict:
            tool_cfg = tools_dict[call.tool]
            if isinstance(tool_cfg, str):
                tool_cfg = {"default": tool_cfg}
            if isinstance(tool_cfg, dict):
                rules = tool_cfg.get("rules", [])
                for r in rules:
                    if match_rule(call, r):
                        r_class = r.get("class", ToolClass.UNKNOWN)
                        r_class = _safe_rule_class(layer_name, r_class, builtin_class)
                        final_class = r_class
                        desc = r.get("reason") or f"rule match ({r.get('match', {})})"
                        if call.write_redirect and DANGER_RANK.get(final_class, 0) < DANGER_RANK[ToolClass.WORKSPACE_WRITE]:
                            final_class = ToolClass.WORKSPACE_WRITE
                            desc += " (write redirection -> workspace-write)"
                        return ClassificationResult(
                            tool_class=final_class,
                            rule_desc=desc,
                            layer=layer_name,
                        )
                if highest_default is None and "default" in tool_cfg:
                    cand_default = tool_cfg["default"]
                    cand_default = _safe_rule_class(layer_name, cand_default, builtin_class)
                    highest_default = cand_default
                    highest_default_layer = layer_name

    if highest_default and highest_default in ToolClass.ALL:
        final_class = highest_default
        desc = f"default nature ({highest_default})"
        if call.write_redirect and DANGER_RANK.get(final_class, 0) < DANGER_RANK[ToolClass.WORKSPACE_WRITE]:
            final_class = ToolClass.WORKSPACE_WRITE
            desc += " (write redirection -> workspace-write)"
        return ClassificationResult(
            tool_class=final_class,
            rule_desc=desc,
            layer=highest_default_layer,
        )

    pat = call.tool if not call.subcommand else f"{call.tool} {call.subcommand}"
    return ClassificationResult(
        tool_class=ToolClass.UNKNOWN,
        rule_desc="unclassified tool",
        layer="",
        unclassified_pattern=pat,
    )


def classify_command(cmd: str, repo_root: Optional[str] = None) -> ClassificationResult:
    """Classify a shell command (possibly compound), taking the most dangerous class."""
    segments = shellparse.split_segments(cmd)
    if segments is None:
        return ClassificationResult(
            tool_class=ToolClass.WORKSPACE_WRITE,
            rule_desc="complex or unparsable shell syntax",
            layer="shell",
        )
    if not segments:
        return ClassificationResult(
            tool_class=ToolClass.READ_ONLY,
            rule_desc="empty command",
            layer="shell",
        )

    seg_results = [classify_segment(seg, repo_root=repo_root) for seg in segments]

    if len(seg_results) == 1:
        return seg_results[0]

    # If any segment is unknown, compound command is held as unknown for classification
    unknowns = [r for r in seg_results if r.tool_class == ToolClass.UNKNOWN]
    if unknowns:
        return ClassificationResult(
            tool_class=ToolClass.UNKNOWN,
            rule_desc=f"compound command contains unclassified segment ({unknowns[0].unclassified_pattern})",
            layer=unknowns[0].layer,
            unclassified_pattern=unknowns[0].unclassified_pattern,
            segments=seg_results,
        )

    most_dang = max(seg_results, key=lambda r: DANGER_RANK.get(r.tool_class, 0))
    return ClassificationResult(
        tool_class=most_dang.tool_class,
        rule_desc=f"compound command: most dangerous segment is '{most_dang.tool_class}' ({most_dang.rule_desc})",
        layer=most_dang.layer,
        segments=seg_results,
    )


def classify_agent_tool(tool_name: str, tool_args: Dict[str, Any], repo_root: Optional[str] = None) -> ClassificationResult:
    """Classify agent tool calls through declarative layers."""
    call = normalize_tool_call(tool_name, tool_args)
    layers = get_layers(repo_root=repo_root)

    highest_default: Optional[str] = None
    highest_default_layer = ""

    for layer_name, tools_dict in layers:
        if call.tool in tools_dict:
            tool_cfg = tools_dict[call.tool]
            if isinstance(tool_cfg, str):
                tool_cfg = {"default": tool_cfg}
            if isinstance(tool_cfg, dict):
                rules = tool_cfg.get("rules", [])
                for r in rules:
                    if match_rule(call, r):
                        return ClassificationResult(
                            tool_class=r.get("class", ToolClass.UNKNOWN),
                            rule_desc=r.get("reason") or f"rule match ({r.get('match', {})})",
                            layer=layer_name,
                        )
                if highest_default is None and "default" in tool_cfg:
                    highest_default = tool_cfg["default"]
                    highest_default_layer = layer_name

    if highest_default and highest_default in ToolClass.ALL:
        return ClassificationResult(
            tool_class=highest_default,
            rule_desc=f"default nature ({highest_default})",
            layer=highest_default_layer,
        )

    pat = call.tool if not call.subcommand else f"{call.tool} {call.subcommand}"
    return ClassificationResult(
        tool_class=ToolClass.UNKNOWN,
        rule_desc="unclassified tool",
        layer="",
        unclassified_pattern=pat,
    )


def classify_event(event: Any, repo_root: Optional[str] = None) -> ClassificationResult:
    """Classify a HookEvent by tool nature."""
    tool = getattr(event, "tool_name", "")
    args = getattr(event, "tool_args", {}) or {}
    if tool in ("run_command", "execute_command", "bash", "shell"):
        cmd = args.get("CommandLine") or args.get("command") or args.get("cmd") or ""
        return classify_command(cmd, repo_root=repo_root)
    return classify_agent_tool(tool, args, repo_root=repo_root)


# ---------------------------------------------------------------------------
# Tool Management CLI Actions (REQ-4, REQ-6)
# ---------------------------------------------------------------------------

def classify_tool(pattern: str, tool_class: str, repo_root: Optional[str] = None, is_global: bool = False) -> str:
    """Record a tool nature classification rule in repository or global user pack."""
    if tool_class not in ToolClass.VALID_CLASSES:
        raise ValueError(f"Invalid tool class: '{tool_class}'. Must be one of: {', '.join(ToolClass.VALID_CLASSES)}")

    pattern = pattern.strip()
    if not pattern:
        raise ValueError("Pattern cannot be empty.")

    parts = shlex.split(pattern)
    tool_name = parts[0].lower()
    if tool_name.endswith(".exe"):
        tool_name = tool_name[:-4]

    user_pack_dir = ""
    if is_global:
        user_pack_dir = os.path.expanduser("~/.along/user-pack")
        os.makedirs(user_pack_dir, exist_ok=True)
        if not os.path.isdir(os.path.join(user_pack_dir, ".git")):
            proc.git(["init"], cwd=user_pack_dir, check=False)
        dest_file = os.path.join(user_pack_dir, "tool_rules.yaml")
        dest_label = dest_file
    else:
        if not repo_root:
            repo_root = repo.find_repo_root()
        if not repo_root:
            raise ValueError("Not inside an Along repository. Use --global to record globally.")

        tool_rules_yaml = os.path.join(repo_root, ".along", "tool_rules.yaml")
        gates_yaml = os.path.join(repo_root, ".along", "rules", "gates.yaml")
        if os.path.isfile(tool_rules_yaml):
            dest_file = tool_rules_yaml
        elif os.path.isfile(gates_yaml):
            dest_file = gates_yaml
        else:
            dest_file = gates_yaml
            os.makedirs(os.path.dirname(dest_file), exist_ok=True)
        dest_label = repo.canonical_relpath(dest_file, repo_root)

    module = bootstrap.require("ruamel.yaml")
    yaml = module.YAML(typ="rt")
    yaml.preserve_quotes = True

    data = None
    if os.path.isfile(dest_file):
        try:
            content = textio.read_text(dest_file, strict=False)
            data = yaml.load(content)
        except (OSError, ValueError, KeyError, AttributeError):
            data = None
    if not isinstance(data, dict):
        init_str = "version: 1\n" if dest_file.endswith("gates.yaml") else "{}\n"
        data = yaml.load(init_str)
        if not isinstance(data, dict):
            data = {}

    if dest_file.endswith("gates.yaml"):
        if "tools" not in data or not isinstance(data["tools"], dict):
            data["tools"] = {}
        target_tools = data["tools"]
    else:
        if "tools" in data and isinstance(data["tools"], dict):
            target_tools = data["tools"]
        else:
            target_tools = data

    if tool_name not in target_tools or not isinstance(target_tools[tool_name], dict):
        target_tools[tool_name] = {}
    tool_entry = target_tools[tool_name]

    if len(parts) == 1:
        tool_entry["default"] = tool_class
    else:
        call = normalize_segment(pattern)
        match_dict: Dict[str, Any] = {}
        if call.subcommand:
            match_dict["subcommand"] = call.subcommand
        if call.flags:
            match_dict["flags"] = call.flags
        if call.flag_values:
            match_dict["flag_value"] = call.flag_values
        if not match_dict and len(parts) > 1:
            match_dict["subcommand"] = " ".join(parts[1:])

        new_rule = {"match": match_dict, "class": tool_class}
        if "rules" not in tool_entry or not isinstance(tool_entry["rules"], list):
            tool_entry["rules"] = []

        replaced = False
        for i, existing in enumerate(tool_entry["rules"]):
            if isinstance(existing, dict) and existing.get("match") == match_dict:
                tool_entry["rules"][i]["class"] = tool_class
                replaced = True
                break
        if not replaced:
            tool_entry["rules"].insert(0, new_rule)

    import io
    buf = io.StringIO()
    yaml.dump(data, buf)
    textio.write_text(dest_file, buf.getvalue())

    if is_global and user_pack_dir and os.path.isdir(os.path.join(user_pack_dir, ".git")):
        proc.git(["add", "tool_rules.yaml"], cwd=user_pack_dir, check=False)
        proc.git(["commit", "-m", f"classify: '{pattern}' as {tool_class}"], cwd=user_pack_dir, check=False)

    return f"Classified '{pattern}' as '{tool_class}' in {dest_label}."


def explain_command(cmd: str, repo_root: Optional[str] = None) -> str:
    """Format an explanation of how a command was classified."""
    res = classify_command(cmd, repo_root=repo_root)
    lines = [
        f"Command: {cmd}",
        f"Class:   {res.tool_class}",
    ]
    if res.layer:
        lines.append(f"Layer:   {res.layer}")
    if res.rule_desc:
        lines.append(f"Reason:  {res.rule_desc}")
    if res.segments:
        lines.append("Segments:")
        for idx, s in enumerate(res.segments, 1):
            lines.append(f"  {idx}. {s.tool_class} [{s.layer or 'rule'}]: {s.rule_desc}")
    return "\n".join(lines)


def list_tools(repo_root: Optional[str] = None) -> List[Dict[str, Any]]:
    """Gather all classified tools, defaults, rules and their layers."""
    layers = get_layers(repo_root=repo_root)
    all_tools: Dict[str, Dict[str, Any]] = {}

    for layer_name, tools_dict in reversed(layers):
        for tool_name, cfg in tools_dict.items():
            if isinstance(cfg, str):
                cfg = {"default": cfg}
            if not isinstance(cfg, dict):
                continue
            if tool_name not in all_tools:
                all_tools[tool_name] = {
                    "tool": tool_name,
                    "default": cfg.get("default", "unknown"),
                    "rules": list(cfg.get("rules", [])),
                    "layer": layer_name,
                }
            else:
                if "default" in cfg:
                    all_tools[tool_name]["default"] = cfg["default"]
                    all_tools[tool_name]["layer"] = layer_name
                if "rules" in cfg:
                    all_tools[tool_name]["rules"] = list(cfg["rules"]) + all_tools[tool_name]["rules"]

    return [all_tools[k] for k in sorted(all_tools)]
