#!/usr/bin/env python3
"""
alongkit.diagnostics - Self-diagnostics, incident recording, and telemetry redaction.

Provides centralized incident tracking across Along Protocol tools without circular imports.
Incidents are safely sanitized and stored under ~/.along/diagnostics/events/<id>.json.
"""

from __future__ import annotations
if __name__ == "__main__":
    import os
    raise SystemExit(
        f"{os.path.basename(__file__)} is a library module, not a command.\n"
        "Run: along feedback   (or: python scripts/along_feedback.py)"
    )

import json
import os
import platform
import re
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from . import version

CURRENT_VERSION = version.CURRENT_VERSION

GLOBAL_ALONG_DIR = os.path.expanduser("~/.along")
DIAGNOSTICS_DIR = os.path.join(GLOBAL_ALONG_DIR, "diagnostics")
EVENTS_DIR = os.path.join(DIAGNOSTICS_DIR, "events")
EXPORT_DIR = os.path.join(DIAGNOSTICS_DIR, "export")
REPORT_FILE = os.path.join(DIAGNOSTICS_DIR, "REPORT.md")
GLOBAL_CONFIG_FILE = os.path.join(GLOBAL_ALONG_DIR, "config.json")

DEFAULT_CONFIG: Dict[str, Any] = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "version": "1.0",
    "telemetry_enabled": True,
    "auto_redact_secrets": True,
    "default_transport": "file",
    "transports": {
        "file": {
            "enabled": True,
            "export_dir": "~/.along/diagnostics/export"
        },
        "telegram": {
            "enabled": False,
            "bot_token": "",
            "chat_id": ""
        },
        "webhook": {
            "enabled": False,
            "url": "",
            "headers": {
                "Content-Type": "application/json"
            }
        }
    }
}


class ConfigManager:
    @staticmethod
    def load_config(repo_root: Optional[str] = None) -> Dict[str, Any]:
        config = dict(DEFAULT_CONFIG)

        # 1. Global config
        if os.path.isfile(GLOBAL_CONFIG_FILE):
            try:
                with open(GLOBAL_CONFIG_FILE, "r", encoding="utf-8") as f:
                    loaded = json.load(f)
                    if isinstance(loaded, dict):
                        config = ConfigManager._deep_merge(config, loaded)
            except (OSError, json.JSONDecodeError, ValueError) as exc:
                print(f"[Warning] Failed to read global config '{GLOBAL_CONFIG_FILE}': {exc}", file=sys.stderr)

        # 2. Repo-local config override if present
        if repo_root:
            local_cfg = os.path.join(repo_root, ".along", "config.json")
            if os.path.isfile(local_cfg):
                try:
                    with open(local_cfg, "r", encoding="utf-8") as f:
                        loaded = json.load(f)
                        if isinstance(loaded, dict):
                            config = ConfigManager._deep_merge(config, loaded)
                except (OSError, json.JSONDecodeError, ValueError) as exc:
                    print(f"[Warning] Failed to read local config '{local_cfg}': {exc}", file=sys.stderr)

        # 3. Environment variable overrides
        if os.environ.get("ALONG_TELEGRAM_BOT_TOKEN"):
            config["transports"]["telegram"]["bot_token"] = os.environ["ALONG_TELEGRAM_BOT_TOKEN"]
            config["transports"]["telegram"]["enabled"] = True
        if os.environ.get("ALONG_TELEGRAM_CHAT_ID"):
            config["transports"]["telegram"]["chat_id"] = os.environ["ALONG_TELEGRAM_CHAT_ID"]
            config["transports"]["telegram"]["enabled"] = True
        if os.environ.get("ALONG_FEEDBACK_WEBHOOK_URL"):
            config["transports"]["webhook"]["url"] = os.environ["ALONG_FEEDBACK_WEBHOOK_URL"]
            config["transports"]["webhook"]["enabled"] = True
        if os.environ.get("ALONG_FEEDBACK_TRANSPORT"):
            config["default_transport"] = os.environ["ALONG_FEEDBACK_TRANSPORT"]
        if os.environ.get("ALONG_TELEMETRY_ENABLED"):
            config["telemetry_enabled"] = os.environ["ALONG_TELEMETRY_ENABLED"].lower() in ("1", "true", "yes")

        return config

    @staticmethod
    def _deep_merge(base: Dict[str, Any], update: Dict[str, Any]) -> Dict[str, Any]:
        res = dict(base)
        for k, v in update.items():
            if isinstance(v, dict) and k in res and isinstance(res[k], dict):
                res[k] = ConfigManager._deep_merge(res[k], v)
            else:
                res[k] = v
        return res

    @staticmethod
    def init_global_config(force: bool = False) -> str:
        os.makedirs(GLOBAL_ALONG_DIR, exist_ok=True)
        if not os.path.exists(GLOBAL_CONFIG_FILE) or force:
            with open(GLOBAL_CONFIG_FILE, "w", encoding="utf-8", newline="\n") as f:
                json.dump(DEFAULT_CONFIG, f, indent=2)
        return GLOBAL_CONFIG_FILE


