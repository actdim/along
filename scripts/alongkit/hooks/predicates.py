#!/usr/bin/env python3
"""
alongkit.hooks.predicates - Stateful predicate handlers for declarative gates.

Implements complex condition checks requiring filesystem inspection, Git queries,
or session-level activity tracking.
"""

from __future__ import annotations

from datetime import datetime, timezone
import fnmatch
import json
import os
import re
from typing import Any, Dict, List, Optional, Tuple

from .. import attribution, frontmatter, kb, proc, repo, sanitizer, session, textio, typography
from . import shellparse
from .models import GateDecision, GateResult, HookEvent, HookEventType


GOVERNED_TYPOGRAPHY_SUFFIXES: Tuple[str, ...] = (
    ".md", ".py", ".ts", ".js", ".tsx", ".jsx",
    ".sh", ".ps1", ".bat", ".rs", ".go", ".txt",
)

SAFE_READ_TOOLS: Tuple[str, ...] = (
    "view_file", "read_file", "view_image", "grep_search", "find_by_name",
    "list_dir", "list_directory", "read_url_content", "search_web",
    "manage_task", "schedule", "send_message", "ask_question",
    "call_mcp_tool", "list_resources", "read_resource",
)


PROTECTED_PROJECTIONS: Tuple[str, ...] = (
    ".along/issues.md",
    "docs/index.md",
)

#: Managed rule packs copied by `along rules attach`; `.along/rules/gates.yaml` is not one.
RULE_PACK_PATH_RE = re.compile(r"(?:^|/)\.along/rules/(?:[^/]+/)*[^/]+\.md$", re.IGNORECASE)
#: A rule pack path as it appears inside a shell command (either slash style).
RULE_PACK_SHELL_RE = re.compile(r"\.along[/\\]+rules[/\\]+(?:[^\s/\\'\"]+[/\\]+)*[^\s/\\'\"]+\.md\b",
                                re.IGNORECASE)

DANGEROUS_CLI_PATTERNS: List[Tuple[re.Pattern, str]] = [
    # Any heredoc delimiter (<<EOF, <<'PY', <<-"END"), but not the bash here-string <<<
    # or a shift operator: a heredoc body starts on the next line. [bug--cli-safety-heredoc-gaps]
    (re.compile(r"(?<!<)<<(?!<)[-~]?[ \t]*(['\"]?)[A-Za-z_][A-Za-z0-9_]*\1[^\n]*(?:\n|$)"), "Heredoc syntax (<<EOF)"),
    # PowerShell here-strings (@'...'@, @"..."@) sent to a file
    (re.compile(r"@['\"][ \t]*\r?\n.*?\r?\n['\"]@[^\n]*(?:\|\s*(?:Set-Content|Add-Content|Out-File|tee)\b|>)",
                re.DOTALL | re.IGNORECASE), "PowerShell here-string written to a file"),
    # Inline file writers
    # Inline file writers, matched in command position (start, or after | ; & ( { or a newline)
    # so a search pattern that merely names them does not trip the gate.
    (re.compile(r"(?:^|[|;&({\n])\s*(?:Set-Content|Add-Content)\b", re.IGNORECASE),
     "Inline PowerShell file writer (Set-Content/Add-Content)"),
    (re.compile(r"\[(?:System\.)?IO\.File\]::(?:Write|Append)", re.IGNORECASE), "Inline .NET file writer ([IO.File]::Write*)"),
    (re.compile(r"(?:^|[|;&({\n])\s*New-Item\b[^\n|;]*\s-Value\b", re.IGNORECASE), "Inline file writer (New-Item -Value)"),
    (re.compile(r"(?:^|[|;&({\n])\s*(?:echo|printf|Write-Output)\b[^\n|;&]*?(?<![0-9&])>{1,2}[ \t]*"
                r"(?!&|/dev/null\b|\$null\b|NUL\b)[\"']?[\w./\\~$-]", re.IGNORECASE),
     "Inline shell file writer (echo/printf > file)"),
    (re.compile(r"(?:^|[|;&({\n])\s*(?:sed\s+(?:-[a-zA-Z]*i|--in-place)\b|perl\s+-[a-zA-Z]*i)", re.IGNORECASE),
     "In-place shell edit (sed -i / perl -i)"),
    (re.compile(r"python\d*(?:\.exe)?\s+-c\s+.*open\(.*['\"][wa]['\"].*\)", re.DOTALL | re.IGNORECASE), "Inline Python file writer"),
    (re.compile(r"python\d*(?:\.exe)?\s+-c\s+['\"].*(?:import\s+(?:alongkit|along_exec)|from\s+(?:alongkit|along_exec)|sys\.path\.insert).*", re.DOTALL | re.IGNORECASE), "Ad-hoc internal module probe via python -c [gate: cli_safety] (use Along CLI, code search tools, or a scratch/ script)"),
    (re.compile(r"git\s+reset\s+--hard", re.IGNORECASE), "Destructive unstaged Git wipe (git reset --hard)"),
    (re.compile(r"git\s+clean\s+-[a-zA-Z]*f", re.IGNORECASE), "Destructive Git clean (git clean -f)"),
    (re.compile(r"npm\s+install\s+(-g|--global)", re.IGNORECASE), "Global package manager mutation (npm -g)"),
    (re.compile(r"pip\s+install\s+(?!-e\s)(?!.*--target)(?!.*--user)[a-zA-Z0-9_\-]+", re.IGNORECASE), "Global package manager mutation (pip install)"),
    (re.compile(r"(choco|winget|apt-get|brew)\s+install", re.IGNORECASE), "Global system package installation"),
]

#: Test runs through the Along lifecycle hook. Where `.along/scripts/test.py` exists only
#: these satisfy test_before_stop [feat--test-gate-lifecycle-hook-only].
LIFECYCLE_TEST_PATTERNS: List[re.Pattern] = [
    re.compile(r"along[-_]test", re.IGNORECASE),
    re.compile(r"\balong(?:\.ps1|_exec\.py)?\s+test\b", re.IGNORECASE),
    re.compile(r"\.along[/\\]scripts[/\\]test\.py", re.IGNORECASE),
]

