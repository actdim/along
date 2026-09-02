#!/usr/bin/env python3
"""
along_feedback.py - Global Diagnostics, Telemetry, and Feedback Engine for Along Protocol.

Captures system errors, tool crashes, and protocol anomalies into ~/.along/diagnostics/
with automated secret & path redaction, and dispatches feedback bundles via
Telegram Bot, Webhook/API, or Local File export.

Usage:
    python scripts/along_feedback.py record --component <name> --error <msg> [--type <type>] [--trace <trace>]
    python scripts/along_feedback.py list [--all]
    python scripts/along_feedback.py show <incident_id>
    python scripts/along_feedback.py report [--output <path>]
    python scripts/along_feedback.py send [--channel telegram|webhook|file|all] [--note <text>] [--dry-run]
    python scripts/along_feedback.py clear [--all]
    python scripts/along_feedback.py config [init|show|path]
"""

import os
import sys
import re
import json
import uuid
import platform
import argparse
import urllib.request
import urllib.parse
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from alongkit import bootstrap
bootstrap.ensure_deps()


from alongkit import version

# Previously a literal that had drifted to 2.1.6 while the project shipped 2.2.8, so
# every submitted bug report carried a version that had not existed for three releases.
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
                    config = ConfigManager._deep_merge(config, loaded)
            except Exception:
                pass

        # 2. Repo-local config override if present
        if repo_root:
            local_cfg = os.path.join(repo_root, ".along", "config.json")
            if os.path.isfile(local_cfg):
                try:
                    with open(local_cfg, "r", encoding="utf-8") as f:
                        loaded = json.load(f)
                        config = ConfigManager._deep_merge(config, loaded)
                except Exception:
                    pass

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
            with open(GLOBAL_CONFIG_FILE, "w", encoding="utf-8") as f:
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
    def ensure_dirs():
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
        with open(event_path, "w", encoding="utf-8") as f:
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
                    if all_status or data.get("status") == "unresolved":
                        incidents.append(data)
            except Exception:
                continue
        return incidents

    @classmethod
    def get_incident(cls, incident_id: str) -> Optional[Dict[str, Any]]:
        cls.ensure_dirs()
        for p in Path(EVENTS_DIR).glob(f"*{incident_id}*.json"):
            try:
                with open(p, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                return None
        return None

    @classmethod
    def mark_resolved(cls, incident_id: str) -> bool:
        cls.ensure_dirs()
        for p in Path(EVENTS_DIR).glob(f"*{incident_id}*.json"):
            try:
                with open(p, "r", encoding="utf-8") as f:
                    data = json.load(f)
                data["status"] = "resolved"
                data["resolved_at"] = datetime.now(timezone.utc).isoformat()
                with open(p, "w", encoding="utf-8") as f:
                    json.dump(data, f, indent=2, ensure_ascii=False)
                cls.update_report()
                return True
            except Exception:
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
                    if data.get("status") != "unresolved":
                        continue
                os.remove(p)
                count += 1
            except Exception:
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
    def update_report(cls):
        try:
            cls.ensure_dirs()
            report_md = cls.generate_markdown_report(unresolved_only=True)
            with open(REPORT_FILE, "w", encoding="utf-8") as f:
                f.write(report_md)
        except Exception:
            pass


class TelegramTransport:
    @staticmethod
    def send(report_text: str, incidents: List[Dict[str, Any]], config: Dict[str, Any]) -> Tuple[bool, str]:
        t_cfg = config.get("transports", {}).get("telegram", {})
        bot_token = t_cfg.get("bot_token", "").strip()
        chat_id = t_cfg.get("chat_id", "").strip()

        if not bot_token or not chat_id:
            return False, "Telegram credentials missing. Set bot_token and chat_id in ~/.along/config.json or environment variables (ALONG_TELEGRAM_BOT_TOKEN, ALONG_TELEGRAM_CHAT_ID)."

        api_url = f"https://api.telegram.org/bot{bot_token}/sendMessage"

        summary = (
            f"[Along Diagnostics Report]\n"
            f"Along Version: v{CURRENT_VERSION}\n"
            f"Incidents: {len(incidents)}\n"
            f"Time: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}\n\n"
        )
        for inc in incidents[:3]:
            summary += (
                f"- ID: {inc.get('id')}\n"
                f"  Component: {inc.get('component')}\n"
                f"  Error: {inc.get('error_message', '')[:120]}\n\n"
            )

        if len(summary) > 4000:
            summary = summary[:3900] + "\n...[truncated]"

        payload = {
            "chat_id": chat_id,
            "text": summary
        }
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(api_url, data=data, headers={"Content-Type": "application/json"})

        try:
            with urllib.request.urlopen(req, timeout=10) as resp:
                if resp.status == 200:
                    return True, "Successfully dispatched diagnostic summary to Telegram channel."
                return False, f"Telegram API returned status {resp.status}."
        except Exception as e:
            return False, f"Failed to send Telegram message: {str(e)}"


class WebhookTransport:
    @staticmethod
    def send(report_text: str, incidents: List[Dict[str, Any]], config: Dict[str, Any]) -> Tuple[bool, str]:
        w_cfg = config.get("transports", {}).get("webhook", {})
        url = w_cfg.get("url", "").strip()
        headers = w_cfg.get("headers", {}) or {"Content-Type": "application/json"}

        if not url:
            return False, "Webhook URL missing. Configure transports.webhook.url in ~/.along/config.json or set ALONG_FEEDBACK_WEBHOOK_URL."

        payload = {
            "source": "along-feedback",
            "along_version": CURRENT_VERSION,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "incident_count": len(incidents),
            "incidents": incidents,
            "report_markdown": report_text
        }
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        req = urllib.request.Request(url, data=data, headers=headers)

        try:
            with urllib.request.urlopen(req, timeout=10) as resp:
                if resp.status in (200, 201, 202, 204):
                    return True, f"Successfully posted diagnostics bundle to Webhook endpoint ({url})."
                return False, f"Webhook endpoint returned status {resp.status}."
        except Exception as e:
            return False, f"Failed to post to Webhook: {str(e)}"


class FileTransport:
    @staticmethod
    def send(report_text: str, incidents: List[Dict[str, Any]], config: Dict[str, Any], custom_path: Optional[str] = None) -> Tuple[bool, str]:
        DiagnosticsStore.ensure_dirs()
        out_dir = custom_path or EXPORT_DIR
        out_dir = os.path.expanduser(out_dir)
        os.makedirs(out_dir, exist_ok=True)

        now_str = datetime.now(timezone.utc).strftime("%Y%m%d--%H%M%S")
        bundle_file = os.path.join(out_dir, f"feedback-bundle--{now_str}.md")
        json_file = os.path.join(out_dir, f"feedback-bundle--{now_str}.json")

        try:
            with open(bundle_file, "w", encoding="utf-8") as f:
                f.write(report_text)
            with open(json_file, "w", encoding="utf-8") as f:
                json.dump({"version": CURRENT_VERSION, "incidents": incidents}, f, indent=2, ensure_ascii=False)
            return True, f"Exported diagnostics bundle to:\n  - Markdown: {bundle_file}\n  - JSON: {json_file}"
        except Exception as e:
            return False, f"Failed to export diagnostics file: {str(e)}"


def dispatch_feedback(
    channel: str = "all",
    incident_id: Optional[str] = None,
    note: Optional[str] = None,
    dry_run: bool = False,
    repo_root: Optional[str] = None
) -> List[Tuple[str, bool, str]]:
    config = ConfigManager.load_config(repo_root)

    if incident_id:
        inc = DiagnosticsStore.get_incident(incident_id)
        incidents = [inc] if inc else []
    else:
        incidents = DiagnosticsStore.list_incidents(all_status=False)

    if not incidents:
        return [("all", True, "No unresolved diagnostic incidents to dispatch.")]

    if note:
        for inc in incidents:
            if not inc.get("note"):
                inc["note"] = Redactor.sanitize_text(note)

    report_text = DiagnosticsStore.generate_markdown_report(unresolved_only=bool(not incident_id))

    if dry_run:
        return [("dry-run", True, f"Simulated dispatch of {len(incidents)} incident(s) via channel '{channel}'.\nPayload length: {len(report_text)} chars.")]

    results = []

    target_channels = []
    if channel == "all":
        target_channels = ["file"]
        if config.get("transports", {}).get("telegram", {}).get("enabled"):
            target_channels.append("telegram")
        if config.get("transports", {}).get("webhook", {}).get("enabled"):
            target_channels.append("webhook")
    else:
        target_channels = [channel]

    for ch in target_channels:
        if ch == "file":
            ok, msg = FileTransport.send(report_text, incidents, config)
            results.append(("file", ok, msg))
        elif ch == "telegram":
            ok, msg = TelegramTransport.send(report_text, incidents, config)
            results.append(("telegram", ok, msg))
        elif ch == "webhook":
            ok, msg = WebhookTransport.send(report_text, incidents, config)
            results.append(("webhook", ok, msg))
        else:
            results.append((ch, False, f"Unknown transport channel '{ch}'."))

    # If at least one successful dispatch, mark incidents resolved
    if any(ok for _, ok, _ in results):
        for inc in incidents:
            DiagnosticsStore.mark_resolved(inc["id"])

    return results


def main():
    parser = argparse.ArgumentParser(description="Along Self-Diagnostics & Feedback Engine")
    subparsers = parser.add_subparsers(dest="action", help="Action to execute")

    # record
    p_rec = subparsers.add_parser("record", help="Record a system diagnostic incident")
    p_rec.add_argument("--component", required=True, help="Failing component or script name")
    p_rec.add_argument("--error", required=True, help="Error message")
    p_rec.add_argument("--type", default="script_crash", help="Event type (script_crash, protocol_anomaly, command_error)")
    p_rec.add_argument("--trace", default="", help="Optional stack trace")
    p_rec.add_argument("--command", default="", help="Executed command line")
    p_rec.add_argument("--repo", default=os.getcwd(), help="Repository root path")
    p_rec.add_argument("--note", default="", help="Optional context note")

    # list
    p_list = subparsers.add_parser("list", help="List recorded diagnostic incidents")
    p_list.add_argument("--all", action="store_true", help="Include resolved incidents")

    # show
    p_show = subparsers.add_parser("show", help="Show details of an incident")
    p_show.add_argument("id", help="Incident ID or substring")

    # report
    p_rep = subparsers.add_parser("report", help="Print or output compiled diagnostics report")
    p_rep.add_argument("--output", "-o", help="Optional output file path")
    p_rep.add_argument("--all", action="store_true", help="Include resolved incidents")

    # send
    p_send = subparsers.add_parser("send", help="Send diagnostics feedback")
    p_send.add_argument("--channel", choices=["all", "telegram", "webhook", "file"], default="all", help="Target transport channel")
    p_send.add_argument("--id", help="Specific incident ID to send")
    p_send.add_argument("--note", help="Additional user note to attach to report")
    p_send.add_argument("--dry-run", action="store_true", help="Simulate without network/disk dispatch")

    # clear
    p_clr = subparsers.add_parser("clear", help="Clear diagnostic incident logs")
    p_clr.add_argument("--all", action="store_true", help="Clear all including resolved")

    # config
    p_cfg = subparsers.add_parser("config", help="Manage Along global configuration")
    p_cfg.add_argument("subaction", choices=["init", "show", "path"], nargs="?", default="show")

    args = parser.parse_args()

    if not args.action or args.action == "list":
        incidents = DiagnosticsStore.list_incidents(all_status=getattr(args, "all", False))
        if not incidents:
            print("[Along Diagnostics] No active unresolved incidents found in ~/.along/diagnostics/events/")
            sys.exit(0)
        print(f"-> Along Diagnostic Incidents ({len(incidents)} unresolved):")
        print(f"{'ID':<30} {'TIMESTAMP':<20} {'COMPONENT':<25} {'ERROR'}")
        print("-" * 100)
        for inc in incidents:
            err = inc.get("error_message", "").replace("\n", " ")[:40]
            print(f"{inc.get('id'):<30} {inc.get('timestamp')[:19]:<20} {inc.get('component')[:24]:<25} {err}")
        sys.exit(0)

    if args.action == "record":
        payload = DiagnosticsStore.record_incident(
            component=args.component,
            error_message=args.error,
            event_type=args.type,
            stack_trace=args.trace,
            command=args.command,
            repo_root=args.repo,
            note=args.note
        )
        if payload:
            print(f"-> Diagnostic incident recorded: {payload['id']}")
            print(f"   Log path: {os.path.join(EVENTS_DIR, payload['id'] + '.json')}")
            print(f"   Report:   {REPORT_FILE}")
        sys.exit(0)

    if args.action == "show":
        inc = DiagnosticsStore.get_incident(args.id)
        if not inc:
            print(f"[Error] Incident '{args.id}' not found.", file=sys.stderr)
            sys.exit(1)
        print(json.dumps(inc, indent=2, ensure_ascii=False))
        sys.exit(0)

    if args.action == "report":
        md = DiagnosticsStore.generate_markdown_report(unresolved_only=not args.all)
        if args.output:
            with open(args.output, "w", encoding="utf-8") as f:
                f.write(md)
            print(f"-> Report saved to: {args.output}")
        else:
            print(md)
        sys.exit(0)

    if args.action == "send":
        results = dispatch_feedback(
            channel=args.channel,
            incident_id=args.id,
            note=args.note,
            dry_run=args.dry_run
        )
        for ch, ok, msg in results:
            prefix = "[Success]" if ok else "[Failed]"
            print(f"{prefix} ({ch}): {msg}")
        sys.exit(0 if any(ok for _, ok, _ in results) else 1)

    if args.action == "clear":
        count = DiagnosticsStore.clear_incidents(all_status=args.all)
        print(f"-> Cleared {count} diagnostic event(s).")
        sys.exit(0)

    if args.action == "config":
        if args.subaction == "init":
            path = ConfigManager.init_global_config(force=True)
            print(f"-> Initialized global configuration: {path}")
        elif args.subaction == "path":
            print(GLOBAL_CONFIG_FILE)
        else:
            cfg = ConfigManager.load_config()
            print(json.dumps(cfg, indent=2, ensure_ascii=False))
        sys.exit(0)


if __name__ == "__main__":
    main()