class Redactor:
    SECRET_PATTERNS = [
        (re.compile(r'(?i)(bearer\s+)[a-zA-Z0-9_\-\.]{12,}'), r'\1[REDACTED]'),
        (re.compile(r'(?i)(token\s*[:=]\s*)[a-zA-Z0-9_\-\.]{12,}'), r'\1[REDACTED]'),
        (re.compile(r'(?i)(api[_-]?key\s*[:=]\s*)[a-zA-Z0-9_\-\.]{12,}'), r'\1[REDACTED]'),
        (re.compile(r'(?i)(secret\s*[:=]\s*)[a-zA-Z0-9_\-\.]{12,}'), r'\1[REDACTED]'),
        (re.compile(r'(?i)(password\s*[:=]\s*)[^\s,;&]+'), r'\1[REDACTED]'),
        (re.compile(r'ghp_[a-zA-Z0-9]{20,}'), 'ghp_[REDACTED]'),
        (re.compile(r'github_pat_[a-zA-Z0-9_]{30,}'), 'github_pat_[REDACTED]'),
        (re.compile(r'sk-[a-zA-Z0-9_\-]{20,}'), 'sk-[REDACTED]'),
        (re.compile(r'AKIA[0-9A-Z]{16}'), 'AKIA[REDACTED]'),
        (re.compile(r'xox[baprs]-[0-9a-zA-Z]{10,}'), 'xox-[REDACTED]'),
    ]

    @classmethod
    def sanitize_text(cls, text: Optional[str]) -> str:
        if not text:
            return ""

        s = str(text)

        # 1. Redact user home directory
        home = os.path.expanduser("~")
        if home and len(home) > 2:
            s = s.replace(home, "~")
            # Windows alternative slash format
            home_alt = home.replace("\\", "/")
            s = s.replace(home_alt, "~")

        # 2. Redact typical usernames in Windows / Linux paths
        user_env = os.environ.get("USERNAME") or os.environ.get("USER")
        if user_env and len(user_env) > 3 and user_env.lower() not in ("root", "admin", "administrator"):
            s = re.sub(r'(?i)[\\/](users|home)[\\/]' + re.escape(user_env), r'/\1/~user', s)

        # 3. Redact secret token patterns
        for pattern, replacement in cls.SECRET_PATTERNS:
            s = pattern.sub(replacement, s)

        return s