#: Raw test runners: they count only in repositories without a lifecycle test hook.
TEST_COMMAND_PATTERNS: List[re.Pattern] = LIFECYCLE_TEST_PATTERNS + [
    re.compile(r"\bvitest\b", re.IGNORECASE),
    re.compile(r"\bjest\b", re.IGNORECASE),
    re.compile(r"\bgo\s+test\b", re.IGNORECASE),
    re.compile(r"\b(?:pnpm|yarn)\s+(?:run\s+)?test\b", re.IGNORECASE),
    re.compile(r"\bpytest\b", re.IGNORECASE),
    re.compile(r"\bnpm\s+test\b", re.IGNORECASE),
    re.compile(r"\bcargo\s+test\b", re.IGNORECASE),
    re.compile(r"\bdotnet\s+test\b", re.IGNORECASE),
    re.compile(r"unittest\s+discover", re.IGNORECASE),
]

# Read-only shell commands are classified segment by segment in `shellparse`; the former
# prefix/substring allowlist let `ls && rm -rf src` through. See
# [bug--safe-command-prefix-bypass].


MUTATION_WHITELIST_PATTERNS: Tuple[str, ...] = (
    ".along/.session/**",
    ".along/diagnostics/**",
    ".along/SESSIONS/**",
    # Planning artifacts: an issue, risk or spike is how a plan is written down.
    ".along/ISSUES/**",
    ".along/RISKS/**",
    ".along/SPIKES/**",
    "implementation_plan.md",
    "walkthrough.md",
    "living_plan.md",
)



def _extract_target_file(event: HookEvent) -> str:
    args = event.tool_args
    return (
        args.get("TargetFile")
        or args.get("target_file")
        or args.get("path")
        or args.get("FilePath")
        or args.get("file_path")
        or ""
    )


def _extract_content(event: HookEvent) -> str:
    tool = event.tool_name
    args = event.tool_args
    if tool in ("write_to_file", "write_file", "create_file"):
        return args.get("CodeContent") or args.get("content") or ""
    elif tool in ("replace_file_content", "edit_file", "patch_file"):
        return (
            args.get("ReplacementContent")
            or args.get("replacement_content")
            or args.get("new_string")
            or args.get("content")
            or ""
        )
    return ""


def _extract_command(event: HookEvent) -> str:
    args = event.tool_args
    return args.get("CommandLine") or args.get("command") or args.get("cmd") or ""


def event_session_key(event: HookEvent) -> Optional[str]:
    """Session key of the agent session that raised `event` (payload id, else env)."""
    return session.session_key(event.runtime, event.conversation_id) or session.current_session_key()


def _matches_pattern(path: str, patterns: List[str]) -> bool:
    norm = repo.normalize_posix(path).lstrip("/")
    for pat in patterns:
        pat_norm = repo.normalize_posix(pat).lstrip("/")
        if fnmatch.fnmatch(norm, pat_norm):
            return True
        if pat_norm.endswith("/**") and (norm.startswith(pat_norm[:-3]) or norm == pat_norm[:-3]):
            return True
    return False


# ---------------------------------------------------------------------------
# Activity Trace Tracker (Session-level state)
# ---------------------------------------------------------------------------

def _issues_dir(repo_root: str) -> str:
    return os.path.join(repo.state_dir(repo_root), "ISSUES")


def get_activity_trace_path(repo_root: str, key: Optional[str] = None) -> str:
    """Per-agent-session trace when the session is known, else the shared file.

    Sessions must not see each other's edits and test runs
    [bug--activity-trace-shared-across-sessions].
    """
    diag = os.path.join(repo.state_dir(repo_root), "diagnostics")
    if key:
        return os.path.join(diag, "activity", f"{key}.json")
    return os.path.join(diag, "activity_trace.json")


def load_activity_trace(repo_root: str, key: Optional[str] = None) -> Dict[str, Any]:
    trace_path = get_activity_trace_path(repo_root, key)
    if not os.path.isfile(trace_path):
        return {"last_edit_time": None, "last_test_time": None, "edited_files": []}
    try:
        raw = textio.read_text(trace_path, strict=False)
        data = json.loads(raw)
        if isinstance(data, dict):
            return data
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        pass
    return {"last_edit_time": None, "last_test_time": None, "edited_files": []}


def save_activity_trace(repo_root: str, data: Dict[str, Any], key: Optional[str] = None) -> None:
    trace_path = get_activity_trace_path(repo_root, key)
    repo.ensure_diagnostics_dir(repo_root)
    os.makedirs(os.path.dirname(trace_path), exist_ok=True)
    try:
        textio.write_text(trace_path, json.dumps(data, indent=2) + "\n")
    except (OSError, UnicodeDecodeError):
        pass


def record_tool_activity(event: HookEvent, repo_root: str) -> None:
    """Record file modifications and test runs to track lifecycle state."""
    if not repo_root:
        return

    # Claude Code runs ExitPlanMode's PostToolUse only after the user accepted the plan.
    # See [feat--plan-approval-exit-plan-mode].
    raw_tool = str((event.raw_payload or {}).get("tool_name") or "")
    if event.event_type == HookEventType.POST_TOOL_USE and raw_tool == "ExitPlanMode":
        session.record_plan_approval(repo_root, event_session_key(event))
        return

    now_iso = datetime.now(timezone.utc).isoformat()
    key = event_session_key(event)
    trace = load_activity_trace(repo_root, key)

    # Track file edits: repository files outside .along/ (agent state is not source), plus the
    # lifecycle hooks in .along/scripts/ [feat--rule-pack-protection-gate].
    if event.tool_name in ("write_to_file", "write_file", "replace_file_content", "edit_file", "patch_file", "create_file"):
        if event.event_type != HookEventType.PRE_TOOL_USE:
            return
        rel = _repo_relative(_extract_target_file(event), repo_root)
        if rel and is_source_edit(rel):
            trace["last_edit_time"] = now_iso
            edited = trace.get("edited_files", [])
            if rel not in edited:
                edited.append(rel)
            trace["edited_files"] = edited[-200:]
            save_activity_trace(repo_root, trace, key)

    # Track test executions
    elif event.tool_name in ("run_command", "execute_command", "bash", "shell"):
        cmd = _extract_command(event)
        if not cmd or event.event_type != HookEventType.PRE_TOOL_USE:
            return
        if any(p.search(cmd) for p in LIFECYCLE_TEST_PATTERNS) or (
                not has_lifecycle_test_hook(repo_root) and any(p.search(cmd) for p in TEST_COMMAND_PATTERNS)):
            trace["last_test_time"] = now_iso
            save_activity_trace(repo_root, trace, key)
        elif any(p.search(cmd) for p in TEST_COMMAND_PATTERNS):
            trace["last_raw_test_time"] = now_iso
            save_activity_trace(repo_root, trace, key)


