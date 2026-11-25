#!/usr/bin/env python3
"""
alongkit.hooks.config - Configuration and audit logging for lifecycle hooks.

Supports dual-mode governance:
- 'enforce': Blocks execution on gate violations.
- 'shadow': Evaluates gates and logs violations to .along/diagnostics/hooks_audit.jsonl
  without blocking tool execution.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
import json
import os
import re
import sys
from typing import Any, Callable, Dict, FrozenSet, List, Optional, Sequence, Tuple

from .. import attribution, repo, textio
from ..telemetry.redactor import Redactor
from .adapters.normalize import SHELL_TOOLS, WRITE_TOOLS
from .models import GateResult, HookEvent, HookEventType


class HookMode:
    ENFORCE = "enforce"
    SHADOW = "shadow"
    OFF = "off"


#: Baseline modes of gates whose catalogue profiles do not decide alone. Override per repo in
#: `.along/config.json` hooks.gates or with ALONG_HOOK_MODE.
DEFAULT_GATE_MODES: Dict[str, str] = {
    "projection_protection": HookMode.ENFORCE,
    "wrapped_work_uncommitted": HookMode.SHADOW,
}


#: State layer gates [feat--gate-strictness-profiles] REQ-2:
#: Anchoring and core integrity rules that MUST remain active ('block') in all profiles.
STATE_LAYER_GATES: Tuple[str, ...] = (
    "require_active_issue",
    "projection_protection",
    "test_before_stop",
)


def is_state_layer_gate(gate_name: str) -> bool:
    return gate_name in STATE_LAYER_GATES


SEVERITY_TO_MODE: Dict[str, str] = {
    "block": HookMode.ENFORCE,
    "warn": HookMode.SHADOW,
    "off": HookMode.OFF,
}


#: Gate tiers [feat--gate-friction-and-bypass-accountability] REQ-4:
#: - invariant: hard safety and state-integrity rules; always enforced, a repo config or
#:   ALONG_HOOK_MODE cannot shadow or disable them, and no bypass flag covers them;
#: - advisory: report only, always shadow;
#: - process (every other gate): enforced by default, shadowable per repo, and bypassable
#:   through `alongkit.bypass` with a reason the user accepted.
#: The catalogue (default_gates.yaml) carries the same `tier:` per gate; a test keeps them equal.
TIER_INVARIANT = "invariant"
TIER_PROCESS = "process"
TIER_ADVISORY = "advisory"
GATE_TIERS: Dict[str, str] = {
    "workspace_containment": TIER_INVARIANT,
    "no_tracked_secrets": TIER_INVARIANT,
    "projection_protection": TIER_INVARIANT,
    "rule_pack_protection": TIER_INVARIANT,
    "entity_deletion_protection": TIER_INVARIANT,
    "wrapped_work_uncommitted": TIER_ADVISORY,
    "projection_sync_before_stop": TIER_ADVISORY,
}


def gate_tier(gate_name: str) -> str:
    return GATE_TIERS.get(gate_name, TIER_PROCESS)


_DEFAULT_GATE_PROFILES_CACHE: Optional[Dict[str, Dict[str, str]]] = None


def get_default_gate_profiles() -> Dict[str, Dict[str, str]]:
    """Lazy load {gate_id: {strict: s, standard: s, light: s}} from default_gates.yaml."""
    global _DEFAULT_GATE_PROFILES_CACHE
    if _DEFAULT_GATE_PROFILES_CACHE is None:
        from .declarative import DEFAULT_GATES_FILE, load_gate_entries
        cache: Dict[str, Dict[str, str]] = {}
        for defn, _raw in load_gate_entries(DEFAULT_GATES_FILE):
            if defn.profiles:
                cache[defn.id] = dict(defn.profiles)
        _DEFAULT_GATE_PROFILES_CACHE = cache
    return _DEFAULT_GATE_PROFILES_CACHE


def load_gate_profiles_table(repo_root: Optional[str] = None) -> Dict[str, Dict[str, str]]:
    """Collect {gate_id: {strict: s, standard: s, light: s}} from default and repo YAML."""
    from .declarative import DEFAULT_GATES_FILE, load_gate_entries, merge_override
    table: Dict[str, Dict[str, str]] = {}
    defs_by_id = {}
    for defn, raw in load_gate_entries(DEFAULT_GATES_FILE):
        defs_by_id[defn.id] = defn
    if repo_root:
        repo_rules_dir = os.path.join(repo.state_dir(repo_root), "rules")
        repo_gates_file = os.path.join(repo_rules_dir, "gates.yaml")
        if os.path.isfile(repo_gates_file):
            for defn, raw in load_gate_entries(repo_gates_file):
                base = defs_by_id.get(defn.id)
                defs_by_id[defn.id] = merge_override(base, defn, raw) if base else defn
    for gid, defn in defs_by_id.items():
        if defn.profiles:
            table[gid] = dict(defn.profiles)
    return table


@dataclass
class HooksConfig:
    """Runtime configuration for hook execution."""
    mode: str = HookMode.ENFORCE
    gates: Dict[str, str] = field(default_factory=lambda: dict(DEFAULT_GATE_MODES))
    record_transcript: bool = False
    profile: Optional[str] = None
    gate_profiles: Dict[str, Dict[str, str]] = field(default_factory=dict)

    def get_gate_mode(self, gate_name: str) -> str:
        """Resolve mode for an individual gate; invariant tier and state layer win."""
        tier = gate_tier(gate_name)
        if tier == TIER_INVARIANT:
            return HookMode.ENFORCE
        if tier == TIER_ADVISORY:
            return HookMode.SHADOW

        # If global mode was explicitly set to shadow (e.g. ALONG_HOOK_MODE=shadow or test fixture)
        if self.mode == HookMode.SHADOW:
            return HookMode.SHADOW

        # Explicit per-gate override from repo config or test fixture
        # (excluding default gate modes that merely reflect baseline defaults)
        if gate_name in self.gates and gate_name not in DEFAULT_GATE_MODES:
            return self.gates[gate_name]

        # State layer gates always enforce across all profiles [REQ-2]
        if is_state_layer_gate(gate_name):
            if gate_name in self.gates and self.gates[gate_name] != DEFAULT_GATE_MODES.get(gate_name):
                return self.gates[gate_name]
            return HookMode.ENFORCE

        # Profile severity lookup
        profs = self.gate_profiles if self.gate_profiles else get_default_gate_profiles()
        gate_prof = profs.get(gate_name, {})
        active_prof = self.profile or "standard"
        if active_prof in gate_prof:
            sev = gate_prof[active_prof]
            return SEVERITY_TO_MODE.get(sev, HookMode.ENFORCE)
        elif active_prof == "autonomous":
            sev = gate_prof.get("standard", "block")
            return SEVERITY_TO_MODE.get(sev, HookMode.ENFORCE)

        if gate_name in self.gates:
            return self.gates[gate_name]
        return self.mode

    def overridden_gates(self) -> Dict[str, str]:
        """Gates a repo config or env set to shadow (process tier only)."""
        names = set(self.gates) | ({n for n in GATE_TIERS} if self.mode == HookMode.SHADOW else set())
        return {n: self.get_gate_mode(n) for n in sorted(names)
                if gate_tier(n) == TIER_PROCESS and self.get_gate_mode(n) == HookMode.SHADOW
                and DEFAULT_GATE_MODES.get(n) != HookMode.SHADOW}

    def is_enforcing(self, gate_name: str) -> bool:
        """True if the gate should actively block on violation."""
        return self.get_gate_mode(gate_name) == HookMode.ENFORCE

    def is_enabled(self, gate_name: str) -> bool:
        """True if gate is active (not off)."""
        return self.get_gate_mode(gate_name) != HookMode.OFF


def load_config(repo_root: Optional[str] = None) -> HooksConfig:
    """Load hooks configuration from repository or environment."""
    if not repo_root:
        repo_root = repo.find_repo_root()

    from .. import profiles
    active_profile = profiles.resolve_active_profile(repo_root)

    config = HooksConfig(profile=active_profile)
    config.gate_profiles = load_gate_profiles_table(repo_root)

    env_mode = os.environ.get("ALONG_HOOK_MODE", "").strip().lower()
    if env_mode in (HookMode.ENFORCE, HookMode.SHADOW):
        config.mode = env_mode
        for k in config.gates:
            config.gates[k] = env_mode

    if not repo_root:
        repo_root = repo.find_repo_root()

    if repo_root:
        config_path = os.path.join(repo.state_dir(repo_root), "config.json")
        if os.path.isfile(config_path):
            try:
                data = json.loads(textio.read_text(config_path, strict=False))
                hooks_data = data.get("hooks", {})
                if isinstance(hooks_data, dict):
                    if "mode" in hooks_data and hooks_data["mode"] in (HookMode.ENFORCE, HookMode.SHADOW):
                        if not env_mode:
                            config.mode = hooks_data["mode"]
                    if "gates" in hooks_data and isinstance(hooks_data["gates"], dict):
                        for gname, gmode in hooks_data["gates"].items():
                            if gmode in (HookMode.ENFORCE, HookMode.SHADOW):
                                config.gates[gname] = gmode
                    if "record_transcript" in hooks_data:
                        config.record_transcript = bool(hooks_data["record_transcript"])
            except (OSError, ValueError):
                pass

    return config


_AUDIT_REDACTOR: Optional[Redactor] = None


def _get_audit_redactor() -> Redactor:
    global _AUDIT_REDACTOR
    if _AUDIT_REDACTOR is None:
        _AUDIT_REDACTOR = Redactor()
    return _AUDIT_REDACTOR


#: Longest audit `target` kept; a longer command is cut with "...".
AUDIT_TARGET_MAX = 200


def audit_target(event: HookEvent) -> Optional[str]:
    """The command or file path an event acts on, cut to AUDIT_TARGET_MAX (not yet redacted)."""
    args = event.tool_args or {}
    for key in ("CommandLine", "command", "cmd", "TargetFile", "target_file", "file_path", "FilePath",
                "path", "notebook_path"):
        value = args.get(key)
        if isinstance(value, str) and value.strip():
            text = " ".join(value.split())
            return text if len(text) <= AUDIT_TARGET_MAX else text[:AUDIT_TARGET_MAX - 3] + "..."
    return None


def record_audit_entry(
    repo_root: Optional[str],
    event: HookEvent,
    result: GateResult,
    mode: str,
) -> None:
    """Append a violation record to .along/diagnostics/hooks_audit.jsonl.

    `decision` is `warn` for a shadow-mode record (nothing was blocked); `target` is the
    redacted command or path the gate judged, so false positives can be measured.
    [debt--gate-simplification]
    """
    if not repo_root:
        repo_root = repo.find_repo_root()
    if not repo_root:
        return

    try:
        diagnostics_dir = repo.ensure_diagnostics_dir(repo_root)
        audit_file = os.path.join(diagnostics_dir, "hooks_audit.jsonl")
        redactor = _get_audit_redactor()
        target = audit_target(event)
        decision = result.decision.value
        if mode == HookMode.SHADOW and decision != "allow":
            decision = "warn"
        entry = {
            "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "gate": redactor.sanitize_text(result.gate_name) if result.gate_name else result.gate_name,
            "decision": decision,
            "mode": mode,
            "runtime": redactor.sanitize_text(event.runtime) if event.runtime else event.runtime,
            "tool": redactor.sanitize_text(event.tool_name) if event.tool_name else event.tool_name,
            "reason": redactor.sanitize_text(result.reason) if result.reason else result.reason,
            "conversation_id": redactor.sanitize_text(event.conversation_id) if isinstance(event.conversation_id, str) else event.conversation_id,
            "step_idx": event.step_idx,
            # Appended last: earlier keys keep their order for existing readers.
            "target": redactor.sanitize_text(target) if target else None,
        }
        subagent = event.subagent_role or event.subagent_id
        if subagent:
            entry["subagent"] = redactor.sanitize_text(subagent)
        if event.subagent_id:
            entry["subagent_id"] = redactor.sanitize_text(event.subagent_id)
        if event.subagent_role:
            entry["subagent_role"] = redactor.sanitize_text(event.subagent_role)
        with open(audit_file, "a", encoding="utf-8") as handle:
            handle.write(json.dumps(entry) + "\n")
    except OSError:
        pass


def _format_hook_script_path(script_path: str) -> str:
    """Format script path safely across operating systems.

    On Windows, wrapping paths in quotes inside cmd /c commands spawned by Go/Node
    causes quotes to be escaped as \\", which cmd.exe does not unescape, passing
    literal quotes into Python and triggering [Errno 22] Invalid argument.
    If whitespace is present on Windows, resolve the 8.3 short path. If no
    whitespace exists (or short path succeeds), omit quotes.

    On Windows the result always uses forward slashes: Claude Code runs hooks through
    Git Bash, which strips unquoted backslashes (`C:\\Users\\Admin` -> `C:UsersAdmin`),
    so Python cannot open the script and exits 2, which Claude Code reads as "block".
    Forward slashes are valid for bash, cmd.exe, and Python alike.
    """
    if sys.platform == "win32":
        if " " in script_path:
            try:
                import ctypes
                norm = os.path.normpath(script_path)
                buf = ctypes.create_unicode_buffer(500)
                if ctypes.windll.kernel32.GetShortPathNameW(norm, buf, 500) > 0:
                    return buf.value.replace("\\", "/")
            except (AttributeError, OSError, ValueError, RuntimeError):
                pass
            return '"' + script_path.replace("\\", "/") + '"'
        return script_path.replace("\\", "/")
    if " " in script_path:
        return f'"{script_path}"'
    return script_path


def get_hook_command(runtime: str, event: str, is_global: bool = False) -> str:
    """Generate command string for a runtime lifecycle hook."""
    if not is_global:
        return f"python scripts/along_hook.py --runtime {runtime} --event {event}"
    script_path = os.path.expanduser("~/.along/bin/along_hook.py")
    formatted_path = _format_hook_script_path(script_path)
    return f"python {formatted_path} --runtime {runtime} --event {event}"


_RUNTIME_TOOL_UNION_CACHE: Dict[Tuple[str, int, Optional[str]], Tuple[str, ...]] = {}

#: Claude Code capitalised tool spellings that never appear in DeepSeek Harness and are
#: explicitly excluded from DSH matchers (see tests/test_hooks_dsh.py).
_DSH_FORBIDDEN_CLAUDE_NAMES: FrozenSet[str] = frozenset((
    "Write", "Edit", "Bash", "Read", "Glob", "Grep",
))

#: Native tool-name aliases per runtime, merged with the catalogue runtime gate union when
#: generating PreToolUse / PostToolUse manifest matchers.
CLAUDE_PRE_TOOL_ALIASES: Tuple[str, ...] = (
    "Write", "WriteFile", "write_file", "Edit", "EditFile", "edit_file",
    "MultiEdit", "NotebookEdit", "Bash", "bash", "PowerShell", "powershell",
    "Read", "Grep", "Glob", "LS", "Task", "Agent", "TodoWrite", "SendMessage",
)
CLAUDE_POST_TOOL_ALIASES: Tuple[str, ...] = (
    "Write", "WriteFile", "write_file", "Edit", "EditFile", "edit_file",
    "MultiEdit", "NotebookEdit", "ExitPlanMode", "Bash", "bash", "PowerShell", "powershell",
)
CODEX_PRE_TOOL_ALIASES: Tuple[str, ...] = (
    "write_file", "WriteFile", "Write", "create_file", "CreateFile",
    "edit_file", "EditFile", "Edit", "patch", "patch_file", "apply_patch",
    "shell", "exec", "execute", "bash", "Bash", "powershell", "PowerShell", "cmd",
    "read_file", "ReadFile", "Read", "view_image", "ViewImage",
    "list_dir", "ListDir", "list_directory", "ListDirectory", "LS",
    "grep_search", "GrepSearch", "grep", "Grep",
    "find_by_name", "find_files", "FindFiles", "file_search", "FileSearch", "Glob",
    "delete_file", "DeleteFile", "remove_file", "RemoveFile", "unlink", "Unlink",
    "delete", "Delete", "file_delete", "FileDelete", "remove", "Remove",
    "Task", "Agent", "TodoWrite", "SendMessage",
)
CODEX_POST_TOOL_ALIASES: Tuple[str, ...] = (
    "write_file", "WriteFile", "Write", "create_file", "CreateFile",
    "edit_file", "EditFile", "Edit", "patch", "patch_file", "apply_patch",
    "shell", "exec", "execute", "bash", "Bash", "powershell", "PowerShell", "cmd",
)
CURSOR_PRE_TOOL_ALIASES: Tuple[str, ...] = (
    "Shell", "Read", "Write", "Edit", "StrReplace", "str_replace",
    "MultiEdit", "NotebookEdit", "edit_notebook", "search_replace", "apply_patch",
    "Delete", "Grep", "GrepSearch", "ripgrep", "codebase_search",
    "Glob", "glob_file_search", "FileSearch",
    "LS", "ListDir", "ListDirectory",
    "Task", "Agent", "Subagent", "subagent", "TodoWrite", "SendMessage",
    "WebFetch", "WebSearch",
    "run_terminal_cmd", "RunTerminalCmd",
    "ReadFile", "ViewFile", "ViewImage", "read_image", "CreateFile",
    "FileDelete", "ExecuteCommand", "FindFiles",
    "write_file", "WriteFile", "edit_file", "EditFile",
    "delete_file", "DeleteFile", "remove_file", "RemoveFile", "unlink", "Unlink",
    "delete", "remove", "Remove",
    "bash", "Bash", "shell", "powershell", "PowerShell", "cmd", "run", "exec", "execute",
    "patch", "patch_file", "write", "edit",
)
CURSOR_POST_TOOL_ALIASES: Tuple[str, ...] = (
    "Shell", "Write", "Edit", "StrReplace", "str_replace",
    "MultiEdit", "NotebookEdit", "edit_notebook", "search_replace", "apply_patch",
    "write_file", "WriteFile", "CreateFile", "edit_file", "EditFile", "patch", "write", "edit",
    "run_terminal_cmd", "RunTerminalCmd", "ExecuteCommand",
    "powershell", "PowerShell", "cmd", "run", "exec", "execute",
)
DSH_PRE_TOOL_ALIASES: Tuple[str, ...] = (
    "read", "write", "edit", "glob", "grep", "pwsh", "bash", "read_image",
    "web_fetch", "web_search", "todo_write", "subagent", "subagent_fork",
    "send_message", "ask_user_question", "exit_plan_mode",
    "tool-pwsh", "tool_pwsh", "tool-bash", "tool_bash",
    "tool-fs", "tool_fs", "tool-fs/write", "tool-fs/edit", "tool-fs/create",
    "fs", "fs_write", "fs_edit", "tool-fs-search", "tool_fs_search", "fs_search",
    "tool-web", "tool_web", "tool-subagent", "tool_subagent",
    "PowerShell", "powershell", "WriteFile", "EditFile", "LS",
)
DSH_POST_TOOL_ALIASES: Tuple[str, ...] = (
    "write", "edit", "pwsh", "bash", "exit_plan_mode",
    "tool-pwsh", "tool_pwsh", "tool-bash", "tool_bash",
    "tool-fs", "tool_fs", "tool-fs/write", "tool-fs/edit", "tool-fs/create",
    "fs", "fs_write", "fs_edit", "PowerShell", "powershell", "WriteFile", "EditFile",
)

#: Explicit runtime narrowing records for runtimes whose native tool surface or hook
#: support cannot express the full canonical catalogue [bug--antigravity-manifest-matcher-unenforceable-invariants].
RUNTIME_HOOK_NARROWINGS: Dict[str, Dict[str, Any]] = {
    "cursor": {
        "unexpressible_tools": ("view_image", "send_message", "spawn_subagent"),
        "missing_capabilities": ("ask", "global_installer_hooks"),
        "notes": (
            "Cursor preToolUse has no dedicated native tool names for view_image, send_message, "
            "or spawn_subagent (and IDE editor-tab/@-mention reads bypass hooks); GenericCliAdapter "
            "cannot prompt ASK natively, and global installers do not register Cursor hooks by default."
        ),
    },
}


def get_runtime_hook_narrowing(runtime_name: str) -> Optional[Dict[str, Any]]:
    """Return explicit narrowing metadata for `runtime_name`, or None if full-coverage."""
    key = (runtime_name or "").strip().lower()
    entry = RUNTIME_HOOK_NARROWINGS.get(key)
    return dict(entry) if entry else None


def runtime_gate_tool_union(
    gates_file: Optional[str] = None,
    event_type: Optional[HookEventType] = None,
) -> Tuple[str, ...]:
    """Ordered union of `tools:` across every enabled `runtime`-enforced gate in the catalogue."""
    from . import declarative

    target = os.path.abspath(gates_file or declarative.DEFAULT_GATES_FILE)
    try:
        mtime_ns = os.stat(target).st_mtime_ns
    except OSError:
        mtime_ns = -1
    ev_key = event_type.value if event_type is not None else None
    cache_key = (target, mtime_ns, ev_key)
    cached = _RUNTIME_TOOL_UNION_CACHE.get(cache_key)
    if cached is not None:
        return cached

    ordered: List[str] = []
    seen = set()
    for defn in declarative.load_gate_definitions(target):
        if not defn.enabled or "runtime" not in defn.enforcement:
            continue
        if event_type is not None:
            if event_type != defn.event_type and event_type not in defn.extra_events:
                continue
        for tool in defn.tools:
            if tool and tool not in seen:
                seen.add(tool)
                ordered.append(tool)
    result = tuple(ordered)
    _RUNTIME_TOOL_UNION_CACHE[cache_key] = result
    return result


def _merge_matcher_tokens(
    *groups: Sequence[str],
    exclude: FrozenSet[str] = frozenset(),
) -> str:
    ordered: List[str] = []
    seen = set()
    for group in groups:
        for item in group:
            tok = str(item or "").strip()
            if tok and tok not in exclude and tok not in seen:
                seen.add(tok)
                ordered.append(tok)
    return "|".join(ordered)


def build_pre_tool_matcher(
    runtime_aliases: Sequence[str] = (),
    gates_file: Optional[str] = None,
    exclude: FrozenSet[str] = frozenset(),
) -> str:
    """Build a PreToolUse matcher covering `runtime_aliases` and all runtime gate tools."""
    gate_tools = runtime_gate_tool_union(gates_file=gates_file, event_type=HookEventType.PRE_TOOL_USE)
    return _merge_matcher_tokens(runtime_aliases, gate_tools, exclude=exclude)


def build_post_tool_matcher(
    runtime_aliases: Sequence[str] = (),
    gates_file: Optional[str] = None,
    exclude: FrozenSet[str] = frozenset(),
) -> str:
    """Build a PostToolUse matcher covering writes, shells, `runtime_aliases`, and PostToolUse gates."""
    post_gate_tools = runtime_gate_tool_union(gates_file=gates_file, event_type=HookEventType.POST_TOOL_USE)
    return _merge_matcher_tokens(runtime_aliases, WRITE_TOOLS, SHELL_TOOLS, post_gate_tools, exclude=exclude)


def _matcher_matches_tool(matcher: Optional[str], tool: str) -> bool:
    """True if a manifest `matcher` string admits `tool`."""
    if matcher is None:
        return True
    pat = str(matcher).strip()
    if not pat or pat in ("*", ".*"):
        return True
    tokens = {part.strip() for part in pat.split("|") if part.strip()}
    if tool in tokens:
        return True
    # Only fall back to regex fullmatch when a token uses regex syntax (e.g. `mcp__.*`),
    # never substring search so `"write"` cannot falsely claim `"write_to_file"`.
    if any(ch in pat for ch in (".", "*", "+", "?", "[", "]", "(", ")", "^", "$")):
        try:
            return re.fullmatch(pat, tool) is not None
        except re.error:
            return False
    return False


def _extract_pre_tool_matchers(runtime_name: str, manifest: Any) -> Tuple[bool, List[Optional[str]]]:
    """Return (has_along_hook, list_of_pre_tool_matchers) for a parsed manifest."""
    rt = (runtime_name or "").strip().lower()
    if rt == "opencode":
        if isinstance(manifest, str):
            has_before = bool(re.search(r'tool\.hook\(\s*["\']execute\.before["\']', manifest))
            return has_before, ["*"] if has_before else []
        if isinstance(manifest, dict):
            has_before = "tool.execute.before" not in (manifest.get("missing_hooks") or []) and bool(manifest.get("valid", True))
            return has_before, ["*"] if has_before else []
        return False, []

    if not isinstance(manifest, dict):
        return False, []

    entries: List[Any] = []
    if rt == "antigravity":
        gate_block = manifest.get("along-runtime-gates")
        if isinstance(gate_block, dict):
            entries = list(gate_block.get("PreToolUse") or [])
    elif rt == "claude":
        container = manifest.get("hooks") if isinstance(manifest.get("hooks"), dict) else manifest
        if isinstance(container, dict):
            entries = list(container.get("PreToolUse") or [])
    elif rt in ("codex", "dsh"):
        container = manifest.get("hooks") if isinstance(manifest.get("hooks"), dict) else manifest
        if isinstance(container, dict):
            entries = list(container.get("PreToolUse") or [])
    elif rt == "cursor":
        container = manifest.get("hooks") if isinstance(manifest.get("hooks"), dict) else manifest
        if isinstance(container, dict):
            entries = list(container.get("preToolUse") or container.get("PreToolUse") or [])

    matchers: List[Optional[str]] = []
    found = False
    for item in entries:
        if not isinstance(item, dict):
            continue
        if is_along_hook_entry(item, "PreToolUse") or rt == "antigravity":
            if rt == "antigravity" and not hook_entry_commands(item):
                continue
            found = True
            matchers.append(item.get("matcher"))
    return found, matchers


def audit_manifest_coverage(
    runtime_name: str,
    manifest: Any = None,
    gates_file: Optional[str] = None,
) -> Dict[str, Any]:
    """Compare `runtime_name`'s manifest matcher(s) against the catalogue runtime gate union."""
    rt = (runtime_name or "").strip().lower()
    if rt == "claude-code":
        rt = "claude"
    if manifest is None:
        if rt == "antigravity":
            manifest = get_antigravity_hook_manifest(gates_file=gates_file)
        elif rt == "claude":
            manifest = get_claude_hook_manifest(gates_file=gates_file)
        elif rt == "codex":
            manifest = get_codex_hook_manifest(gates_file=gates_file)
        elif rt == "cursor":
            manifest = get_cursor_hook_manifest(gates_file=gates_file)
        elif rt == "dsh":
            manifest = get_dsh_hook_manifest(gates_file=gates_file)
        elif rt == "opencode":
            src = os.path.join(os.path.dirname(__file__), "opencode_plugin.js")
            manifest = textio.read_text(src, strict=False) if os.path.isfile(src) else ""

    required = runtime_gate_tool_union(gates_file=gates_file, event_type=HookEventType.PRE_TOOL_USE)
    has_hook, matchers = _extract_pre_tool_matchers(rt, manifest)
    if not has_hook:
        missing = list(required)
    else:
        missing = [
            tool for tool in required
            if not any(_matcher_matches_tool(m, tool) for m in matchers)
        ]

    # Also verify runtime-native aliases in the adapter map are matched for non-OpenCode manifests
    unmatched_aliases: List[str] = []
    if has_hook and rt in ("claude", "codex", "cursor", "dsh"):
        required_set = set(required)
        alias_source: Sequence[str] = ()
        if rt == "claude":
            from .adapters.claude import TOOL_NAME_MAP as _CLAUDE_MAP
            alias_source = [k for k, v in _CLAUDE_MAP.items() if v in required_set]
        elif rt == "codex":
            from .adapters.codex import TOOL_NAME_MAP as _CODEX_MAP
            alias_source = [k for k, v in _CODEX_MAP.items() if v in required_set]
        elif rt == "cursor":
            alias_source = CURSOR_PRE_TOOL_ALIASES
        elif rt == "dsh":
            alias_source = DSH_PRE_TOOL_ALIASES
        for alias in alias_source:
            if not any(_matcher_matches_tool(m, alias) for m in matchers):
                unmatched_aliases.append(alias)

    narrowing = get_runtime_hook_narrowing(rt)
    explicit_missing_matcher = (rt == "cursor" and has_hook and any(m is None for m in matchers))
    return {
        "runtime": rt,
        "has_hook": has_hook,
        "required_tools": list(required),
        "missing_tools": missing,
        "unmatched_aliases": unmatched_aliases,
        "explicit_missing_matcher": explicit_missing_matcher,
        "is_superset": has_hook and not missing and not unmatched_aliases and not explicit_missing_matcher,
        "narrowing": narrowing,
    }


