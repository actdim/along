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
import sys
from typing import Any, Dict, List, Optional, Tuple

from .. import attribution, entities, frontmatter, kb, proc, repo, sanitizer, session, testruns, textio, typography
from . import shellparse, shellwrite
from .models import GateDecision, GateResult, HookEvent, HookEventType


GOVERNED_TYPOGRAPHY_SUFFIXES: Tuple[str, ...] = (
    ".md", ".py", ".ts", ".js", ".tsx", ".jsx",
    ".sh", ".ps1", ".bat", ".rs", ".go", ".txt",
)

SAFE_READ_TOOLS: Tuple[str, ...] = (
    "view_file", "read_file", "view_image", "grep_search", "find_by_name",
    "list_dir", "list_directory", "read_url_content", "search_web",
    "manage_task", "schedule", "send_message", "ask_question",
    "list_resources", "read_resource",
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
    # Quote-aware: a `>` inside quotes, stderr / null redirects and pipes are no file write
    # [bug--cli-safety-redirect-false-positive].
    (shellwrite.InlineEchoWriter(), "Inline shell file writer (echo/printf > file)"),
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

#: Edits the execution trace leaves out: the blackboard itself and machine-local diagnostics.
TRACE_EXCLUDED_PATTERNS: Tuple[str, ...] = (
    ".along/.session/**",
    ".along/diagnostics/**",
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


def _matches_in_context(rel_target: str, repo_root: str, patterns: List[str]) -> bool:
    """`_matches_pattern`, also against the path relative to the subproject context owning it.

    The patterns are context-relative (`.along/ISSUES/**`, `docs/**`), so a subproject's own
    Along state and docs match like the root's. A plain `**/` prefix would not do: `fnmatch`
    `*` crosses `/`. [bug--subproject-model-overdetection] REQ-6
    """
    if _matches_pattern(rel_target, patterns):
        return True
    ctx = subproject_context(repo_root, repo.normalize_posix(rel_target))
    if not ctx:
        return False
    sub_rel = repo.canonical_relpath(os.path.join(repo_root, rel_target), ctx)
    return not sub_rel.startswith("..") and _matches_pattern(sub_rel, patterns)


def _bound_scope_covers(repo_root: str, key: Optional[str], rel_target: str) -> bool:
    """The session's bound issue declares `rel_target` in its `write_scope` / `allowed_roots`.

    Entries are written by `along start --write-scope/--allow-root` and resolve against the
    issue's own context. [bug--subproject-model-overdetection] REQ-8
    """
    from . import containment
    ctx, slug = session.resolve_bound(repo_root, key)
    fm = _issue_frontmatter(ctx, slug) if slug else None
    if not fm:
        return False
    entries = containment._as_list(fm.get("write_scope")) + containment._as_list(fm.get("allowed_roots"))
    target = containment.canonical(os.path.join(repo_root, rel_target))
    return any(containment.is_within(target, containment.canonical(e, ctx)) for e in entries)


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
    diag = repo.diagnostics_dir(repo_root)
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


def record_gate_denial(event: HookEvent, repo_root: Optional[str], gate: str, reason: Optional[str]) -> None:
    """An enforced gate held the event: note it in the bound issue's execution trace.

    See [bug--session-records-not-captured] REQ-2.
    """
    if not repo_root:
        return
    first = (reason or "").strip().splitlines()[0] if (reason or "").strip() else ""
    first = first if len(first) <= 160 else first[:157] + "..."
    session.trace_event(repo_root, event_session_key(event), f"denied [{gate}] {event.tool_name}: {first}",
                        collapse=True)
    # A later bypass flag for this gate must follow a failure the user saw.
    from .. import bypass
    bypass.record_hook_denial(repo_root, gate, event_session_key(event))


def record_tool_activity(event: HookEvent, repo_root: str) -> None:
    """Record file modifications and test runs to track lifecycle state.

    Called by the engine only for events the gates allowed. An edit counts on PostToolUse,
    once the tool succeeded, so a write a gate (or the user) rejected is never attributed
    to the session; a test run counts on PreToolUse, after the gates let the command
    through. See [bug--hook-activation-and-gate-deadlock].
    """
    if not repo_root:
        return

    # The user's last message: CLI approvals and bypasses are checked against it.
    # [bug--plan-approval-self-and-lost]
    if event.event_type == HookEventType.USER_PROMPT_SUBMIT:
        session.record_user_prompt(repo_root, event_session_key(event))
        return

    # Claude Code runs ExitPlanMode's PostToolUse only after the user accepted the plan; the
    # plan text (tool_input.plan) goes into the blackboard. See [feat--plan-approval-exit-plan-mode],
    # [bug--session-records-not-captured].
    raw_tool = str((event.raw_payload or {}).get("tool_name") or "")
    if event.event_type == HookEventType.POST_TOOL_USE and raw_tool == "ExitPlanMode":
        plan = (event.tool_args or {}).get("plan")
        if not isinstance(plan, str):
            plan = ((event.raw_payload or {}).get("tool_input") or {}).get("plan")
        session.record_accepted_plan(repo_root, event_session_key(event), plan if isinstance(plan, str) else None)
        return

    now_iso = datetime.now(timezone.utc).isoformat()
    key = event_session_key(event)
    trace = load_activity_trace(repo_root, key)

    # Track file edits: repository files outside .along/ (agent state is not source), plus the
    # lifecycle hooks in .along/scripts/ [feat--rule-pack-protection-gate].
    if event.tool_name in ("write_to_file", "write_file", "replace_file_content", "edit_file", "patch_file", "create_file"):
        if event.event_type != HookEventType.POST_TOOL_USE:
            return
        rel = _repo_relative(_extract_target_file(event), repo_root)
        # Every repository edit goes into the bound issue's execution trace, except the
        # blackboard and diagnostics themselves [bug--session-records-not-captured].
        if rel and not _matches_pattern(rel, list(TRACE_EXCLUDED_PATTERNS)):
            # Ledger first (source of truth for attribution), then the readable trace
            # [feat--parallel-session-closeout].
            record = session.record_event(repo_root, key, "edit", repo.normalize_posix(rel))
            if record:
                # The hook projects the same record onto the runner's span (fail-open).
                event.ledger_event = record
            session.trace_event(repo_root, key, f"edit {repo.normalize_posix(rel)}", collapse=True)
        if rel and is_source_edit(rel):
            trace["last_edit_time"] = now_iso
            edited = trace.get("edited_files", [])
            if rel not in edited:
                edited.append(rel)
            trace["edited_files"] = edited[-200:]
            save_activity_trace(repo_root, trace, key)
        elif rel and is_doc_edit(rel):
            trace["last_doc_edit_time"] = now_iso
            save_activity_trace(repo_root, trace, key)

    # Track test executions
    elif event.tool_name in ("run_command", "execute_command", "bash", "shell"):
        cmd = _extract_command(event)
        if not cmd or event.event_type != HookEventType.PRE_TOOL_USE:
            return
        is_doc_cmd = bool(re.search(r"--doc(?:-tests)?\b", cmd))
        if any(p.search(cmd) for p in LIFECYCLE_TEST_PATTERNS) or (
                not has_lifecycle_test_hook(repo_root) and any(p.search(cmd) for p in TEST_COMMAND_PATTERNS)):
            if is_doc_cmd:
                trace["last_doc_test_time"] = now_iso
            else:
                trace["last_test_time"] = now_iso
                trace["last_doc_test_time"] = now_iso
            save_activity_trace(repo_root, trace, key)
        elif any(p.search(cmd) for p in TEST_COMMAND_PATTERNS):
            trace["last_raw_test_time"] = now_iso
            save_activity_trace(repo_root, trace, key)


def _repo_relative(target: str, repo_root: str) -> Optional[str]:
    """POSIX path of `target` relative to `repo_root`, or None when outside it.

    A path inside the root's state directory comes back as `.along/...` even when that
    directory lives elsewhere (a declared root such as `.local/.along/`), so state paths
    match the same patterns wherever the state is kept.
    """
    if not target:
        return None
    abs_target = os.path.normpath(target if os.path.isabs(target) else os.path.join(repo_root, target))
    sdir = os.path.normpath(repo.state_dir(repo_root))
    if not repo._same_path(sdir, os.path.join(repo_root, repo.STATE_DIR)) \
            and repo.is_within(abs_target, sdir):
        inner = repo.canonical_relpath(abs_target, sdir)
        return repo.STATE_DIR if inner == "." else f"{repo.STATE_DIR}/{inner}"
    if os.path.isabs(target):
        rel = repo.safe_relpath(target, repo_root)
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
        return not is_doc_edit(rel)
    idx = parts.index(".along")
    return len(parts) > idx + 2 and parts[idx + 1] == "scripts"


def is_doc_edit(rel: str) -> bool:
    """True for documentation outside `.along/`: Markdown anywhere (except skills, rules, code), or anything under a `docs/`.

    Not a source edit for test_before_stop unless the gate sets `count_docs: true`.
    [bug--lifecycle-test-false-pass] REQ-4
    """
    parts = repo.normalize_posix(rel).lower().split("/")
    if ".along" in parts or not parts:
        return False
    base = parts[-1]
    norm = "/".join(parts)
    if norm in ("agents.md", "claude.md", "gemini.md") or base in ("agents.md", "claude.md", "protocol.md"):
        return False
    if "skills" in parts or norm.startswith("skills/"):
        return False
    return base.endswith(".md") or "docs" in parts[:-1]


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

    rel_target = _repo_relative(target, repo_root)
    if rel_target is None:
        return None

    norm_rel = repo.normalize_posix(rel_target).lstrip("/")
    if not (norm_rel.startswith("docs/") or norm_rel.startswith(".along/")):
        return None

    abs_target = os.path.normpath(target if os.path.isabs(target) else os.path.join(repo_root, target))
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
    # Check if this active session is bound to an issue targeting this doc with an approved plan.
    slug = fm.get("slug") or os.path.splitext(os.path.basename(rel_target))[0].replace("topic--", "")
    key = event_session_key(event)
    active_slug = session.get_active_session_slug(repo_root, key)

    is_targeted = False
    if active_slug:
        clean_active = active_slug.replace("docs--", "").replace("topic--", "")
        if clean_active == slug or active_slug == slug or active_slug == f"docs--{slug}" or active_slug == f"topic--{slug}":
            is_targeted = True
        else:
            iss = entities.find_issue_by_slug(repo_root, active_slug)
            if iss and iss.get("file_path") and os.path.isfile(iss["file_path"]):
                try:
                    i_fm, _, _ = frontmatter.try_parse(textio.read_text(iss["file_path"], strict=False))
                    if i_fm:
                        affects = i_fm.get("affects") or []
                        if isinstance(affects, str):
                            affects = [affects]
                        norm_target = repo.normalize_posix(rel_target).lstrip("/")
                        affects_norm = [repo.normalize_posix(str(a)).lstrip("/") for a in affects]
                        target_doc = i_fm.get("target_doc") or ""
                        if norm_target in affects_norm or rel_target in affects or any(a.endswith(os.path.basename(rel_target)) for a in affects) or (target_doc and os.path.basename(rel_target) in str(target_doc)):
                            is_targeted = True
                except (OSError, UnicodeDecodeError, ValueError):
                    pass
        if is_targeted and (not key or session.is_plan_approved(repo_root, slug=active_slug, key=key)):
            return None
    elif not key:
        # In test environments or runtimes without session tracking, verify an active doc issue exists
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


_ENTITY_DIR_PATTERN = re.compile(
    r"\.along[/\\]+(?:ISSUES|DECISIONS|MILESTONES|RISKS|SPIKES)(?:[/\\]|$)",
    re.IGNORECASE,
)
_SHELL_DELETION_CMD_RE = re.compile(
    r"(?:^|[|;&(\n\s])(?:git\s+(?:-\S+\s+)*rm|(?:rm|rmdir|del|erase|Remove-Item|ri|unlink)(?:\.exe)?)\b|"
    r"(?:os\.(?:remove|unlink|rmdir)|shutil\.rmtree|\.unlink\(\))",
    re.IGNORECASE,
)
_DELETE_TOOL_NAMES = frozenset({"delete_file", "remove_file", "unlink", "delete", "file_delete", "remove"})


def _extract_all_target_paths(event: HookEvent) -> List[str]:
    args = event.tool_args or {}
    paths: List[str] = []
    for k in ("TargetFile", "target_file", "path", "FilePath", "file_path", "filename", "file"):
        val = args.get(k)
        if val:
            if isinstance(val, str):
                paths.append(val)
            elif isinstance(val, (list, tuple)):
                paths.extend(str(x) for x in val if x)
    for k in ("paths", "files", "TargetFiles", "target_files"):
        val = args.get(k)
        if isinstance(val, (list, tuple)):
            paths.extend(str(x) for x in val if x)
        elif isinstance(val, str):
            paths.append(val)
    return paths


def check_entity_deletion_protection(event: HookEvent, repo_root: str, **kwargs: Any) -> Optional[str]:
    """Intercept file deletion tools and shell commands deleting issue/ADR/milestone/risk/spike files."""
    tool = (event.tool_name or "").lower()

    # 1. File deletion tools
    if tool in _DELETE_TOOL_NAMES:
        for p in _extract_all_target_paths(event):
            if _ENTITY_DIR_PATTERN.search(p):
                return (
                    "Entity file deletion rejected by [gate: entity-reference-integrity]: "
                    "Deleting an issue, ADR, milestone, risk, or spike file is forbidden. "
                    "Use 'along issue supersede' / 'along issue rename' (split: supersede into several keys)."
                )

    # 2. Shell commands
    if tool in ("run_command", "execute_command", "bash", "shell"):
        cmd = _extract_command(event)
        if cmd and _ENTITY_DIR_PATTERN.search(cmd):
            segments = shellparse.split_segments(cmd)
            if segments is None:
                segments = [cmd]
            for seg in segments:
                if _ENTITY_DIR_PATTERN.search(seg) and _SHELL_DELETION_CMD_RE.search(seg):
                    return (
                        "Entity file deletion rejected by [gate: entity-reference-integrity]: "
                        "Deleting an issue, ADR, milestone, risk, or spike file is forbidden. "
                        "Use 'along issue supersede' / 'along issue rename' (split: supersede into several keys)."
                    )

    return None


def check_cli_safety(event: HookEvent, repo_root: str, **kwargs: Any) -> Optional[str]:
    """Check command line for dangerous shell patterns and destructive commands."""
    entity_err = check_entity_deletion_protection(event, repo_root, **kwargs)
    if entity_err:
        return entity_err

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


def is_unbound(repo_root: str, key: Optional[str]) -> bool:
    """True when the agent session is not bound to an issue (no binding, no runner slug)."""
    _slug, how = session.resolve_active_session(repo_root, key)
    return how not in ("binding", "env", "elsewhere")


def _enforce_unbound(options: Optional[Dict[str, Any]]) -> bool:
    """Gate option `enforce_unbound`: also hold sessions not bound to an issue (default off)."""
    return bool((options or {}).get("enforce_unbound", False))


def check_mutation_authorization(event: HookEvent, repo_root: str, options: Optional[Dict[str, Any]] = None,
                                 **kwargs: Any) -> Optional[Any]:
    """Intercept file mutations and shell commands outside execution phase without plan approval.

    Sessions not bound to an issue are not held unless the repository sets
    `enforce_unbound: true` for this gate; read-only and verification commands (build,
    test, lint, typecheck) pass in every phase. See [bug--hook-activation-and-gate-deadlock].
    """
    if event.event_type != HookEventType.PRE_TOOL_USE:
        return None

    tool = event.tool_name
    if tool in SAFE_READ_TOOLS:
        return None

    cmd = ""
    # Check file modification tools
    if tool in ("write_to_file", "write_file", "replace_file_content", "edit_file", "patch_file", "create_file"):
        target = _extract_target_file(event)
        if not target or not repo_root:
            return None

        # Outside the repository root (brain artifacts, temporary directories): not ours.
        rel_target = _repo_relative(target, repo_root)
        if rel_target is None:
            return None

        # Check whitelisted session/planning/diagnostics paths (in any context)
        if _matches_in_context(rel_target, repo_root, list(MUTATION_WHITELIST_PATTERNS)):
            return None

    # Check shell commands
    elif tool in ("run_command", "execute_command", "bash", "shell"):
        cmd = _extract_command(event).strip()
        if not cmd:
            return None
        if shellparse.is_plan_gate_exempt(cmd):
            return None
        # `along wrap` left this session a completion token for the issue it commits, or the
        # user approved closing it out [feat--parallel-session-closeout] REQ-6.
        commit_issue = shellparse.along_commit_issue(cmd)
        if commit_issue:
            commit_slug = entities.parse_key(commit_issue)[1]
            ckey = event_session_key(event)
            if commit_slug in session.completion_tokens(repo_root, ckey) \
                    or commit_slug in session.closeout_approved(repo_root, ckey):
                return None

    # Classify tool nature
    from . import toolnature
    nature_res = toolnature.classify_event(event, repo_root=repo_root)
    t_class = nature_res.tool_class

    # Read-only and verification: allowed in every phase
    if t_class in (toolnature.ToolClass.READ_ONLY, toolnature.ToolClass.VERIFICATION):
        return None

    # Sessions not bound to an issue are not held unless enforce_unbound: true
    key = event_session_key(event)
    if not _enforce_unbound(options) and is_unbound(repo_root, key):
        return None

    # Unknown tools: hold with unclassified reason directing the agent to ask user
    if t_class == toolnature.ToolClass.UNKNOWN:
        pat = nature_res.unclassified_pattern or (cmd.split()[0] if cmd else tool)
        reason = (
            f"Unclassified Tool Nature [gate: require-plan-approval]: Tool or command '{pat}' has unclassified nature. "
            f"Ask the user for its nature (read-only, verification, workspace-write, external, destructive) "
            f"and record it via 'along tool classify \"{pat}\" <class>'."
        )
        if event.runtime == "antigravity":
            return GateResult(
                decision=GateDecision.ASK,
                reason=reason,
                gate_name="require_plan_approval",
            )
        return reason

    slug, how = session.resolve_active_session(repo_root, key)
    approved = session.is_plan_approved(repo_root, slug=slug, key=key)
    phase = session.get_session_phase(repo_root, slug=slug, key=key)

    # Destructive tools: require confirmation
    if t_class == toolnature.ToolClass.DESTRUCTIVE:
        desc = nature_res.rule_desc or "destructive operation"
        destructive_confirmed = session.is_destructive_confirmed(repo_root, slug=slug, key=key)
        if approved and (phase == "execution" or not slug) and destructive_confirmed:
            return None
        reason = (
            f"Destructive Action [gate: require-plan-approval]: Tool or command '{cmd or tool}' is classified as destructive ({desc}). "
            "Execution requires explicit confirmation. In interactive environments approve prompt, or run 'along plan approve --confirm-destructive'."
        )
        if event.runtime == "antigravity":
            return GateResult(
                decision=GateDecision.ASK,
                reason=reason,
                gate_name="require_plan_approval",
            )
        return reason

    # External tools: require explicit confirmation
    if t_class == toolnature.ToolClass.EXTERNAL:
        desc = nature_res.rule_desc or "external operation"
        external_confirmed = session.is_external_confirmed(repo_root, slug=slug, key=key)
        if approved and (phase == "execution" or not slug) and external_confirmed:
            return None
        reason = (
            f"External Action [gate: require-plan-approval]: Tool or command '{cmd or tool}' is classified as external ({desc}). "
            "Execution interacts with remote services and requires explicit confirmation. In interactive environments approve prompt, or run 'along plan approve --confirm-external'."
        )
        if event.runtime == "antigravity":
            return GateResult(
                decision=GateDecision.ASK,
                reason=reason,
                gate_name="require_plan_approval",
            )
        return reason

    # Workspace-write: require plan approval (allow if approved or in execution phase)
    if approved and (phase == "execution" or not slug):
        return None

    # Violation: inquiry phase or unapproved plan
    target = f"issue '{slug}'" if slug else "this session"
    if how == "ambiguous":
        target = "this session (several in-progress issues, none bound to it)"
    elif how == "single" and key:
        target = f"this session (not bound to an issue; in-progress '{slug}' is not bound to it)"
    reason = (
        f"Inquiry Read-Only Invariance [gate: require-plan-approval]: "
        f"No approved plan for {target} (phase: '{phase}', plan_approved: {str(approved).lower()}). "
        "Call EnterPlanMode, write the plan, then ExitPlanMode. Outside plan mode, write the "
        "plan to a file and run 'along plan approve --plan-file <path>' after the user's explicit yes. "
        "Use 'along start <slug>' to bind this session to an issue."
    )
    if tool in ("run_command", "execute_command", "bash", "shell") and shellparse.is_along_commit(cmd):
        reason += " " + _held_commit_reason(repo_root, key, cmd)

    if event.runtime == "antigravity":
        return GateResult(
            decision=GateDecision.ASK,
            reason=reason,
            gate_name="require_plan_approval",
        )
    return reason


def _held_commit_reason(repo_root: str, key: Optional[str], cmd: str) -> str:
    """Why an `along commit` without an approved plan is held, and what to run instead.

    See [bug--commit-blocked-after-wrap] REQ-7.
    """
    issue = shellparse.along_commit_issue(cmd)
    if issue is None:
        return ("This 'along commit' rewrites files (--fix-typography), redirects output or is chained "
                "with a mutation: run the plain 'along commit -i <slug> ...' on its own.")
    if not issue:
        return ("Without an approved plan, 'along commit' passes only for an issue this session wrapped: "
                "pass '-i <slug>'.")
    slug = entities.parse_key(issue)[1]
    owners = [k for k in session.completion_token_owners(repo_root, slug) if k != key]
    if owners:
        return (f"Issue '{slug}' was wrapped by another agent session ({', '.join(owners)}): commit it from "
                "that session.")
    return (f"This session holds no completion token for '{slug}' and no closeout approval for it: "
            f"'along wrap {slug}' in the session that had its plan approved leaves a token; a closeout needs the "
            f"user's yes, then 'along plan approve --closeout {slug}'; otherwise bind the issue ('along start') "
            "and get the plan approved.")


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

    # Outside the repository root (brain artifacts, temp files, another drive): not ours.
    rel_target = _repo_relative(target, repo_root)
    if rel_target is None:
        return None

    if _matches_in_context(rel_target, repo_root, excludes):
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
    if how == "elsewhere" and _bound_scope_covers(repo_root, key, rel_target):
        return None
    if how == "elsewhere":
        bctx, bslug = session.resolve_bound(repo_root, key)
        where = repo.canonical_relpath(bctx, repo_root) if bctx else "?"
        return (
            f"Mandatory Issue Anchoring Violation [gate: require-active-issue]: this session is bound to "
            f"'{bslug}' in '{where}/.along/', and '{rel_target}' is outside that subproject. Bind an issue "
            f"of this .along/ (or an umbrella issue) with 'along start <slug>', or declare the folder in "
            f"the bound issue's scope ('along start {bslug} --write-scope <path>')."
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


def check_test_before_stop(event: HookEvent, repo_root: str, options: Optional[Dict[str, Any]] = None,
                           **kwargs: Any) -> Optional[str]:
    """Ensure automated tests were run after code modifications before stopping turn.

    Quiet for sessions not bound to an issue (unless `enforce_unbound: true`) and while the
    circuit breaker blocks commands, since no test could run then.
    """
    if not repo_root:
        return None

    key = event_session_key(event)
    if not _enforce_unbound(options) and is_unbound(repo_root, key):
        return None
    from .. import circuit
    if circuit.get_breaker_state(repo_root)[0] == circuit.CircuitState.TRIPPED:
        return None

    # [feat--test-gate-cost-reduction] REQ-1: if the working tree has a recorded green run,
    # the gate passes without checking timestamps (covers clean / reverted trees and runs
    # recorded by agent runs, commit, wrap, or closeout).
    tree = testruns.tree_hash(repo_root)
    if tree and testruns.green_run_for(repo_root, tree):
        return None

    trace = load_activity_trace(repo_root, key)
    edit_time = trace.get("last_edit_time")
    doc_time = trace.get("last_doc_edit_time")
    test_time = trace.get("last_test_time")
    doc_test_time = trace.get("last_doc_test_time")

    # [feat--test-gate-cost-reduction] REQ-2: Doc-only edits under count_docs: true
    # are satisfied by a scoped run of Markdown-facing tests.
    count_docs = bool((options or {}).get("count_docs"))
    has_source_edits = (edit_time is not None) and (test_time is None or test_time < edit_time)

    if count_docs and doc_time:
        has_doc_edits = (test_time is None or doc_time > test_time) and (doc_test_time is None or doc_time > doc_test_time)
    else:
        has_doc_edits = False

    if has_source_edits:
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

    if has_doc_edits:
        raw = trace.get("last_raw_test_time")
        hint = ""
        if raw and raw >= doc_time:
            hint = (" A raw test runner ran after the edit, but this repository has a lifecycle "
                    "test hook, and only it counts.")
        doc_hint = " (or doc-scoped tests via 'along test --doc')" if (options or {}).get("doc_tests") else ""
        return (
            "Turn Completion Rejected [gate: test-before-stop]: Documentation files were modified in this session, "
            f"but automated tests have not been executed afterward.{hint} "
            f"Run tests via 'along test'{doc_hint} before completing."
        )

    return None


def check_wrap_before_stop(event: HookEvent, repo_root: str, **kwargs: Any) -> Optional[str]:
    """Every issue completed today is listed in `issues_completed` of a session log of today.

    The local date, as `along wrap` / `along issue done` write it (`entities.today_iso`).
    See [bug--session-records-not-captured] REQ-6.
    """
    if not repo_root:
        return None

    done_dir = os.path.join(_issues_dir(repo_root), "done")
    if not os.path.isdir(done_dir):
        return None

    today = entities.today_iso()
    completed_today: List[str] = []
    try:
        for entry in os.scandir(done_dir):
            if entry.is_file() and entry.name.endswith(".md"):
                parsed, _body, _err = frontmatter.try_parse(textio.read_text(entry.path, strict=False))
                if parsed and parsed.get("status") == "done" and str(parsed.get("completed", "")).startswith(today):
                    completed_today.append(entry.name[:-3])
    except (OSError, UnicodeDecodeError, ValueError):
        pass
    if not completed_today:
        return None

    logged: set = set()
    year_dir = os.path.join(repo.state_dir(repo_root), "SESSIONS", today.split("-")[0])
    if os.path.isdir(year_dir):
        for name in os.listdir(year_dir):
            if name.startswith(today) and name.endswith(".md"):
                try:
                    fm, _body, _err = frontmatter.try_parse(textio.read_text(os.path.join(year_dir, name), strict=False))
                except (OSError, UnicodeDecodeError):
                    continue
                logged.update(str(k) for k in ((fm or {}).get("issues_completed") or []))
    missing = sorted(k for k in completed_today if k not in logged)
    if not missing:
        return None
    first = entities.parse_key(missing[0])[1]
    return (
        f"Turn Completion Rejected [gate: wrap-before-stop]: issue(s) completed today ({today}) are not in "
        f"'issues_completed' of any session log of today: {', '.join(missing)}. "
        f"Record each one with 'along wrap <slug> --no-decisions -m \"...\"' (e.g. 'along wrap {first} ...'); "
        "it also works for an issue already in done/."
    )


def check_uncommitted_wrap_before_stop(event: HookEvent, repo_root: str, **kwargs: Any) -> Optional[str]:
    """Warn if a session completed/wrapped an issue but attributed files remain uncommitted.

    [bug--wrapped-work-left-uncommitted] REQ-4. Evaluated as an optional Stop-gate warning.
    """
    if not repo_root:
        return None
    from .. import closeout
    sid = event_session_key(event) if event else session.current_session_key()
    tokens = session.completion_tokens(repo_root, sid) if sid else []
    done_attr = closeout.done_issues_attribution(repo_root)
    changes = closeout.git_changes(repo_root)
    if not changes:
        return None
    changed_keys = {closeout.path_key(p): p for p in changes}

    # Only this session's issues are listed in full; other sessions' leftovers collapse to
    # one line. [bug--stop-hook-shadow-list-scope]
    bound = session.load_binding(repo_root, sid).get("slug") if sid and session.load_binding(repo_root, sid) else None
    own_slugs = set(tokens) | ({str(bound)} if bound else set())

    def dirty(dinfo: Dict[str, Any]) -> bool:
        dfiles = list(dinfo["files"].keys()) + dinfo["entity_files"]
        return any(closeout.path_key(p) in changed_keys for p in dfiles)

    def touched_by_this_session(dinfo: Dict[str, Any]) -> bool:
        return bool(sid) and any(sid in (meta or {}).get("sessions", []) for meta in dinfo["files"].values()
                                 if isinstance(meta, dict))

    mine: List[str] = []
    others: List[str] = []
    for tok in tokens:
        if not any(info["slug"] == tok for info in done_attr.values()):
            mine.append(tok)
    for dinfo in done_attr.values():
        if not dirty(dinfo):
            continue
        # Without a session id nothing tells sessions apart: every issue is listed.
        if not sid or dinfo["slug"] in own_slugs or touched_by_this_session(dinfo):
            mine.append(dinfo["slug"])
        else:
            others.append(dinfo["slug"])

    mine = sorted(set(mine))
    others = sorted(set(others) - set(mine))
    if not mine and not others:
        return None
    parts = []
    if mine:
        first = mine[0]
        parts.append(
            f"Session wrapped issue(s) but attributed files remain uncommitted: {', '.join(mine)}. "
            f"Commit them with 'along commit -i {first} --paths ...' or close out with 'along session close {first}'.")
    if others:
        parts.append(f"{len(others)} other session issue(s) have uncommitted attributed files ('along session list').")
    return " ".join(parts)


def check_projection_sync_before_stop(event: HookEvent, repo_root: str, **kwargs: Any) -> Optional[str]:
    """Keep every context's ISSUES.md equal to the board compiled from its issue files.

    Recompiling is mechanical, so the hook does it itself instead of rejecting the turn: a
    rejection could demand a write that another gate (or plan mode) forbids at that moment.
    Staleness is judged by content, not mtimes, so a checkout or `touch` does not count.
    Never blocks. [feat--gate-friction-and-bypass-accountability] REQ-2
    """
    if not repo_root:
        return None
    try:
        contexts = [os.path.abspath(repo_root)]
        contexts += [c for c in repo.find_agent_contexts(repo_root) if c not in contexts]
    except OSError:
        return None
    synced = []
    for ctx in contexts:
        try:
            if _resync_issues_board(ctx):
                synced.append(repo.safe_relpath(os.path.join(repo.state_dir(ctx), "ISSUES.md"), repo_root))
        except (OSError, UnicodeDecodeError, ValueError, frontmatter.FrontmatterError):
            # A projection refresh never blocks the stop; `along issue sync` reports the cause.
            continue
    if synced:
        print("[ALONG HOOK] Auto-synced stale projection(s): " + ", ".join(
            p.replace(os.sep, "/") for p in synced), file=sys.stderr)
    return None


def _resync_issues_board(ctx: str) -> bool:
    """Rewrite ctx's ISSUES.md when it differs from the compiled board; True if rewritten."""
    if not os.path.isdir(_issues_dir(ctx)):
        return False
    board = os.path.join(repo.state_dir(ctx), "ISSUES.md")
    compiled = entities.compile_issues_board(ctx)
    current = textio.read_text(board) if os.path.isfile(board) else None
    if current is not None and current.replace("\r\n", "\n").strip() == compiled.replace("\r\n", "\n").strip():
        return False
    entities.sync_issues_board(ctx)
    return True


_ENTITY_DIRS = ("ISSUES/", "MILESTONES/", "RISKS/", "SPIKES/", "CHECKLISTS/", "DECISIONS/", "SESSIONS/")


def _entity_files_changed(repo_root: str) -> bool:
    """True when git reports a changed entity file under the state dir (or git cannot say)."""
    real_root = os.path.realpath(repo_root)
    sdir = repo.state_dir(real_root)
    rel = repo.canonical_relpath(sdir, real_root)
    result = proc.run_capture(["git", "status", "--porcelain", "-uall", "--", rel], cwd=real_root,
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
    """Entity files changed: no new dangling references or enum violations.

    Only problems absent at `HEAD` block; pre-existing ones belong to `along doctor
    --entities`, not to the agent that happens to touch an entity file.
    [bug--entity-gate-blocks-preexisting-problems]
    """
    if not repo_root or not os.path.isdir(repo.state_dir(repo_root)):
        return None
    if not _entity_files_changed(repo_root):
        return None
    from .. import gates
    problems, _old = gates.split_entity_integrity_errors(repo_root)
    if not problems:
        return None
    shown = "; ".join(problems[:5]) + (f"; ... {len(problems) - 5} more" if len(problems) > 5 else "")
    return (
        "Turn Completion Rejected [gate: entity-reference-integrity]: "
        f"{len(problems)} new entity graph problem(s) (absent at HEAD): {shown}. "
        "Fix them (see `along doctor --entities`); rename or retire referenced entities with "
        "`along issue rename` / `along issue supersede` instead of deleting them."
    )


def subproject_context(repo_root: str, rel_target: str) -> Optional[str]:
    """Directory of the nearest Along context below `repo_root` that owns `rel_target`, or None.

    A `.along/` holding only hook output is not a context, and the directory a declared root
    keeps its state in belongs to the declaring context, not to a subproject of its own.
    """
    abs_target = os.path.normpath(os.path.join(repo_root, rel_target))
    found = repo.find_context(os.path.dirname(abs_target))
    if not found:
        return None
    ctx, sdir = found
    if repo._same_path(ctx, repo_root):
        return None
    if repo._same_path(sdir, repo.state_dir(repo_root)):
        return None
    return ctx if repo.is_within(ctx, repo_root) else None


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


def _ref_slug(ref: Any) -> str:
    """Bare slug of an entity reference (`[root:task--x]` -> 'x')."""
    clean = str(ref).strip().strip("[]")
    if ":" in clean:
        clean = clean.split(":", 1)[1]
    return entities.parse_key(clean)[1]


def _parent_chain_slugs(context_root: str, fm: Optional[Dict[str, Any]], limit: int = 16) -> List[str]:
    """Slugs of the `parent` chain of an issue in `context_root`, nearest first.

    Each parent resolves in the nearest context of the chain from `context_root` upward
    (ISSUES/ and ISSUES/done/); a parent with the issue's own slug resolves above its context
    [bug--cross-context-parent-dangling]. Any depth, cycles stop the walk.
    """
    contexts = [owner for owner, _sdir in repo.context_chain(context_root)] or [context_root]
    chain: List[str] = []
    cur_owner, cur_slug = context_root, str((fm or {}).get("slug") or "")
    while fm and len(chain) < limit:
        parent = fm.get("parent")
        if not parent or not str(parent).strip():
            break
        pslug = _ref_slug(parent)
        if pslug in chain:
            break
        chain.append(pslug)
        nxt = None
        for owner in contexts:
            if pslug == cur_slug and repo._same_path(owner, cur_owner):
                continue
            if repo.is_within(cur_owner, owner) or repo._same_path(owner, cur_owner):
                found = _issue_frontmatter(owner, pslug, include_done=True)
                if found:
                    nxt, cur_owner, cur_slug = found, owner, pslug
                    break
        fm = nxt
    return chain


def _subproject_issue_ok(context_root: str, repo_root: str, key: Optional[str]) -> bool:
    """The session works on an issue of `context_root`, or on an umbrella issue whose child
    (at any depth, ISSUES/ or done/) lives there."""
    slug, _how = session.resolve_active_session(context_root, key)
    if slug:
        fm = _issue_frontmatter(context_root, slug)
        if fm and fm.get("status") == "in-progress":
            return True
    root_slug = session.get_active_session_slug(repo_root, key)
    root_fm = _issue_frontmatter(repo_root, root_slug) if root_slug else None
    if not root_fm:
        return False
    issues_dir = _issues_dir(context_root)
    for d in (issues_dir, os.path.join(issues_dir, "done")):
        if not os.path.isdir(d):
            continue
        for name in os.listdir(d):
            if not name.endswith(".md"):
                continue
            try:
                child, _b, _e = frontmatter.try_parse(textio.read_text(os.path.join(d, name), strict=False))
            except (OSError, UnicodeDecodeError, ValueError):
                continue
            if child and root_slug in _parent_chain_slugs(context_root, child):
                return True
    return False


def _bound_subproject_owns_root_entity(repo_root: str, rel_path: str, key: Optional[str]) -> Optional[str]:
    """Subproject path when the session is bound to a subproject issue and `rel_path` (an
    entity of the root `.along/`) is not on that issue's parent chain; else None.

    Decided from the target file and the binding, never from the shell cwd.
    [bug--subproject-boundary-cwd-context]
    """
    ctx, slug = session.resolve_bound(repo_root, key)
    if not slug or repo._same_path(ctx, repo_root) or not repo.is_within(ctx, repo_root):
        return None
    if not repo.is_along_state_dir(os.path.join(ctx, repo.STATE_DIR)):
        return None
    stem = os.path.basename(rel_path)
    stem = stem[:-3] if stem.endswith(".md") else stem
    bound_fm = _issue_frontmatter(ctx, str(slug), include_done=True)
    if entities.parse_key(stem)[1] in _parent_chain_slugs(ctx, bound_fm):
        return None
    return repo.canonical_relpath(ctx, repo_root)


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
            sub_rel = repo.canonical_relpath(os.path.join(repo_root, rel), ctx)
            if not sub_rel.lower().startswith(".along/") and \
                    not _subproject_issue_ok(ctx, repo_root, event_session_key(event)):
                sub = repo.canonical_relpath(ctx, repo_root)
                return (
                    f"Subproject Boundary Violation [gate: subproject-boundary]: '{rel}' belongs to subproject "
                    f"'{sub}', which has its own .along/. Work on it under an issue of '{sub}/.along/' "
                    f"('along start <slug>' from '{sub}'), or give a child issue there "
                    f"'parent: <root issue key>' of the umbrella issue this session is bound to."
                )

    rel_path = rel
    if rel_path is None:
        return None

    # A root entity written while the session works on a subproject issue: allowed for that
    # issue's parent chain (the umbrella), else it belongs in the subproject's .along/.
    # Decided from the target path and the binding, not the shell cwd
    # [bug--subproject-boundary-cwd-context].
    if rel_path.startswith(".along/") and not rel_path.startswith(".along/.session/"):
        subpath = _bound_subproject_owns_root_entity(repo_root, rel_path, event_session_key(event))
        if subpath:
            return (
                f"Subproject Boundary Violation [gate: subproject-boundary]: "
                f"Cannot write root '{rel_path}' while this session works on an issue of subproject "
                f"'{subpath}'. Entities of that work belong in '{subpath}/.along/'; root entities "
                f"on the bound issue's parent chain (its umbrella) are allowed."
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
    # Read-only inspection (git status, along doctor, cat) cannot worsen the fault and is how a
    # false trip is diagnosed [bug--stop-gates-breaker-deadlock].
    if cmd and cmd.strip() and shellparse.is_read_only_command(cmd):
        return None

    from .. import circuit
    state, anomaly = circuit.get_breaker_state(repo_root)
    if state == circuit.CircuitState.TRIPPED:
        sig = anomaly.signature if anomaly else "Environment failure"
        cls_name = anomaly.anomaly_class.value if anomaly else "Systemic Anomaly"
        evidence = ""
        if anomaly and (anomaly.source or anomaly.detail):
            first = anomaly.detail.splitlines()[0][:160] if anomaly.detail else ""
            evidence = f" Evidence: source '{anomaly.source or 'unknown'}', output '{first}'."
        return (
            f"Circuit Breaker Violation [gate: circuit-breaker]: Tool execution is blocked because "
            f"the systemic anomaly circuit breaker is TRIPPED ({cls_name}: {sig}).{evidence} "
            "Read-only commands still run. Human remediation is required: run 'along circuit status'; "
            "if the evidence is not a real fault, 'along circuit verify' then 'along circuit reset'."
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