def _repo_relative(target: str, repo_root: str) -> Optional[str]:
    """POSIX path of `target` relative to `repo_root`, or None when outside it."""
    if not target:
        return None
    if os.path.isabs(target):
        try:
            rel = os.path.relpath(target, repo_root)
        except ValueError:
            return None
        if rel.startswith("..") or os.path.isabs(rel):
            return None
        return repo.normalize_posix(rel)
    rel = repo.normalize_posix(target)
    while rel.startswith("./"):
        rel = rel[2:]
    return rel


def is_source_edit(rel: str) -> bool:
    """True when an edit to repo-relative `rel` is a source edit for test_before_stop.

    Files under any `.along/` are agent state, except `.along/scripts/`: the repository's
    lifecycle hooks (test, build, dev, bump_version) are code.
    """
    parts = repo.normalize_posix(rel).lower().split("/")
    if ".along" not in parts:
        return True
    idx = parts.index(".along")
    return len(parts) > idx + 2 and parts[idx + 1] == "scripts"


def is_rule_pack_path(rel: str) -> bool:
    """True for a managed rule pack: `.along/rules/**/*.md` (any `.along/`, any depth)."""
    return bool(RULE_PACK_PATH_RE.search(repo.normalize_posix(rel)))


def has_lifecycle_test_hook(repo_root: str) -> bool:
    """True when the repository ships `.along/scripts/test.py`."""
    return os.path.isfile(os.path.join(repo.state_dir(repo_root), "scripts", "test.py"))


# ---------------------------------------------------------------------------
# Predicate Handlers
# ---------------------------------------------------------------------------

def check_typography(event: HookEvent, repo_root: str, **kwargs: Any) -> Optional[str]:
    """Validate content against forbidden non-ASCII typography."""
    content = _extract_content(event)
    if not content:
        return None

    target_file = _extract_target_file(event)
    if target_file:
        norm_path = repo.normalize_posix(target_file)
        segments = norm_path.split("/")
        if any(seg in sanitizer.LOCALIZED_DIRS for seg in segments):
            return None

        _, ext = os.path.splitext(norm_path)
        if ext and ext.lower() not in GOVERNED_TYPOGRAPHY_SUFFIXES:
            return None

    hits = typography.findings(content)
    if not hits:
        return None

    counts: Dict[str, int] = {}
    lines: List[int] = []
    for line_num, _col, char in hits:
        cname = typography.name_of(char)
        counts[cname] = counts.get(cname, 0) + 1
        if line_num not in lines:
            lines.append(line_num)

    detail = ", ".join(f"{c} {name}" for name, c in sorted(counts.items()))
    line_str = ", ".join(str(n) for n in lines[:6])
    if len(lines) > 6:
        line_str += ", ..."

    target_label = f" in '{target_file}'" if target_file else ""
    return (
        f"Typography Gate Violation: Detected forbidden non-ASCII typography{target_label}: "
        f"{detail} (lines: {line_str}). "
        f"Replace with standard ASCII equivalents ('-', '\"', ''', '...') before writing."
    )


def check_projection_protection(event: HookEvent, repo_root: str, **kwargs: Any) -> Optional[str]:
    """Disallow manual edits to compiled views (.along/ISSUES.md, docs/INDEX.md)."""
    target = _extract_target_file(event)
    if not target:
        return None

    norm_path = repo.normalize_posix(target).lower()
    is_protected = any(
        norm_path == p or norm_path.endswith("/" + p)
        for p in PROTECTED_PROJECTIONS
    )

    if is_protected:
        return (
            f"Projection Protection Violation: Direct manual edits to '{target}' are forbidden. "
            "The Single Source of Truth (SSOT) is atomic files in '.along/ISSUES/' or 'docs/'. "
            "Modify atomic files and run 'along issue sync' or 'along kb sync' to recompile."
        )
    return None


_RULE_PACK_REMEDIATION = (
    "Managed rule packs are Along's generic conventions and are replaced by 'along rules attach'. "
    "Put project-specific guidelines in docs/topic--<slug>.md or the 'Project specifics' section of "
    "AGENTS.md. Revert local edits with 'along rules restore'; change a pack itself in the Along "
    "repository's rules/ templates."
)


def check_rule_pack_protection(event: HookEvent, repo_root: str, **kwargs: Any) -> Optional[str]:
    """Deny agent writes to managed rule packs (`.along/rules/**/*.md`).

    File tools are matched on their target; shell commands on any non-read-only segment that
    names a rule pack, except `along rules ...` (attach / restore write them on purpose).
    """
    if event.tool_name in ("run_command", "execute_command", "bash", "shell"):
        cmd = _extract_command(event)
        if not cmd or not RULE_PACK_SHELL_RE.search(cmd):
            return None
        segments = shellparse.split_segments(cmd)
        if segments is None:
            segments = [cmd]
        for seg in segments:
            match = RULE_PACK_SHELL_RE.search(seg)
            if not match:
                continue
            sub = shellparse.along_subcommand(seg)
            if sub is not None and (sub == "rules" or sub.startswith("rules ")):
                continue
            if shellparse.is_read_only_command(seg):
                continue
            return (
                f"Rule Pack Protection Violation [gate: rule-pack-protection]: the command writes to "
                f"'{match.group(0)}'. {_RULE_PACK_REMEDIATION}"
            )
        return None

    target = _extract_target_file(event)
    rel = _repo_relative(target, repo_root) if target else None
    if not rel or not is_rule_pack_path(rel):
        return None
    return (
        f"Rule Pack Protection Violation [gate: rule-pack-protection]: '{rel}' is a managed Along "
        f"rule pack. {_RULE_PACK_REMEDIATION}"
    )