def audit_installed_hook_manifests(
    repo_root: Optional[str] = None,
    gates_file: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """Inspect every installed Along hook manifest (global and local) for stale/narrow matchers."""
    home = os.path.expanduser("~")
    candidates: List[Tuple[str, str, str]] = [
        ("antigravity", os.path.join(home, ".gemini", "config", "hooks.json"), "along hook install --runtime antigravity --global"),
        ("claude", os.path.join(home, ".claude", "settings.json"), "along hook install --runtime claude --global"),
        ("codex", os.path.join(home, ".codex", "hooks.json"), "along hook install --runtime codex --global"),
        ("cursor", os.path.join(home, ".cursor", "hooks.json"), "along hook install --runtime cursor --global"),
    ]
    dsh_base = os.environ.get("DSH_HOME") or os.path.join(home, ".dsh")
    dsh_profiles = os.path.join(dsh_base, "profiles")
    if os.path.isdir(dsh_profiles):
        try:
            for entry in sorted(os.listdir(dsh_profiles)):
                cand = os.path.join(dsh_profiles, entry, DSH_HOOKS_FILE_NAME)
                if os.path.isfile(cand):
                    candidates.append(("dsh", cand, "along hook install --runtime dsh --global"))
        except OSError:
            pass
    if repo_root:
        candidates.extend([
            ("antigravity", os.path.join(repo_root, ".agents", "hooks.json"), "along hook install --runtime antigravity"),
            ("claude", os.path.join(repo_root, ".claude", "settings.json"), "along hook install --runtime claude"),
            ("claude", os.path.join(repo_root, ".claude", "settings.local.json"), "along hook install --runtime claude"),
            ("codex", os.path.join(repo_root, ".codex", "hooks.json"), "along hook install --runtime codex"),
            ("cursor", os.path.join(repo_root, ".cursor", "hooks.json"), "along hook install --runtime cursor"),
            ("dsh", os.path.join(repo_root, ".dsh", DSH_HOOKS_FILE_NAME), "along hook install --runtime dsh"),
        ])

    results: List[Dict[str, Any]] = []
    seen_paths = set()
    for rt, path, remediation in candidates:
        norm = os.path.normcase(os.path.abspath(path))
        if norm in seen_paths or not os.path.isfile(path):
            continue
        seen_paths.add(norm)
        try:
            content = textio.read_text(path, strict=False)
            if not content.strip():
                continue
            data = json.loads(content)
        except (OSError, ValueError):
            continue
        audit = audit_manifest_coverage(rt, data, gates_file=gates_file)
        if not audit["has_hook"]:
            continue
        audit["path"] = path
        audit["remediation"] = remediation
        results.append(audit)
    return results


def get_antigravity_hook_manifest(
    is_global: bool = False,
    gates_file: Optional[str] = None,
) -> Dict[str, Any]:
    """Canonical hook configuration dictionary for Google Antigravity."""
    pre_matcher = build_pre_tool_matcher(gates_file=gates_file)
    post_matcher = build_post_tool_matcher(gates_file=gates_file)
    return {
        "along-runtime-gates": {
            "PreToolUse": [
                {
                    "matcher": pre_matcher,
                    "hooks": [
                        {
                            "type": "command",
                            "command": get_hook_command("antigravity", "PreToolUse", is_global=is_global),
                            "timeout": 15,
                        }
                    ],
                }
            ],
            "PostToolUse": [
                {
                    "matcher": post_matcher,
                    "hooks": [
                        {
                            "type": "command",
                            "command": get_hook_command("antigravity", "PostToolUse", is_global=is_global),
                            "timeout": 15,
                        }
                    ],
                }
            ],
        }
    }


def install_antigravity_hooks(
    repo_root: Optional[str] = None,
    dry_run: bool = False,
    is_global: bool = False,
    target_home: Optional[str] = None,
) -> Tuple[str, str]:
    """Scaffold or update hooks.json for Antigravity globally or in repo_root."""
    if is_global:
        agents_dir = target_home or os.path.expanduser("~/.gemini/config")
    else:
        if not repo_root:
            return "failed", "repo_root is required for local hook install"
        agents_dir = os.path.join(repo_root, ".agents")
    hooks_file = os.path.join(agents_dir, "hooks.json")

    existing: Dict[str, Any] = {}
    if os.path.isfile(hooks_file):
        try:
            content = textio.read_text(hooks_file, strict=False)
            if content.strip():
                existing = json.loads(content)
                if not isinstance(existing, dict):
                    return "failed", f"left {hooks_file} alone: top-level is not a JSON object"
        except (OSError, ValueError) as exc:
            return "failed", f"left {hooks_file} alone: cannot parse JSON ({exc})"

    spec = get_antigravity_hook_manifest(is_global=is_global)
    gate_key = "along-runtime-gates"
    if existing.get(gate_key) == spec[gate_key]:
        return "present", f"{hooks_file}: already up to date"

    if dry_run:
        return "dry-run", f"would update {hooks_file} with {gate_key}"

    existing[gate_key] = spec[gate_key]
    os.makedirs(agents_dir, exist_ok=True)
    textio.write_text(hooks_file, json.dumps(existing, indent=2) + "\n", newline="\n")
    return "installed", f"updated {hooks_file} with {gate_key}"


#: Seconds Claude Code waits for one Along hook process before it gives up on it.
CLAUDE_HOOK_TIMEOUT: int = 30

#: Claude Code tools the PreToolUse gates inspect: Claude aliases plus the catalogue
#: runtime gate tool union.
CLAUDE_PRE_TOOL_MATCHER: str = build_pre_tool_matcher(CLAUDE_PRE_TOOL_ALIASES)

#: PostToolUse: edits, shells, and ExitPlanMode (the user accepted a plan).
CLAUDE_POST_TOOL_MATCHER: str = build_post_tool_matcher(CLAUDE_POST_TOOL_ALIASES)


def hook_entry_commands(item: Any) -> List[str]:
    """Every command string of a hook entry, flat (`command`) or nested (`hooks[].command`)."""
    commands: List[str] = []
    if not isinstance(item, dict):
        return commands
    if "command" in item:
        commands.append(str(item.get("command", "")))
    inner = item.get("hooks")
    if isinstance(inner, list):
        for hook in inner:
            if isinstance(hook, dict) and "command" in hook:
                commands.append(str(hook.get("command", "")))
    return commands


_HOOK_EVENT_ALIASES: Dict[str, Tuple[str, ...]] = {
    "beforesubmitprompt": ("userpromptsubmit", "beforesubmitprompt"),
}


def is_along_hook_entry(item: Any, event_name: Optional[str] = None) -> bool:
    """True when a hook entry (either schema) runs along_hook.py, for `event_name` if given."""
    targets: Optional[Tuple[str, ...]] = None
    if event_name is not None:
        key = event_name.lower()
        targets = tuple(f"--event {name}".lower() for name in _HOOK_EVENT_ALIASES.get(key, (key,)))
    for command in hook_entry_commands(item):
        if "along_hook.py" not in command:
            continue
        if targets is None:
            return True
        lowered = command.lower()
        if any(target in lowered for target in targets):
            return True
    return False


def _strip_along_hooks(entries: List[Any]) -> Tuple[List[Any], bool]:
    """Remove Along commands from a hook event list, keeping every foreign hook.

    A nested entry that mixes Along and foreign commands keeps its foreign commands.
    """
    kept: List[Any] = []
    modified = False
    for item in entries:
        if not is_along_hook_entry(item):
            kept.append(item)
            continue
        modified = True
        inner = item.get("hooks") if isinstance(item, dict) else None
        if isinstance(inner, list) and "command" not in item:
            foreign = [h for h in inner if not (isinstance(h, dict) and "along_hook.py" in str(h.get("command", "")))]
            if foreign:
                kept.append({**item, "hooks": foreign})
    return kept, modified


def _claude_entry(event: str, matcher: Optional[str], is_global: bool) -> Dict[str, Any]:
    entry: Dict[str, Any] = {}
    if matcher:
        entry["matcher"] = matcher
    entry["hooks"] = [{
        "type": "command",
        "command": get_hook_command("claude", event, is_global=is_global),
        "timeout": CLAUDE_HOOK_TIMEOUT,
    }]
    return entry


def get_claude_hook_manifest(
    is_global: bool = False,
    gates_file: Optional[str] = None,
) -> Dict[str, Any]:
    """Canonical hook configuration for Anthropic Claude Code (.claude/settings.json).

    Claude Code reads only the nested schema `{matcher, hooks: [{type, command, timeout}]}`;
    a flat `{matcher, command}` entry is ignored. See [bug--claude-hook-manifest-flat-schema].
    """
    pre_matcher = build_pre_tool_matcher(CLAUDE_PRE_TOOL_ALIASES, gates_file=gates_file) if gates_file else CLAUDE_PRE_TOOL_MATCHER
    post_matcher = build_post_tool_matcher(CLAUDE_POST_TOOL_ALIASES, gates_file=gates_file) if gates_file else CLAUDE_POST_TOOL_MATCHER
    return {
        "PreToolUse": [_claude_entry("PreToolUse", pre_matcher, is_global)],
        "PostToolUse": [_claude_entry("PostToolUse", post_matcher, is_global)],
        "Stop": [_claude_entry("Stop", None, is_global)],
        # Timestamp of the user's last message: CLI plan approval and gate bypasses are
        # checked against it. [bug--plan-approval-self-and-lost]
        "UserPromptSubmit": [_claude_entry("UserPromptSubmit", None, is_global)],
    }


def install_claude_hooks(
    repo_root: Optional[str] = None,
    dry_run: bool = False,
    is_global: bool = False,
    target_home: Optional[str] = None,
) -> Tuple[str, str]:
    """Scaffold or update settings.json for Claude Code globally or in repo_root."""
    if is_global:
        claude_dir = target_home or os.path.expanduser("~/.claude")
    else:
        if not repo_root:
            return "failed", "repo_root is required for local hook install"
        claude_dir = os.path.join(repo_root, ".claude")
    settings_file = os.path.join(claude_dir, "settings.json")

    existing: Dict[str, Any] = {}
    if os.path.isfile(settings_file):
        try:
            content = textio.read_text(settings_file, strict=False)
            if content.strip():
                existing = json.loads(content)
                if not isinstance(existing, dict):
                    return "failed", f"left {settings_file} alone: top-level is not a JSON object"
        except (OSError, ValueError) as exc:
            return "failed", f"left {settings_file} alone: cannot parse JSON ({exc})"

    spec = get_claude_hook_manifest(is_global=is_global)
    existing_hooks = existing.get("hooks")
    if not isinstance(existing_hooks, dict):
        existing_hooks = {}
        existing["hooks"] = existing_hooks

    changed = False
    for event_name, hook_list in spec.items():
        cur_list = existing_hooks.get(event_name)
        if not isinstance(cur_list, list):
            cur_list = []
            existing_hooks[event_name] = cur_list
            changed = True

        # One Along entry per event, in the nested schema: legacy flat entries and
        # duplicates are replaced in place, foreign hooks keep their position.
        along_idx = [i for i, item in enumerate(cur_list) if is_along_hook_entry(item, event_name)]
        expected_hook = hook_list[0]
        if not along_idx:
            cur_list.append(expected_hook)
            changed = True
        else:
            if cur_list[along_idx[0]] != expected_hook:
                cur_list[along_idx[0]] = expected_hook
                changed = True
            for idx in reversed(along_idx[1:]):
                del cur_list[idx]
                changed = True

    # Keep AI co-author trailers out of commits [gate: commit-no-ai-coauthor].
    if not attribution.allow_ai_coauthor(repo_root):
        changed = attribution.apply_claude_attribution(existing) or changed

    if not changed:
        return "present", f"{settings_file}: already up to date"

    if dry_run:
        return "dry-run", f"would update {settings_file} with Along hooks"

    os.makedirs(claude_dir, exist_ok=True)
    textio.write_text(settings_file, json.dumps(existing, indent=2) + "\n", newline="\n")
    return "installed", f"updated {settings_file} with Along hooks"



def get_codex_hook_manifest(
    is_global: bool = False,
    gates_file: Optional[str] = None,
) -> Dict[str, Any]:
    """Canonical hook configuration dictionary for OpenAI Codex (.codex/hooks.json)."""
    pre_matcher = build_pre_tool_matcher(CODEX_PRE_TOOL_ALIASES, gates_file=gates_file)
    post_matcher = build_post_tool_matcher(CODEX_POST_TOOL_ALIASES, gates_file=gates_file)
    return {
        "hooks": {
            "PreToolUse": [
                {
                    "matcher": pre_matcher,
                    "command": get_hook_command("codex", "PreToolUse", is_global=is_global),
                }
            ],
            "PostToolUse": [
                {
                    "matcher": post_matcher,
                    "command": get_hook_command("codex", "PostToolUse", is_global=is_global),
                }
            ],
            "Stop": [
                {
                    "command": get_hook_command("codex", "Stop", is_global=is_global),
                }
            ],
        }
    }


def install_codex_hooks(
    repo_root: Optional[str] = None,
    dry_run: bool = False,
    is_global: bool = False,
    target_home: Optional[str] = None,
) -> Tuple[str, str]:
    """Scaffold or update hooks.json for OpenAI Codex globally or in repo_root."""
    if is_global:
        codex_dir = target_home or os.path.expanduser("~/.codex")
    else:
        if not repo_root:
            return "failed", "repo_root is required for local hook install"
        codex_dir = os.path.join(repo_root, ".codex")
    hooks_file = os.path.join(codex_dir, "hooks.json")

    existing: Dict[str, Any] = {}
    if os.path.isfile(hooks_file):
        try:
            content = textio.read_text(hooks_file, strict=False)
            if content.strip():
                existing = json.loads(content)
                if not isinstance(existing, dict):
                    return "failed", f"left {hooks_file} alone: top-level is not a JSON object"
        except (OSError, ValueError) as exc:
            return "failed", f"left {hooks_file} alone: cannot parse JSON ({exc})"

    spec = get_codex_hook_manifest(is_global=is_global)
    spec_hooks = spec.get("hooks", {})

    hooks_container: Dict[str, Any]
    if "hooks" in existing and isinstance(existing["hooks"], dict):
        hooks_container = existing["hooks"]
    elif any(k in existing for k in ("PreToolUse", "PostToolUse", "Stop")):
        hooks_container = existing
    else:
        if not isinstance(existing.get("hooks"), dict):
            existing["hooks"] = {}
        hooks_container = existing["hooks"]

    changed = False
    for event_name, hook_list in spec_hooks.items():
        cur_list = hooks_container.get(event_name)
        if not isinstance(cur_list, list):
            cur_list = []
            hooks_container[event_name] = cur_list
            changed = True

        for expected_hook in hook_list:
            matched_idx = -1
            for idx, item in enumerate(cur_list):
                if is_along_hook_entry(item, event_name):
                    matched_idx = idx
                    break

            if matched_idx >= 0:
                if cur_list[matched_idx] != expected_hook:
                    cur_list[matched_idx] = expected_hook
                    changed = True
            else:
                cur_list.append(expected_hook)
                changed = True

    if not changed:
        return "present", f"{hooks_file}: already up to date"

    if dry_run:
        return "dry-run", f"would update {hooks_file} with Along hooks"

    os.makedirs(codex_dir, exist_ok=True)
    textio.write_text(hooks_file, json.dumps(existing, indent=2) + "\n", newline="\n")
    return "installed", f"updated {hooks_file} with Along hooks"


def get_cursor_hook_manifest(
    is_global: bool = False,
    gates_file: Optional[str] = None,
) -> Dict[str, Any]:
    """Canonical hook configuration dictionary for Cursor (.cursor/hooks.json).

    Includes explicit `preToolUse`/`postToolUse` matchers covering Cursor's native tool
    names and the catalogue runtime gate union. Remaining Cursor platform narrowings
    (unexpressible tools, no native ASK, advisory installer default) are recorded in
    `RUNTIME_HOOK_NARROWINGS['cursor']` and reported by `along doctor`.
    """
    pre_matcher = build_pre_tool_matcher(CURSOR_PRE_TOOL_ALIASES, gates_file=gates_file)
    post_matcher = build_post_tool_matcher(CURSOR_POST_TOOL_ALIASES, gates_file=gates_file)
    return {
        "version": 1,
        "hooks": {
            "preToolUse": [
                {
                    "matcher": pre_matcher,
                    "command": get_hook_command("cursor", "PreToolUse", is_global=is_global),
                }
            ],
            "postToolUse": [
                {
                    "matcher": post_matcher,
                    "command": get_hook_command("cursor", "PostToolUse", is_global=is_global),
                }
            ],
            "stop": [
                {
                    "command": get_hook_command("cursor", "Stop", is_global=is_global),
                }
            ],
            "beforeSubmitPrompt": [
                {
                    "command": get_hook_command("cursor", "UserPromptSubmit", is_global=is_global),
                }
            ],
        },
    }


def install_cursor_hooks(
    repo_root: Optional[str] = None,
    dry_run: bool = False,
    is_global: bool = False,
    target_home: Optional[str] = None,
) -> Tuple[str, str]:
    """Scaffold or update hooks.json for Cursor globally or in repo_root."""
    if is_global:
        cursor_dir = target_home or os.path.expanduser("~/.cursor")
    else:
        if not repo_root:
            return "failed", "repo_root is required for local hook install"
        cursor_dir = os.path.join(repo_root, ".cursor")
    hooks_file = os.path.join(cursor_dir, "hooks.json")

    existing: Dict[str, Any] = {}
    if os.path.isfile(hooks_file):
        try:
            content = textio.read_text(hooks_file, strict=False)
            if content.strip():
                existing = json.loads(content)
                if not isinstance(existing, dict):
                    return "failed", f"left {hooks_file} alone: top-level is not a JSON object"
        except (OSError, ValueError) as exc:
            return "failed", f"left {hooks_file} alone: cannot parse JSON ({exc})"

    spec = get_cursor_hook_manifest(is_global=is_global)
    spec_hooks = spec.get("hooks", {})

    changed = False
    if "version" not in existing:
        existing["version"] = 1
        changed = True

    hooks_container = existing.get("hooks")
    if not isinstance(hooks_container, dict):
        hooks_container = {}
        existing["hooks"] = hooks_container

    for event_name, hook_list in spec_hooks.items():
        cur_list = hooks_container.get(event_name)
        if not isinstance(cur_list, list):
            cur_list = []
            hooks_container[event_name] = cur_list
            changed = True

        for expected_hook in hook_list:
            matched_idx = -1
            for idx, item in enumerate(cur_list):
                if is_along_hook_entry(item, event_name):
                    matched_idx = idx
                    break

            if matched_idx >= 0:
                if cur_list[matched_idx] != expected_hook:
                    cur_list[matched_idx] = expected_hook
                    changed = True
            else:
                cur_list.append(expected_hook)
                changed = True

    # Cursor reads commit attribution from the user-level cli-config.json only.
    if is_global and not attribution.allow_ai_coauthor(repo_root):
        attr_status, attr_msg = _install_cursor_attribution(cursor_dir, dry_run=dry_run)
        if attr_status == "failed":
            return attr_status, attr_msg

    if not changed:
        return "present", f"{hooks_file}: already up to date"

    if dry_run:
        return "dry-run", f"would update {hooks_file} with Along hooks"

    os.makedirs(cursor_dir, exist_ok=True)
    textio.write_text(hooks_file, json.dumps(existing, indent=2) + "\n", newline="\n")
    return "installed", f"updated {hooks_file} with Along hooks"


def install_opencode_hooks(
    repo_root: Optional[str] = None,
    dry_run: bool = False,
    is_global: bool = False,
    target_home: Optional[str] = None,
) -> Tuple[str, str]:
    """Scaffold or update along-gates.js plugin for OpenCode globally or in repo_root."""
    if is_global:
        base_dir = target_home or os.path.expanduser("~/.config/opencode")
    else:
        if not repo_root:
            return "failed", "repo_root is required for local hook install"
        base_dir = os.path.join(repo_root, ".opencode")

    plugins_dir = os.path.join(base_dir, "plugins")
    plugin_file = os.path.join(plugins_dir, "along-gates.js")

    src_plugin = os.path.join(os.path.dirname(__file__), "opencode_plugin.js")
    if not os.path.isfile(src_plugin):
        return "failed", f"Source plugin template not found: {src_plugin}"

    try:
        plugin_content = textio.read_text(src_plugin, strict=False)
    except OSError as exc:
        return "failed", f"cannot read {src_plugin}: {exc}"

    # REQ-10: validate registered hook names against the OpenCode runtime contract before installing
    from .. import runtime as along_runtime
    contract = along_runtime.load_opencode_contract(repo_root)
    valid_by_domain = {
        "tool": set(contract.get("tool_hooks") or []),
        "session": set(contract.get("session_hooks") or []),
        "shell": set(contract.get("shell_hooks") or []),
    }
    invalid_hooks: List[str] = []
    for domain, hook_name in re.findall(r"(tool|session|shell)\.hook\(\s*[\"']([^\"']+)[\"']", plugin_content):
        if hook_name not in valid_by_domain.get(domain, set()):
            invalid_hooks.append(f"{domain}.{hook_name}")
    if invalid_hooks:
        return "failed", f"OpenCode plugin registers unsupported hook(s) for {contract.get('version', '2.3.2')}: {', '.join(invalid_hooks)}"

    pruned_msg = ""
    if is_global and repo_root and not dry_run:
        proj_plugin = os.path.join(repo_root, ".opencode", "plugins", "along-gates.js")
        if os.path.isfile(proj_plugin):
            try:
                proj_text = textio.read_text(proj_plugin, strict=False)
                if "along-gates" in proj_text:
                    os.remove(proj_plugin)
                    pruned_msg = f" (pruned duplicate project plugin {proj_plugin})"
            except OSError:
                pass

    if os.path.isfile(plugin_file):
        try:
            existing = textio.read_text(plugin_file, strict=False)
            if existing.replace("\r\n", "\n") == plugin_content.replace("\r\n", "\n"):
                return "present", f"{plugin_file}: already up to date{pruned_msg}"
        except OSError:
            pass

    if dry_run:
        return "dry-run", f"{plugin_file}: would install OpenCode Along plugin"

    try:
        os.makedirs(plugins_dir, exist_ok=True)
        legacy_file = os.path.join(plugins_dir, "along-opencode-plugin.js")
        if os.path.isfile(legacy_file):
            try:
                os.remove(legacy_file)
            except OSError:
                pass
        textio.write_text(plugin_file, plugin_content, newline="\n")
        return "installed", f"{plugin_file}: installed OpenCode Along plugin{pruned_msg}"
    except OSError as exc:
        return "failed", f"cannot write {plugin_file}: {exc}"


#: DeepSeek Harness tool names the PreToolUse gates inspect. The bridge reads a
#: pipe-separated pattern as literal alternatives matched against the harness tool name, so
#: these must be the model-facing names (`read`, `write`, `pwsh`, ...) plus the catalogue
#: runtime gate tool union, never the Claude Code capitalised ones (`Read`, `Write`, `Bash`),
#: which match nothing there.
DSH_PRE_TOOL_MATCHER: str = build_pre_tool_matcher(
    DSH_PRE_TOOL_ALIASES,
    exclude=_DSH_FORBIDDEN_CLAUDE_NAMES,
)

#: PostToolUse: mutations, shells, and the plan-exit signal.
DSH_POST_TOOL_MATCHER: str = build_post_tool_matcher(
    DSH_POST_TOOL_ALIASES,
    exclude=_DSH_FORBIDDEN_CLAUDE_NAMES,
)

#: File the bridge mounts: inside the profile for a global install, `<repo>/.dsh` locally.
DSH_HOOKS_FILE_NAME: str = "along-hooks.json"


def _dsh_entry(event: str, matcher: Optional[str], is_global: bool) -> Dict[str, Any]:
    entry: Dict[str, Any] = {}
    if matcher:
        entry["matcher"] = matcher
    entry["hooks"] = [{
        "type": "command",
        "command": get_hook_command("dsh", event, is_global=is_global),
        "timeout": CLAUDE_HOOK_TIMEOUT,
    }]
    return entry


def get_dsh_hook_manifest(
    is_global: bool = False,
    gates_file: Optional[str] = None,
) -> Dict[str, Any]:
    """Hooks file mounted into DeepSeek Harness by the Claude-dialect bridge.

    A DSH-specific matcher list, not the Claude one: the harness matches the pattern against
    its own tool names, so a Claude Code manifest admits nothing.
    See [bug--dsh-tool-name-map-and-ask-capability].
    """
    pre_matcher = (
        build_pre_tool_matcher(DSH_PRE_TOOL_ALIASES, gates_file=gates_file, exclude=_DSH_FORBIDDEN_CLAUDE_NAMES)
        if gates_file else DSH_PRE_TOOL_MATCHER
    )
    post_matcher = (
        build_post_tool_matcher(DSH_POST_TOOL_ALIASES, gates_file=gates_file, exclude=_DSH_FORBIDDEN_CLAUDE_NAMES)
        if gates_file else DSH_POST_TOOL_MATCHER
    )
    return {
        "hooks": {
            "PreToolUse": [_dsh_entry("PreToolUse", pre_matcher, is_global)],
            "PostToolUse": [_dsh_entry("PostToolUse", post_matcher, is_global)],
            "Stop": [_dsh_entry("Stop", None, is_global)],
            "UserPromptSubmit": [_dsh_entry("UserPromptSubmit", None, is_global)],
        }
    }


def _write_dsh_hooks_file(path: str, is_global: bool = False,
                          dry_run: bool = False) -> Tuple[str, str]:
    """Write the hooks file the bridge mounts, idempotently."""
    payload = json.dumps(get_dsh_hook_manifest(is_global=is_global), indent=2) + "\n"
    if os.path.isfile(path):
        try:
            existing = textio.read_text(path, strict=False)
        except OSError:
            existing = ""
        if existing.replace("\r\n", "\n") == payload:
            return "present", f"{path}: already up to date"
    if dry_run:
        return "dry-run", f"would write {path}"
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        textio.write_text(path, payload, newline="\n")
    except OSError as exc:
        return "failed", f"cannot write {path}: {exc}"
    return "installed", f"updated {path}"


def install_dsh_hooks(
    repo_root: Optional[str] = None,
    dry_run: bool = False,
    is_global: bool = False,
    target_home: Optional[str] = None,
) -> Tuple[str, str]:
    """Scaffold or update cordis.patch.yml for DeepSeek Harness (DSH)."""
    from .. import bootstrap
    ruamel = bootstrap.require("ruamel.yaml")
    yaml = ruamel.YAML()
    yaml.default_flow_style = False

    if is_global:
        base_dir = target_home or os.environ.get("DSH_HOME") or os.path.expanduser("~/.dsh")
        profiles_dir = os.path.join(base_dir, "profiles")
        candidate_dirs: List[str] = []
        if os.path.isdir(profiles_dir):
            for entry in os.listdir(profiles_dir):
                full_entry = os.path.join(profiles_dir, entry)
                if os.path.isdir(full_entry):
                    candidate_dirs.append(full_entry)
        if not candidate_dirs:
            candidate_dirs.append(os.path.join(profiles_dir, "desktop"))
    else:
        if not repo_root:
            return "failed", "repo_root is required for local hook install"
        candidate_dirs = [os.path.join(repo_root, ".dsh")]

    changed_any = False
    messages: List[str] = []
    statuses: List[str] = []

    for cdir in candidate_dirs:
        # The bridge mounts this file, so it must exist and carry the DSH matcher; pointing
        # the bridge at the Claude manifest admitted no harness tool name at all.
        hooks_file = os.path.join(cdir, DSH_HOOKS_FILE_NAME)
        config_path = os.path.abspath(hooks_file).replace("\\", "/") if is_global else ("./.dsh/" + DSH_HOOKS_FILE_NAME)
        expected_patch = {
            "id": "along-hooks-bridge",
            "name": "@deepseek-ai/dsh-hooks-claude-code",
            "config": {
                "configPath": config_path,
            },
        }
        hooks_status, hooks_message = _write_dsh_hooks_file(hooks_file, is_global=is_global, dry_run=dry_run)
        messages.append(hooks_message)
        statuses.append(hooks_status)
        patch_file = os.path.join(cdir, "cordis.patch.yml")
        existing_entries: List[Any] = []
        if os.path.isfile(patch_file):
            try:
                content = textio.read_text(patch_file, strict=False)
                if content.strip():
                    loaded = yaml.load(content)
                    if isinstance(loaded, list):
                        existing_entries = loaded
                    elif isinstance(loaded, dict):
                        existing_entries = [loaded]
            except (OSError, ValueError, TypeError, KeyError, AttributeError) as exc:
                messages.append(f"left {patch_file} alone: cannot parse YAML ({exc})")
                statuses.append("failed")
                continue

        matched_idx = -1
        for idx, item in enumerate(existing_entries):
            if isinstance(item, dict) and item.get("id") == "along-hooks-bridge":
                matched_idx = idx
                break

        changed = False
        if matched_idx >= 0:
            cur_item = existing_entries[matched_idx]
            cur_config = cur_item.get("config") if isinstance(cur_item, dict) else None
            if cur_item.get("name") != expected_patch["name"] or cur_config != expected_patch["config"]:
                existing_entries[matched_idx] = dict(expected_patch)
                changed = True
        else:
            existing_entries.append(dict(expected_patch))
            changed = True

        if not changed:
            messages.append(f"{patch_file}: already up to date")
            statuses.append("present")
            continue

        changed_any = True
        if dry_run:
            messages.append(f"would update {patch_file} with Along DSH hook bridge")
            statuses.append("dry-run")
            continue

        try:
            os.makedirs(cdir, exist_ok=True)
            import io
            buf = io.StringIO()
            yaml.dump(existing_entries, buf)
            textio.write_text(patch_file, buf.getvalue(), newline="\n")
            messages.append(f"updated {patch_file} with Along DSH hook bridge")
            statuses.append("installed")
        except OSError as exc:
            messages.append(f"cannot write {patch_file}: {exc}")
            statuses.append("failed")

    if any(s == "failed" for s in statuses):
        return "failed", "; ".join(messages)
    if any(s == "installed" for s in statuses):
        return "installed", "; ".join(messages)
    if any(s == "dry-run" for s in statuses):
        return "dry-run", "; ".join(messages)
    return "present", "; ".join(messages) if messages else "no DSH profiles configured"



def _apply_json_settings(
    config_file: str,
    apply: Callable[[Dict[str, Any]], bool],
    dry_run: bool = False,
) -> Tuple[str, str]:
    """Merge settings into a JSON object file through `apply`, keeping every other key."""
    existing: Dict[str, Any] = {}
    if os.path.isfile(config_file):
        try:
            content = textio.read_text(config_file, strict=False)
            if content.strip():
                existing = json.loads(content)
                if not isinstance(existing, dict):
                    return "failed", f"left {config_file} alone: top-level is not a JSON object"
        except (OSError, ValueError) as exc:
            return "failed", f"left {config_file} alone: cannot parse JSON ({exc})"

    if not apply(existing):
        return "present", f"{config_file}: attribution already up to date"
    if dry_run:
        return "dry-run", f"would update {config_file} with attribution settings"
    os.makedirs(os.path.dirname(config_file), exist_ok=True)
    textio.write_text(config_file, json.dumps(existing, indent=2) + "\n", newline="\n")
    return "installed", f"updated {config_file} with attribution settings"


def _install_cursor_attribution(cursor_dir: str, dry_run: bool = False) -> Tuple[str, str]:
    """Turn off agent commit attribution in Cursor `cli-config.json` [gate: commit-no-ai-coauthor]."""
    return _apply_json_settings(
        os.path.join(cursor_dir, "cli-config.json"), attribution.apply_cursor_attribution, dry_run
    )


def reconcile_attribution(
    claude_home: Optional[str] = None,
    cursor_home: Optional[str] = None,
    dry_run: bool = False,
    repo_root: Optional[str] = None,
    runtimes: Tuple[str, ...] = ("claude", "cursor"),
) -> List[Tuple[str, str]]:
    """Turn off AI commit attribution in every installed runtime's user-level config.

    Only touches a runtime whose home directory already exists, so nothing is created
    for a runtime the user does not have. Writes only the attribution keys, never hooks.
    Called by `along-update` and the installers [gate: commit-no-ai-coauthor].
    """
    if attribution.allow_ai_coauthor(repo_root):
        return [("present", "attribution left alone: commits.allow_ai_coauthor is true")]
    claude_home = claude_home or os.path.expanduser("~/.claude")
    cursor_home = cursor_home or os.path.expanduser("~/.cursor")
    results: List[Tuple[str, str]] = []
    if "claude" in runtimes and os.path.isdir(claude_home):
        results.append(_apply_json_settings(
            os.path.join(claude_home, "settings.json"), attribution.apply_claude_attribution, dry_run
        ))
    if "cursor" in runtimes and os.path.isdir(cursor_home):
        results.append(_install_cursor_attribution(cursor_home, dry_run=dry_run))
    return results


def purge_local_along_hooks(repo_root: str, recursive: bool = True, dry_run: bool = False) -> List[str]:
    """Purge spurious local Along hooks and workaround scripts from a consumer repository and its subprojects."""
    actions: List[str] = []
    if not repo_root or not os.path.isdir(repo_root):
        return actions

    contexts = [os.path.abspath(repo_root)]
    if recursive:
        try:
            # Installations, plus folders an older Along version initialized (a managed protocol
            # block in their AGENTS.md): both may hold hooks Along wrote and must remove.
            for c in repo.find_agent_contexts(repo_root) + repo.find_managed_agents_md_dirs(repo_root):
                abs_c = os.path.abspath(c)
                if abs_c not in contexts:
                    contexts.append(abs_c)
        except (OSError, ValueError):
            pass

    for ctx in contexts:
        # 1. Purge .agents/hooks.json
        agents_hooks = os.path.join(ctx, ".agents", "hooks.json")
        if os.path.isfile(agents_hooks):
            try:
                content = textio.read_text(agents_hooks, strict=False)
                data = json.loads(content) if content.strip() else {}
                if isinstance(data, dict) and "along-runtime-gates" in data:
                    del data["along-runtime-gates"]
                    if not data:
                        if not dry_run:
                            os.remove(agents_hooks)
                        actions.append(f"removed {agents_hooks}")
                        # Note: We do not remove agents_dir (.agents) even if empty, because active
                        # agent processes (e.g. Antigravity) may hold in-memory hook registrations
                        # with cwd set to this directory; deleting it causes OS-level chdir failures.
                    else:
                        if not dry_run:
                            textio.write_text(agents_hooks, json.dumps(data, indent=2) + "\n", newline="\n")
                        actions.append(f"cleaned along-runtime-gates from {agents_hooks}")
            except (OSError, ValueError):
                pass

        # 2. Purge .claude/settings.json
        claude_settings = os.path.join(ctx, ".claude", "settings.json")
        if os.path.isfile(claude_settings):
            try:
                content = textio.read_text(claude_settings, strict=False)
                data = json.loads(content) if content.strip() else {}
                if isinstance(data, dict) and "hooks" in data and isinstance(data["hooks"], dict):
                    modified = False
                    for ev in list(data["hooks"].keys()):
                        ev_list = data["hooks"][ev]
                        if isinstance(ev_list, list):
                            new_list, ev_modified = _strip_along_hooks(ev_list)
                            if ev_modified:
                                modified = True
                                if new_list:
                                    data["hooks"][ev] = new_list
                                else:
                                    del data["hooks"][ev]
                    if modified:
                        if not data["hooks"]:
                            del data["hooks"]
                        if not data:
                            if not dry_run:
                                os.remove(claude_settings)
                            actions.append(f"removed {claude_settings}")
                            # Note: preserve .claude directory to protect active Claude processes
                        else:
                            if not dry_run:
                                textio.write_text(claude_settings, json.dumps(data, indent=2) + "\n", newline="\n")
                            actions.append(f"cleaned Along hooks from {claude_settings}")
            except (OSError, ValueError):
                pass

        # 3. Purge .codex/hooks.json
        codex_hooks = os.path.join(ctx, ".codex", "hooks.json")
        if os.path.isfile(codex_hooks):
            try:
                content = textio.read_text(codex_hooks, strict=False)
                data = json.loads(content) if content.strip() else {}
                if isinstance(data, dict):
                    hooks_dict = data.get("hooks", data)
                    modified = False
                    for ev in list(hooks_dict.keys()):
                        ev_list = hooks_dict[ev]
                        if isinstance(ev_list, list):
                            new_list, ev_modified = _strip_along_hooks(ev_list)
                            if ev_modified:
                                modified = True
                                if new_list:
                                    hooks_dict[ev] = new_list
                                else:
                                    del hooks_dict[ev]
                    if modified:
                        if "hooks" in data and not data["hooks"]:
                            del data["hooks"]
                        if not data or (len(data) == 1 and "hooks" in data and not data["hooks"]):
                            if not dry_run:
                                os.remove(codex_hooks)
                            actions.append(f"removed {codex_hooks}")
                            # Note: preserve .codex directory to protect active Codex processes
                        else:
                            if not dry_run:
                                textio.write_text(codex_hooks, json.dumps(data, indent=2) + "\n", newline="\n")
                            actions.append(f"cleaned Along hooks from {codex_hooks}")
            except (OSError, ValueError):
                pass

        # 4. Purge .cursor/hooks.json
        cursor_hooks = os.path.join(ctx, ".cursor", "hooks.json")
        if os.path.isfile(cursor_hooks):
            try:
                content = textio.read_text(cursor_hooks, strict=False)
                data = json.loads(content) if content.strip() else {}
                if isinstance(data, dict) and "hooks" in data and isinstance(data["hooks"], dict):
                    modified = False
                    for ev in list(data["hooks"].keys()):
                        ev_list = data["hooks"][ev]
                        if isinstance(ev_list, list):
                            new_list, ev_modified = _strip_along_hooks(ev_list)
                            if ev_modified:
                                modified = True
                                if new_list:
                                    data["hooks"][ev] = new_list
                                else:
                                    del data["hooks"][ev]
                    if modified:
                        if not data["hooks"]:
                            del data["hooks"]
                        keys_left = [k for k in data.keys() if k != "version"]
                        if not keys_left:
                            if not dry_run:
                                os.remove(cursor_hooks)
                            actions.append(f"removed {cursor_hooks}")
                            # Note: preserve .cursor directory to protect active Cursor processes
                        else:
                            if not dry_run:
                                textio.write_text(cursor_hooks, json.dumps(data, indent=2) + "\n", newline="\n")
                            actions.append(f"cleaned Along hooks from {cursor_hooks}")
            except (OSError, ValueError):
                pass

        # 5. Purge workaround scripts/along_hook.py or .along/scripts/along_hook.py in consumer repos
        if not repo.is_dev_repo(ctx):
            for candidate_script in [
                os.path.join(ctx, "scripts", "along_hook.py"),
                os.path.join(ctx, ".along", "scripts", "along_hook.py"),
            ]:
                if os.path.isfile(candidate_script):
                    try:
                        if not dry_run:
                            os.remove(candidate_script)
                        actions.append(f"removed workaround {candidate_script}")
                        s_dir = os.path.dirname(candidate_script)
                        if not dry_run and os.path.isdir(s_dir) and not os.listdir(s_dir):
                            os.rmdir(s_dir)
                            actions.append(f"removed empty directory {s_dir}")
                    except OSError:
                        pass

    return actions





