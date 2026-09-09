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

from alongkit import diagnostics

GLOBAL_ALONG_DIR = diagnostics.GLOBAL_ALONG_DIR
DIAGNOSTICS_DIR = diagnostics.DIAGNOSTICS_DIR
EVENTS_DIR = diagnostics.EVENTS_DIR
EXPORT_DIR = diagnostics.EXPORT_DIR
REPORT_FILE = diagnostics.REPORT_FILE
GLOBAL_CONFIG_FILE = diagnostics.GLOBAL_CONFIG_FILE
DEFAULT_CONFIG = diagnostics.DEFAULT_CONFIG
ConfigManager = diagnostics.ConfigManager
Redactor = diagnostics.Redactor
DiagnosticsStore = diagnostics.DiagnosticsStore


class _FeedbackModule(sys.modules[__name__].__class__):
    """Synchronizes diagnostic path overrides from callers/tests into alongkit.diagnostics."""
    def __setattr__(self, name, value):
        super().__setattr__(name, value)
        if hasattr(diagnostics, name):
            setattr(diagnostics, name, value)

sys.modules[__name__].__class__ = _FeedbackModule


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
        except (urllib.error.URLError, OSError, TimeoutError) as e:
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
        except (urllib.error.URLError, OSError, TimeoutError) as e:
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
            with open(bundle_file, "w", encoding="utf-8", newline="\n") as f:
                f.write(report_text)
            with open(json_file, "w", encoding="utf-8", newline="\n") as f:
                json.dump({"version": CURRENT_VERSION, "incidents": incidents}, f, indent=2, ensure_ascii=False)
            return True, f"Exported diagnostics bundle to:\n  - Markdown: {bundle_file}\n  - JSON: {json_file}"
        except OSError as e:
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
            with open(args.output, "w", encoding="utf-8", newline="\n") as f:
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