def check_doc_manual_lock(event: HookEvent, repo_root: str, **kwargs: Any) -> Optional[str]:
    """Disallows modifying documentation marked with write_policy: manual without explicit intent."""
    target = _extract_target_file(event)
    if not target:
        return None

    if os.path.isabs(target):
        try:
            rel_target = os.path.relpath(target, repo_root)
            if rel_target.startswith("..") or os.path.isabs(rel_target):
                return None
        except ValueError:
            return None
    else:
        rel_target = target

    norm_rel = repo.normalize_posix(rel_target).lstrip("/")
    if not (norm_rel.startswith("docs/") or norm_rel.startswith(".along/")):
        return None

    abs_target = os.path.normpath(os.path.join(repo_root, rel_target))
    if not os.path.isfile(abs_target):
        return None

    try:
        content = textio.read_text(abs_target, strict=False)
        fm, _, _ = frontmatter.try_parse(content)
        if not fm or not kb.is_manual_write_policy(fm):
            return None
    except (OSError, UnicodeDecodeError, ValueError):
        return None

    # Target has write_policy: manual (or locked: true).
    # Check if there is an active session or in-progress issue specifically targeting this doc.
    slug = fm.get("slug") or os.path.splitext(os.path.basename(rel_target))[0].replace("topic--", "")
    active_slug = session.get_active_session_slug(repo_root, event_session_key(event))
    if active_slug and (active_slug == slug or active_slug == f"docs--{slug}" or active_slug == f"topic--{slug}"):
        return None

    issues_dir = _issues_dir(repo_root)
    if os.path.isdir(issues_dir):
        doc_issue_cand = os.path.join(issues_dir, f"docs--{slug}.md")
        if os.path.isfile(doc_issue_cand):
            try:
                i_raw = textio.read_text(doc_issue_cand, strict=False)
                i_fm, _, _ = frontmatter.try_parse(i_raw)
                if i_fm and i_fm.get("status") == "in-progress":
                    return None
            except (OSError, UnicodeDecodeError, ValueError):
                pass

    return (
        f"Manual Document Lock Violation [gate: doc-manual-lock]: "
        f"Document '{rel_target}' is governed by 'write_policy: manual'. "
        f"Automated modifications during code refactoring or blast radius sync are prohibited. "
        f"To edit this file, activate an explicit documentation issue (.along/ISSUES/docs--{slug}.md) "
        f"or modify the frontmatter write_policy."
    )


def check_cli_safety(event: HookEvent, repo_root: str, **kwargs: Any) -> Optional[str]:
    """Check command line for dangerous shell patterns and destructive commands."""
    cmd = _extract_command(event)
    if not cmd:
        return None

    for pattern, label in DANGEROUS_CLI_PATTERNS:
        if pattern.search(cmd):
            return (
                f"CLI Safety Gate Violation: {label} detected in command: {cmd.strip()[:100]}. "
                "Use native file editing tools and Along lifecycle scripts instead."
            )
    return None


_CONFLICT_MARKER_LINE = re.compile(r"^(<{7} |={7}$|>{7} |<{7}$|>{7}$)")
_COMMIT_ALL_FLAG = re.compile(r"(?:^|\s)(?:-[a-zA-Z]*a[a-zA-Z]*|--all)(?:\s|$)")


def find_added_conflict_markers(diff_text: str) -> List[str]:
    """Return `path:marker` for every conflict marker a unified diff adds."""
    hits: List[str] = []
    current = ""
    for line in diff_text.splitlines():
        if line.startswith("+++ "):
            current = line[4:].strip()
            if current.startswith("b/"):
                current = current[2:]
            continue
        if line.startswith("+") and not line.startswith("+++"):
            added = line[1:]
            if _CONFLICT_MARKER_LINE.match(added):
                hits.append(f"{current}: {added.strip()[:20]}")
    return hits


def check_staged_conflict_markers(event: HookEvent, repo_root: str, **kwargs: Any) -> Optional[str]:
    """Block `git commit` when the content it would record adds conflict markers.

    Inspects `git diff --cached` (or `git diff HEAD` when the command commits all tracked
    changes with `-a` / `--all`), not the command line. See
    [bug--conflict-marker-gate-wrong-target].
    """
    cmd = _extract_command(event).strip()
    if not repo_root or not re.match(r"^git\s+commit\b", cmd):
        return None
    commit_all = bool(_COMMIT_ALL_FLAG.search(cmd[len("git commit"):]))
    diff_cmd = ["git", "diff", "HEAD" if commit_all else "--cached", "-U0", "--no-color", "--no-ext-diff"]
    result = proc.run_capture(diff_cmd, cwd=repo_root, trip_on_anomaly=False)
    if result.returncode != 0:
        return None
    hits = find_added_conflict_markers(result.stdout or "")
    if not hits:
        return None
    shown = "; ".join(hits[:5]) + (" ..." if len(hits) > 5 else "")
    return (
        "Git commit rejected by [gate: commit-no-conflict-markers]: unresolved merge conflict "
        f"markers in staged content ({shown}). Resolve the conflicts and stage the files again."
    )


_GIT_COMMIT_RE = re.compile(r"\bgit\s+(?:-C\s+\S+\s+)?commit\b")
_COMMIT_MSG_FILE_RE = re.compile(r"(?:\s-F\s*|\s--file[=\s]\s*)(['\"]?)([^\s'\"]+)\1")


def check_ai_coauthor(event: HookEvent, repo_root: str, **kwargs: Any) -> Optional[str]:
    """Block `git commit` whose message carries an AI `Co-Authored-By:` trailer.

    Looks at the command line (`-m`, heredoc) and at a message file passed with
    `-F` / `--file`. Human co-authors pass. See [feat--suppress-ai-coauthor-attribution].
    """
    cmd = _extract_command(event)
    if not _GIT_COMMIT_RE.search(cmd) or attribution.allow_ai_coauthor(repo_root):
        return None
    trailer = attribution.find_ai_coauthor(cmd)
    if trailer is None:
        file_match = _COMMIT_MSG_FILE_RE.search(cmd)
        if file_match and file_match.group(2) != "-":
            msg_path = file_match.group(2)
            if not os.path.isabs(msg_path) and repo_root:
                msg_path = os.path.join(repo_root, msg_path)
            if os.path.isfile(msg_path):
                try:
                    trailer = attribution.find_ai_coauthor(textio.read_text(msg_path, strict=False))
                except OSError:
                    trailer = None
    if trailer is None:
        return None
    return (
        f"Git commit rejected by [gate: commit-no-ai-coauthor]: '{trailer[:80]}' names an AI "
        "agent as co-author. Remove the trailer; GitHub would list the vendor as a contributor."
    )