class DiagnosticsStore:
    @staticmethod
    def ensure_dirs() -> None:
        os.makedirs(EVENTS_DIR, exist_ok=True)
        os.makedirs(EXPORT_DIR, exist_ok=True)

    @classmethod
    def record_incident(
        cls,
        component: str,
        error_message: str,
        event_type: str = "script_crash",
        stack_trace: Optional[str] = None,
        command: Optional[str] = None,
        repo_root: Optional[str] = None,
        note: Optional[str] = None,
        extra_metadata: Optional[Dict[str, Any]] = None,
    ) -> Optional[Dict[str, Any]]:
        config = ConfigManager.load_config(repo_root)
        if not config.get("telemetry_enabled", True):
            return None

        cls.ensure_dirs()

        now = datetime.now(timezone.utc)
        ts_str = now.strftime("%Y-%m-%dT%H-%M-%SZ")
        short_id = uuid.uuid4().hex[:8]
        incident_id = f"{ts_str}--{short_id}"

        # Sanitize all strings
        clean_comp = Redactor.sanitize_text(component)
        clean_err = Redactor.sanitize_text(error_message)
        clean_trace = Redactor.sanitize_text(stack_trace) if stack_trace else ""
        clean_cmd = Redactor.sanitize_text(command) if command else ""
        clean_note = Redactor.sanitize_text(note) if note else ""

        repo_name = os.path.basename(repo_root) if repo_root else "unknown"
        has_along = bool(repo_root and (os.path.exists(os.path.join(repo_root, ".along")) or os.path.exists(os.path.join(repo_root, "AGENTS.md"))))

        payload: Dict[str, Any] = {
            "id": incident_id,
            "timestamp": now.isoformat(),
            "status": "unresolved",
            "along_version": CURRENT_VERSION,
            "component": clean_comp,
            "event_type": event_type,
            "platform": platform.system().lower(),
            "os_release": platform.release(),
            "python_version": platform.python_version(),
            "command": clean_cmd,
            "error_message": clean_err,
            "stack_trace": clean_trace,
            "repo_name": repo_name,
            "has_along": has_along,
            "note": clean_note,
            "metadata": extra_metadata or {}
        }

        event_path = os.path.join(EVENTS_DIR, f"{incident_id}.json")
        with open(event_path, "w", encoding="utf-8", newline="\n") as f:
            json.dump(payload, f, indent=2, ensure_ascii=False)

        cls.update_report()
        return payload

    @classmethod
    def list_incidents(cls, all_status: bool = False) -> List[Dict[str, Any]]:
        cls.ensure_dirs()
        incidents = []
        for p in sorted(Path(EVENTS_DIR).glob("*.json"), reverse=True):
            try:
                with open(p, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    if isinstance(data, dict):
                        if all_status or data.get("status") == "unresolved":
                            incidents.append(data)
            except (OSError, json.JSONDecodeError, ValueError) as exc:
                print(f"[Warning] Corrupt incident file '{p}': {exc}", file=sys.stderr)
                continue
        return incidents

    @classmethod
    def get_incident(cls, incident_id: str) -> Optional[Dict[str, Any]]:
        cls.ensure_dirs()
        for p in Path(EVENTS_DIR).glob(f"*{incident_id}*.json"):
            try:
                with open(p, "r", encoding="utf-8") as f:
                    loaded = json.load(f)
                    if isinstance(loaded, dict):
                        return loaded
            except (OSError, json.JSONDecodeError, ValueError) as exc:
                print(f"[Warning] Failed to read incident '{p}': {exc}", file=sys.stderr)
                return None
        return None

    @classmethod
    def mark_resolved(cls, incident_id: str) -> bool:
        cls.ensure_dirs()
        for p in Path(EVENTS_DIR).glob(f"*{incident_id}*.json"):
            try:
                with open(p, "r", encoding="utf-8") as f:
                    data = json.load(f)
                if isinstance(data, dict):
                    data["status"] = "resolved"
                    data["resolved_at"] = datetime.now(timezone.utc).isoformat()
                    with open(p, "w", encoding="utf-8", newline="\n") as f:
                        json.dump(data, f, indent=2, ensure_ascii=False)
                    cls.update_report()
                    return True
            except (OSError, json.JSONDecodeError, ValueError) as exc:
                print(f"[Warning] Failed to update incident '{p}': {exc}", file=sys.stderr)
                return False
        return False

    @classmethod
    def clear_incidents(cls, all_status: bool = False) -> int:
        cls.ensure_dirs()
        count = 0
        for p in Path(EVENTS_DIR).glob("*.json"):
            try:
                if not all_status:
                    with open(p, "r", encoding="utf-8") as f:
                        data = json.load(f)
                    if isinstance(data, dict) and data.get("status") != "unresolved":
                        continue
                os.remove(p)
                count += 1
            except (OSError, json.JSONDecodeError, ValueError) as exc:
                print(f"[Warning] Failed to remove incident '{p}': {exc}", file=sys.stderr)
                continue
        cls.update_report()
        return count

    @classmethod
    def generate_markdown_report(cls, unresolved_only: bool = True) -> str:
        incidents = cls.list_incidents(all_status=not unresolved_only)
        lines = [
            "# Along Diagnostics & Telemetry Report",
            "",
            f"- **Generated**: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}",
            f"- **Along Version**: v{CURRENT_VERSION}",
            f"- **Total Incidents**: {len(incidents)}",
            "",
            "## Incident Log",
            ""
        ]

        if not incidents:
            lines.append("No active or unresolved diagnostic incidents recorded.")
            lines.append("")
            return "\n".join(lines)

        for inc in incidents:
            lines.append(f"### Incident `{inc.get('id')}`")
            lines.append(f"- **Timestamp**: {inc.get('timestamp')}")
            lines.append(f"- **Component**: `{inc.get('component')}`")
            lines.append(f"- **Type**: `{inc.get('event_type')}` | **Status**: `{inc.get('status')}`")
            lines.append(f"- **Platform**: `{inc.get('platform')}` ({inc.get('os_release')}) | Python `{inc.get('python_version')}`")
            lines.append(f"- **Repository**: `{inc.get('repo_name')}` (has_along: `{inc.get('has_along')}`)")
            if inc.get("command"):
                lines.append(f"- **Command**: `{inc.get('command')}`")
            if inc.get("note"):
                lines.append(f"- **User Note**: {inc.get('note')}")
            lines.append("")
            lines.append("**Error Message**:")
            lines.append("```text")
            lines.append(inc.get("error_message", "").strip())
            lines.append("```")
            if inc.get("stack_trace"):
                lines.append("")
                lines.append("**Stack Trace**:")
                lines.append("```text")
                lines.append(inc.get("stack_trace", "").strip())
                lines.append("```")
            lines.append("")
            lines.append("---")
            lines.append("")

        return "\n".join(lines)

    @classmethod
    def update_report(cls) -> None:
        try:
            cls.ensure_dirs()
            report_md = cls.generate_markdown_report(unresolved_only=True)
            with open(REPORT_FILE, "w", encoding="utf-8", newline="\n") as f:
                f.write(report_md)
        except OSError as exc:
            print(f"[Warning] Could not update diagnostic report '{REPORT_FILE}': {exc}", file=sys.stderr)


def record_incident(
    component: str,
    error_message: str,
    event_type: str = "script_crash",
    stack_trace: Optional[str] = None,
    command: Optional[str] = None,
    repo_root: Optional[str] = None,
    note: Optional[str] = None,
    extra_metadata: Optional[Dict[str, Any]] = None,
) -> Optional[Dict[str, Any]]:
    """Record a structured incident into ~/.along/diagnostics/."""
    return DiagnosticsStore.record_incident(
        component=component,
        error_message=error_message,
        event_type=event_type,
        stack_trace=stack_trace,
        command=command,
        repo_root=repo_root,
        note=note,
        extra_metadata=extra_metadata,
    )


def try_record_incident(
    component: str,
    error_message: str,
    event_type: str = "script_crash",
    stack_trace: Optional[str] = None,
    command: Optional[str] = None,
    repo_root: Optional[str] = None,
    note: Optional[str] = None,
    extra_metadata: Optional[Dict[str, Any]] = None,
) -> Optional[Dict[str, Any]]:
    """Safely traps and records internal Along exceptions into ~/.along/diagnostics/ without crashing."""
    try:
        return record_incident(
            component=component,
            error_message=error_message,
            event_type=event_type,
            stack_trace=stack_trace,
            command=command,
            repo_root=repo_root,
            note=note,
            extra_metadata=extra_metadata,
        )
    except (OSError, ValueError, TypeError) as exc:
        print(f"[Warning] Failed to record diagnostic incident for {component}: {exc}", file=sys.stderr)
        return None