def check_mutation_authorization(event: HookEvent, repo_root: str, **kwargs: Any) -> Optional[Any]:
    """Intercept file mutations and shell commands outside execution phase without plan approval."""
    if event.event_type != HookEventType.PRE_TOOL_USE:
        return None

    tool = event.tool_name
    if tool in SAFE_READ_TOOLS:
        return None

    # Check shell commands
    if tool in ("run_command", "execute_command", "bash", "shell"):
        cmd = _extract_command(event).strip()
        if not cmd:
            return None
        if shellparse.is_read_only_command(cmd) or shellparse.is_along_state_command(cmd):
            return None

    # Check file modification tools
    elif tool in ("write_to_file", "write_file", "replace_file_content", "edit_file", "patch_file", "create_file"):
        target = _extract_target_file(event)
        if not target or not repo_root:
            return None

        # Check if outside repository root (e.g. brain artifacts, temporary directories)
        if os.path.isabs(target):
            try:
                rel_target = os.path.relpath(target, repo_root)
                if rel_target.startswith("..") or os.path.isabs(rel_target):
                    return None
            except ValueError:
                return None
        else:
            rel_target = target

        # Check whitelisted session/planning/diagnostics paths
        if _matches_pattern(rel_target, list(MUTATION_WHITELIST_PATTERNS)):
            return None
    else:
        # Other / unknown tools: do not block
        return None

    # Non-whitelisted file mutation or shell command. Verify this session's phase and approval.
    key = event_session_key(event)
    slug, how = session.resolve_active_session(repo_root, key)
    approved = session.is_plan_approved(repo_root, slug=slug, key=key)
    phase = session.get_session_phase(repo_root, slug=slug, key=key)

    if approved and (phase == "execution" or not slug):
        return None

    # Violation: inquiry phase or unapproved plan
    target = f"issue '{slug}'" if slug else "this session"
    if how == "ambiguous":
        target = "this session (several in-progress issues, none bound to it)"
    reason = (
        f"Inquiry Read-Only Invariance [gate: require-plan-approval]: "
        f"No approved plan for {target} (phase: '{phase}', plan_approved: {str(approved).lower()}). "
        "Present the implementation plan to the user first. Approval is recorded when the user "
        "accepts it (Claude Code: ExitPlanMode), or by 'along plan approve' after the user's explicit yes. "
        "Use 'along start <slug>' to bind this session to an issue."
    )

    if event.runtime == "antigravity":
        return GateResult(
            decision=GateDecision.ASK,
            reason=reason,
            gate_name="require_plan_approval",
        )
    return reason


def check_active_issue(event: HookEvent, repo_root: str, exclude_paths: Optional[List[str]] = None, **kwargs: Any) -> Optional[str]:
    """Enforce that code modifications occur under an in-progress issue bound to the session."""
    target = _extract_target_file(event)
    if not target or not repo_root:
        return None

    excludes = exclude_paths or [
        ".along/ISSUES/**",
        ".along/.session/**",
        ".along/diagnostics/**",
        ".along/SESSIONS/**",
        ".along/DECISIONS/**",
        ".along/MILESTONES/**",
        ".along/RISKS/**",
        ".along/SPIKES/**",
        ".along/CHECKLISTS/**",
        ".along/*.md",
        ".along/HISTORY.md",
        "docs/**",
        "CHANGELOG.md",
    ]

    if os.path.isabs(target):
        try:
            rel_target = os.path.relpath(target, repo_root)
            if rel_target.startswith("..") or os.path.isabs(rel_target):
                # Outside repository root (e.g. brain artifacts, temp files)
                return None
        except ValueError:
            # Different drive on Windows: target is outside repository root
            return None
    else:
        rel_target = target

    if _matches_pattern(rel_target, excludes):
        return None

    # A file of a subproject with its own .along/ is anchored by that subproject's issue
    # (subproject_boundary decides whether a root issue may cover it).
    key = event_session_key(event)
    ctx = subproject_context(repo_root, repo.normalize_posix(rel_target))
    if ctx and _subproject_issue_ok(ctx, repo_root, key):
        return None

    issues_dir = _issues_dir(repo_root)
    if not os.path.isdir(issues_dir):
        return None

    # Verify this session's bound issue first
    active_slug, how = session.resolve_active_session(repo_root, key)
    if how == "elsewhere":
        bctx, bslug = session.resolve_bound(repo_root, key)
        where = repo.normalize_posix(os.path.relpath(bctx, repo_root)) if bctx else "?"
        return (
            f"Mandatory Issue Anchoring Violation [gate: require-active-issue]: this session is bound to "
            f"'{bslug}' in '{where}/.along/', and '{rel_target}' is outside that subproject. Bind an issue "
            f"of this .along/ (or an umbrella issue) with 'along start <slug>'."
        )
    if how == "ambiguous":
        return (
            f"Mandatory Issue Anchoring Violation [gate: require-active-issue]: "
            f"Several issues are in progress and none is bound to this agent session. "
            f"Run 'along start <slug>' to bind it before modifying '{rel_target}'."
        )
    if active_slug:
        has_active = False
        try:
            for prefix in ("feat--", "bug--", "debt--", "task--", "docs--", ""):
                candidate = os.path.join(issues_dir, f"{prefix}{active_slug}.md")
                if os.path.isfile(candidate):
                    content = textio.read_text(candidate, strict=False)
                    mapping, _body, _err = frontmatter.try_parse(content)
                    if mapping and mapping.get("status") == "in-progress":
                        has_active = True
                        break
        except (OSError, UnicodeDecodeError, ValueError):
            pass

        if not has_active:
            return (
                f"Mandatory Issue Anchoring Violation [gate: require-active-issue]: "
                f"Active session '{active_slug}' is not bound to an in-progress issue in .along/ISSUES/. "
                f"Run 'along start {active_slug}' before modifying repository code."
            )
        return None

    # If no session-bound issue, check if any issue is in-progress
    has_active = False
    try:
        with os.scandir(issues_dir) as entries:
            for entry in entries:
                if entry.is_file() and entry.name.endswith(".md"):
                    content = textio.read_text(entry.path, strict=False)
                    mapping, _body, _err = frontmatter.try_parse(content)
                    if mapping and mapping.get("status") == "in-progress":
                        has_active = True
                        break
    except (OSError, UnicodeDecodeError, ValueError):
        pass

    # Runtimes without a session id keep the repository-level inquiry lock.
    gst = session.load_global_session_state(repo_root) if not key else None
    if gst and gst.get("phase") == "inquiry" and not gst.get("plan_approved", False):
        return (
            f"Mandatory Issue Anchoring Violation [gate: require-active-issue]: "
            f"Cannot modify repository file '{rel_target}'. Current session is locked in inquiry mode. "
            f"Run 'along start <slug>' to activate the issue before writing code."
        )

    if not has_active:
        return (
            f"Mandatory Issue Anchoring Violation [gate: require-active-issue]: "
            f"Cannot modify repository file '{rel_target}' without an active in-progress issue. "
            f"Identify or create an issue in .along/ISSUES/ with 'status: in-progress' before writing code."
        )
    return None


def check_team_step_active(event: HookEvent, repo_root: str, **kwargs: Any) -> Optional[str]:
    """A role-based (along-team) blackboard allows source edits only inside an in-progress step.

    See [feat--along-team-step-enforcement].
    """
    if not repo_root or event.event_type != HookEventType.PRE_TOOL_USE:
        return None
    rel = _repo_relative(_extract_target_file(event), repo_root)
    if not rel or "/.along/" in f"/{rel.lower()}":
        return None
    ctx, slug = session.resolve_bound(repo_root, event_session_key(event))
    st = session.load_state(ctx, slug) if slug else None
    if not session.is_role_based(st):
        return None
    if any(s.get("status") == "in-progress" for s in st.get("steps", [])):
        return None
    nxt = next((s for s in st.get("steps", []) if s.get("status") in ("pending", "failed")), None)
    hint = (f"'along scratch update {slug} --step {nxt.get('step')} --step-status in-progress'"
            if nxt else f"'along scratch update {slug} --step <N> --step-status in-progress'")
    return (
        f"along-team Step Violation [gate: team-step-active]: '{slug}' runs the along-team step loop, "
        f"but no step is in progress, so '{rel}' may not be edited. Start the step first with {hint}, "
        f"or record a single-agent fallback: 'along scratch fallback {slug} --reason \"...\"'."
    )


def check_team_reviews_before_stop(event: HookEvent, repo_root: str, **kwargs: Any) -> Optional[str]:
    """Every passed along-team step has its reviews/step-N.md before the turn ends."""
    if not repo_root:
        return None
    ctx, slug = session.resolve_bound(repo_root, event_session_key(event))
    if not slug:
        return None
    missing = session.missing_reviews(ctx, slug)
    if not missing:
        return None
    files = ", ".join(f"reviews/step-{n}.md" for n in missing)
    return (
        f"Turn Completion Rejected [gate: team-reviews-before-stop]: along-team steps {missing} of '{slug}' "
        f"are passed without a review record ({files} in .along/.session/{slug}/). Write the Reviewer's "
        "verdict there, or set the step back to in-progress."
    )


def check_test_before_stop(event: HookEvent, repo_root: str, **kwargs: Any) -> Optional[str]:
    """Ensure automated tests were run after code modifications before stopping turn."""
    if not repo_root:
        return None

    trace = load_activity_trace(repo_root, event_session_key(event))
    edit_time = trace.get("last_edit_time")
    test_time = trace.get("last_test_time")

    if edit_time is not None:
        if test_time is None or test_time < edit_time:
            raw = trace.get("last_raw_test_time")
            hint = ""
            if raw and raw >= edit_time:
                hint = (" A raw test runner ran after the edit, but this repository has a lifecycle "
                        "test hook, and only it counts.")
            return (
                "Turn Completion Rejected [gate: test-before-stop]: Source files were modified in this session, "
                f"but automated tests have not been executed afterward.{hint} "
                "Run tests via 'along test' or 'python .along/scripts/test.py' before completing."
            )
    return None


def check_wrap_before_stop(event: HookEvent, repo_root: str, **kwargs: Any) -> Optional[str]:
    """Ensure session log is recorded if an issue was marked done."""
    if not repo_root:
        return None

    done_dir = os.path.join(_issues_dir(repo_root), "done")
    if not os.path.isdir(done_dir):
        return None

    today_prefix = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    recent_done = False
    try:
        for entry in os.scandir(done_dir):
            if entry.is_file() and entry.name.endswith(".md"):
                content = textio.read_text(entry.path, strict=False)
                parsed, _body, _err = frontmatter.try_parse(content)
                if parsed:
                    completed = str(parsed.get("completed", ""))
                    if completed.startswith(today_prefix):
                        recent_done = True
                        break
    except (OSError, UnicodeDecodeError, ValueError):
        pass

    if recent_done:
        # Verify a session log exists for today
        sessions_dir = os.path.join(repo.state_dir(repo_root), "SESSIONS")
        has_session_today = False
        if os.path.isdir(sessions_dir):
            for root, _dirs, files in os.walk(sessions_dir):
                for f in files:
                    if f.startswith(today_prefix) and f.endswith(".md"):
                        has_session_today = True
                        break
                if has_session_today:
                    break

        if not has_session_today:
            return (
                f"Turn Completion Rejected [gate: wrap-before-stop]: Issue completed today ({today_prefix}), "
                "but no matching session log was found in .along/SESSIONS/. "
                "Execute '/along-wrap' or write the session log before ending."
            )
    return None


def check_projection_sync_before_stop(event: HookEvent, repo_root: str, **kwargs: Any) -> Optional[str]:
    """Ensure projections (ISSUES.md, docs/INDEX.md) are updated when atomic sources change."""
    if not repo_root:
        return None

    issues_proj = os.path.join(repo.state_dir(repo_root), "ISSUES.md")
    issues_dir = _issues_dir(repo_root)

    if os.path.isfile(issues_proj) and os.path.isdir(issues_dir):
        proj_mtime = os.path.getmtime(issues_proj)
        for root, _dirs, files in os.walk(issues_dir):
            for f in files:
                if f.endswith(".md"):
                    p = os.path.join(root, f)
                    if os.path.getmtime(p) > proj_mtime + 2.0:  # Allow 2s tolerance
                        return (
                            "Turn Completion Rejected [gate: projection-sync-before-stop]: "
                            "Atomic issues were modified after the latest .along/ISSUES.md projection. "
                            "Run 'along issue sync' to recompile before ending."
                        )

    return None


_ENTITY_DIRS = ("ISSUES/", "MILESTONES/", "RISKS/", "SPIKES/", "CHECKLISTS/", "DECISIONS/", "SESSIONS/")


def _entity_files_changed(repo_root: str) -> bool:
    """True when git reports a changed entity file under the state dir (or git cannot say)."""
    sdir = repo.state_dir(repo_root)
    rel = repo.normalize_posix(os.path.relpath(sdir, repo_root))
    result = proc.run_capture(["git", "status", "--porcelain", "-uall", "--", rel], cwd=repo_root,
                              check=False, trip_on_anomaly=False)
    if not result.ok:
        return True
    prefix = rel.rstrip("/") + "/"
    for line in result.stdout.splitlines():
        path = line[3:].split(" -> ")[-1].strip().strip('"')
        if path.startswith(prefix) and path[len(prefix):].startswith(_ENTITY_DIRS):
            return True
    return False


def check_entity_reference_integrity(event: HookEvent, repo_root: str, **kwargs: Any) -> Optional[str]:
    """Entity graph stays valid once entity files changed: no dangling references or enum violations."""
    if not repo_root or not os.path.isdir(repo.state_dir(repo_root)):
        return None
    if not _entity_files_changed(repo_root):
        return None
    from .. import gates
    problems = gates.entity_integrity_errors(repo_root)
    if not problems:
        return None
    shown = "; ".join(problems[:5]) + (f"; ... {len(problems) - 5} more" if len(problems) > 5 else "")
    return (
        "Turn Completion Rejected [gate: entity-reference-integrity]: "
        f"{len(problems)} entity graph problem(s): {shown}. "
        "Fix them (see `along doctor --entities`); rename or retire referenced entities with "
        "`along issue rename` / `along issue supersede` instead of deleting them."
    )


def subproject_context(repo_root: str, rel_target: str) -> Optional[str]:
    """Directory of the nearest `.along/` below `repo_root` that owns `rel_target`, or None."""
    abs_target = os.path.normpath(os.path.join(repo_root, rel_target))
    sdir = repo.find_state_dir(os.path.dirname(abs_target))
    if not sdir:
        return None
    ctx = os.path.dirname(os.path.abspath(sdir))
    root = os.path.abspath(repo_root)
    if os.path.normcase(ctx) == os.path.normcase(root):
        return None
    try:
        inside = not os.path.relpath(ctx, root).startswith("..")
    except ValueError:
        return None
    return ctx if inside else None


def _issue_frontmatter(context_root: str, slug: str, include_done: bool = False) -> Optional[Dict[str, Any]]:
    issues_dir = _issues_dir(context_root)
    dirs = [issues_dir] + ([os.path.join(issues_dir, "done")] if include_done else [])
    for d in dirs:
        for prefix in ("feat--", "bug--", "debt--", "task--", "docs--", ""):
            path = os.path.join(d, f"{prefix}{slug}.md")
            if os.path.isfile(path):
                try:
                    mapping, _b, _e = frontmatter.try_parse(textio.read_text(path, strict=False))
                except (OSError, UnicodeDecodeError, ValueError):
                    return None
                return mapping or None
    return None


def _subproject_issue_ok(context_root: str, repo_root: str, key: Optional[str]) -> bool:
    """The session works on an issue of `context_root`, or on a root umbrella with a child there."""
    slug, _how = session.resolve_active_session(context_root, key)
    if slug:
        fm = _issue_frontmatter(context_root, slug)
        if fm and fm.get("status") == "in-progress":
            return True
    root_slug = session.get_active_session_slug(repo_root, key)
    root_fm = _issue_frontmatter(repo_root, root_slug) if root_slug else None
    if not root_fm:
        return False
    root_key = f"{root_fm.get('type', '')}--{root_slug}"
    issues_dir = _issues_dir(context_root)
    if not os.path.isdir(issues_dir):
        return False
    for name in os.listdir(issues_dir):
        if name.endswith(".md"):
            try:
                child, _b, _e = frontmatter.try_parse(textio.read_text(os.path.join(issues_dir, name), strict=False))
            except (OSError, UnicodeDecodeError, ValueError):
                continue
            if child and str(child.get("parent") or "") in (root_key, root_slug):
                return True
    return False


def check_subproject_boundary(event: HookEvent, repo_root: str, **kwargs: Any) -> Optional[str]:
    """Enforce subproject localization [gate: subproject-boundary].

    1. A source edit inside a subproject that has its own `.along/` needs an issue of that
       subproject bound to the session, or a root umbrella issue with a child there
       (`parent: <root key>`). Decided from the edited path, not the process cwd.
       See [feat--subproject-boundary-by-active-issue].
    2. Entities are not written to the root `.along/` while working inside a subproject.
    """
    target = _extract_target_file(event)
    if not target or not repo_root:
        return None

    rel = _repo_relative(target, repo_root)
    if rel and not rel.lower().startswith(".along/"):
        ctx = subproject_context(repo_root, rel)
        if ctx:
            sub_rel = repo.normalize_posix(os.path.relpath(os.path.join(repo_root, rel), ctx))
            if not sub_rel.lower().startswith(".along/") and \
                    not _subproject_issue_ok(ctx, repo_root, event_session_key(event)):
                sub = repo.normalize_posix(os.path.relpath(ctx, repo_root))
                return (
                    f"Subproject Boundary Violation [gate: subproject-boundary]: '{rel}' belongs to subproject "
                    f"'{sub}', which has its own .along/. Work on it under an issue of '{sub}/.along/' "
                    f"('along start <slug>' from '{sub}'), or give a child issue there "
                    f"'parent: <root issue key>' of the umbrella issue this session is bound to."
                )

    if os.path.isabs(target):
        try:
            rel = os.path.relpath(target, repo_root)
            if rel.startswith(".."):
                return None
            rel_path = repo.normalize_posix(rel)
        except ValueError:
            return None
    else:
        rel_path = repo.normalize_posix(target)

    # If writing directly to root .along/ but the path indicates working inside a subproject
    if rel_path.startswith(".along/"):
        cwd = repo.normalize_posix(os.getcwd())
        root_norm = repo.normalize_posix(repo_root)
        if cwd != root_norm and cwd.startswith(root_norm + "/"):
            subpath = cwd[len(root_norm) + 1:]
            # Check if subproject has manifest
            sub_along = os.path.join(cwd, ".along")
            sub_pkg = os.path.join(cwd, "package.json")
            if os.path.isdir(sub_along) or os.path.isfile(sub_pkg):
                return (
                    f"Subproject Boundary Violation [gate: subproject-boundary]: "
                    f"Cannot write to root '{rel_path}' while working inside subproject '{subpath}'. "
                    f"Entities must be created in nearest '{subpath}/.along/'."
                )
    return None


def check_workspace_containment(event: HookEvent, repo_root: str, options: Optional[Dict[str, Any]] = None,
                                **kwargs: Any) -> Optional[Any]:
    """Keep file, search and shell-cwd paths inside the workspace scope [gate: workspace-containment].

    Writes outside scope are denied; reads outside scope ask interactively and are denied in
    autonomous runs. Policy details: alongkit.hooks.containment.
    """
    if not repo_root:
        return None
    from . import containment
    policy = containment.build_policy(repo_root, options, conversation_id=event.conversation_id,
                                      session_key=event_session_key(event))
    base = event.workspace_root or repo_root
    bad = containment.violations(event, policy, base=base)
    if not bad:
        return None
    access, path = bad[0]
    what = {"write": "Write", "read": "Read", "cwd": "Shell working directory"}[access]
    hint = ("declare it in allowed_roots (.along/rules/gates.yaml, issue frontmatter, "
            "or 'along start <slug> --allow-root <path>')")
    if access == "write":
        hint = ("writes are limited to the workspace (and its write_scope), the temp dir and "
                "runtime artifact dirs")
    reason = (f"Workspace containment violation [gate: workspace-containment]: {what} outside the "
              f"allowed scope: '{path}'. To allow it, {hint}.")
    if policy.is_secret(path):
        reason = (f"Workspace containment violation [gate: workspace-containment]: '{path}' is a "
                  f"credential store and is never accessible to agents.")
    if access == "write" or policy.is_secret(path) or containment.is_autonomous(event, policy):
        return GateResult(decision=GateDecision.DENY, reason=reason, exit_code=2)
    return GateResult(decision=GateDecision.ASK, reason=reason, exit_code=2)


def _is_reparse_or_link(path: str) -> bool:
    """Check if path is a symlink or Windows directory junction."""
    if os.path.islink(path):
        return True
    try:
        attributes = os.lstat(path).st_file_attributes
    except (AttributeError, OSError):
        return False
    return bool(attributes & 0x400)


def check_worktree_env_readiness(event: HookEvent, repo_root: str, **kwargs: Any) -> Optional[str]:
    """Verify that if operating inside a Git worktree, environment dependencies are linked."""
    target = _extract_target_file(event)
    cwd = os.getcwd()
    check_dir = None

    if target and os.path.isabs(target):
        parent_dir = os.path.dirname(target)
        if os.path.isfile(os.path.join(parent_dir, ".git")):
            check_dir = parent_dir
    if not check_dir and os.path.isfile(os.path.join(cwd, ".git")):
        check_dir = cwd

    if not check_dir:
        return None

    git_file = os.path.join(check_dir, ".git")
    try:
        content = textio.read_text(git_file).strip()
        if not content.startswith("gitdir:"):
            return None
    except (OSError, UnicodeDecodeError):
        return None

    if repo_root and os.path.abspath(repo_root) != os.path.abspath(check_dir):
        for dep in ("node_modules", ".venv"):
            root_dep = os.path.join(repo_root, dep)
            if os.path.isdir(root_dep):
                worktree_dep = os.path.join(check_dir, dep)
                if not os.path.exists(worktree_dep) and not _is_reparse_or_link(worktree_dep):
                    return (
                        f"Worktree Environment Readiness Violation [gate: worktree-env-readiness]: "
                        f"Primary repository contains '{dep}', but it is not linked in worktree '{check_dir}'. "
                        f"Run 'along worktree create' or link dependencies before modifying files."
                    )

    manifest_file = os.path.join(check_dir, ".along-worktree.json")
    if os.path.isfile(manifest_file):
        try:
            data = json.loads(textio.read_text(manifest_file))
            for rel_dir in data.get("linked_dirs", []):
                full_path = os.path.join(check_dir, rel_dir)
                if not (os.path.exists(full_path) or _is_reparse_or_link(full_path)):
                    return (
                        f"Worktree Environment Readiness Violation [gate: worktree-env-readiness]: "
                        f"Required linked directory '{rel_dir}' is missing or broken in '{check_dir}'."
                    )
        except (OSError, json.JSONDecodeError):
            pass

    return None


def check_circuit_breaker(event: HookEvent, repo_root: str, **kwargs: Any) -> Optional[str]:
    """Block execution if the systemic anomaly circuit breaker is tripped."""
    if not repo_root:
        return None

    # Recovery and status commands must never be blocked by the breaker
    cmd = _extract_command(event)
    if cmd and re.search(r"\b(along|along_exec\.py)\s+circuit\b", cmd):
        return None

    from .. import circuit
    state, anomaly = circuit.get_breaker_state(repo_root)
    if state == circuit.CircuitState.TRIPPED:
        sig = anomaly.signature if anomaly else "Environment failure"
        cls_name = anomaly.anomaly_class.value if anomaly else "Systemic Anomaly"
        return (
            f"Circuit Breaker Violation [gate: circuit-breaker]: Tool execution is blocked because "
            f"the systemic anomaly circuit breaker is TRIPPED ({cls_name}: {sig}). "
            "Human remediation is required. Run 'along circuit status' or 'along circuit reset' to recover."
        )
    return None


def check_fast_retrieval(event: HookEvent, repo_root: str, **kwargs: Any) -> Optional[str]:
    """
    Block manual directory searches (grep_search, find_by_name) targeting docs/ or .along/ directories.
    Directs agents to use 'along kb-search <query>' for fast, sub-100ms indexed retrieval.
    """
    tool = (event.tool_name or "").lower()
    args = event.tool_args or {}

    target_path = ""
    if tool in ("grep_search", "grep"):
        target_path = (
            args.get("SearchPath")
            or args.get("search_path")
            or args.get("path")
            or ""
        )
        if target_path:
            # If target_path points to an existing regular file, allow targeted inspection
            norm_abs = target_path
            if repo_root and not os.path.isabs(norm_abs):
                norm_abs = os.path.join(repo_root, norm_abs)
            if os.path.isfile(norm_abs):
                return None

    elif tool in ("find_by_name", "find_files", "file_search"):
        target_path = (
            args.get("SearchDirectory")
            or args.get("search_directory")
            or args.get("directory")
            or args.get("path")
            or ""
        )

    if not target_path:
        return None

    norm = repo.normalize_posix(target_path).strip().lower()
    if repo_root:
        root_norm = repo.normalize_posix(repo_root).rstrip("/").lower()
        if norm.startswith(root_norm + "/"):
            norm = norm[len(root_norm) + 1:]
        elif norm == root_norm:
            # Whole repo search - permitted
            return None

    while norm.startswith("./"):
        norm = norm[2:]
    norm = norm.lstrip("/")

    if (
        norm == "docs" or norm.startswith("docs/")
        or norm == ".along" or norm.startswith(".along/")
    ):
        return (
            f"Manual Search Rejected [gate: fast-retrieval]: Manual directory search across '{target_path}' "
            "is forbidden to prevent latency and LLM token exhaustion. "
            "Execute 'along kb-search \"<query>\"' instead for sub-100ms indexed retrieval."
        )

    return None


