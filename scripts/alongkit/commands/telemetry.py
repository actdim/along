#!/usr/bin/env python3
"""
alongkit.commands.telemetry - Telemetry spool status, endpoint verification, and WAL flushing.
[debt--split-along-exec-and-entities]
"""

from __future__ import annotations
if __name__ == "__main__":
    import os
    raise SystemExit(
        f"{os.path.basename(__file__)} is a library module, not a command.\n"
        "Run: python .along/scripts/test.py"
    )

import json
import os
import sys
from typing import Any, Dict, List, Optional, Tuple

from .. import repo


def _get_active_telemetry_endpoint(explicit_endpoint: Optional[str] = None) -> str:
    if explicit_endpoint:
        return explicit_endpoint
    env_traces = os.environ.get("OTEL_EXPORTER_OTLP_TRACES_ENDPOINT")
    if env_traces:
        return env_traces
    along_ep = os.environ.get("ALONG_TELEMETRY_ENDPOINT")
    if along_ep:
        return along_ep
    env_otlp = os.environ.get("OTEL_EXPORTER_OTLP_ENDPOINT")
    if env_otlp:
        return f"{env_otlp.rstrip('/')}/v1/traces"
    return "http://localhost:4318/v1/traces"


def _test_endpoint_connectivity(endpoint: str, timeout: float = 1.5) -> Tuple[bool, str]:
    import urllib.error
    import urllib.request
    from alongkit.telemetry.otlp import build_otlp_payload

    payload = build_otlp_payload(service_name="actdim-along", resource_attrs={}, spans=[])
    data = json.dumps(payload, ensure_ascii=True).encode("utf-8")
    req = urllib.request.Request(
        url=endpoint,
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            status = getattr(resp, "status", 200)
            return True, f"HTTP {status}"
    except urllib.error.HTTPError as exc:
        return True, f"HTTP {exc.code}"
    except (urllib.error.URLError, TimeoutError, OSError, ValueError) as exc:
        reason = getattr(exc, "reason", str(exc))
        return False, str(reason)


def _telemetry_status(repo_root: str, args: List[str]):
    as_json = "--json" in args
    explicit_endpoint = None
    idx = 0
    while idx < len(args):
        if args[idx] in ("--endpoint", "-e") and idx + 1 < len(args):
            explicit_endpoint = args[idx + 1]
            idx += 2
        else:
            idx += 1

    endpoint = _get_active_telemetry_endpoint(explicit_endpoint)
    spool_dir = os.path.join(repo_root, ".along", "telemetry", "spool")

    wal_files: List[Tuple[str, int]] = []
    total_bytes = 0
    if os.path.isdir(spool_dir):
        try:
            for entry in sorted(os.scandir(spool_dir), key=lambda e: e.name):
                if entry.is_file() and entry.name.endswith(".wal"):
                    size = entry.stat().st_size
                    wal_files.append((entry.name, size))
                    total_bytes += size
        except OSError:
            pass

    connected, conn_detail = _test_endpoint_connectivity(endpoint, timeout=1.5)

    if as_json:
        result = {
            "wal_count": len(wal_files),
            "total_bytes": total_bytes,
            "endpoint": endpoint,
            "connected": connected,
            "endpoint_status": conn_detail,
            "spool_dir": spool_dir,
            "wal_files": [{"name": name, "size_bytes": sz} for name, sz in wal_files],
        }
        print(json.dumps(result, indent=2))
    else:
        conn_str = f"connected ({conn_detail})" if connected else f"unreachable ({conn_detail})"
        print("Along Telemetry Status:")
        print(f"  Endpoint:      {endpoint} [{conn_str}]")
        print(f"  Spool Dir:     {spool_dir}")
        print(f"  Pending WALs:  {len(wal_files)} file(s)")
        print(f"  Spooled Size:  {total_bytes} bytes")
        if wal_files:
            print("  WAL Files:")
            for name, sz in wal_files:
                print(f"    - {name} ({sz} bytes)")
    sys.exit(0)


def _telemetry_flush(repo_root: str, args: List[str]):
    explicit_endpoint = None
    idx = 0
    while idx < len(args):
        if args[idx] in ("--endpoint", "-e") and idx + 1 < len(args):
            explicit_endpoint = args[idx + 1]
            idx += 2
        else:
            idx += 1

    endpoint = _get_active_telemetry_endpoint(explicit_endpoint)
    spool_dir = os.path.join(repo_root, ".along", "telemetry", "spool")

    wal_paths: List[str] = []
    if os.path.isdir(spool_dir):
        try:
            for entry in sorted(os.scandir(spool_dir), key=lambda e: e.name):
                if entry.is_file() and entry.name.endswith(".wal"):
                    wal_paths.append(entry.path)
        except OSError:
            pass

    if not wal_paths:
        print("No pending telemetry spans in spool.")
        sys.exit(0)

    from alongkit.telemetry.otlp import OTLPExporter

    all_spans: List[Dict[str, Any]] = []
    valid_wal_paths: List[str] = []
    for p in wal_paths:
        try:
            with open(p, "r", encoding="utf-8") as f:
                file_has_spans = False
                for line in f:
                    line = line.strip()
                    if line:
                        try:
                            span_dict = json.loads(line)
                            all_spans.append(span_dict)
                            file_has_spans = True
                        except json.JSONDecodeError:
                            pass
                if file_has_spans:
                    valid_wal_paths.append(p)
                else:
                    try:
                        os.remove(p)
                    except OSError:
                        pass
        except OSError:
            pass

    if not all_spans:
        print("No pending telemetry spans in spool.")
        sys.exit(0)

    exporter = OTLPExporter(endpoint=endpoint, timeout=5.0)
    success = exporter.export(all_spans, spool_on_failure=False)
    if success:
        for p in valid_wal_paths:
            try:
                os.remove(p)
            except OSError:
                pass
        print(f"Successfully flushed {len(all_spans)} telemetry span(s) to {endpoint}.")
        sys.exit(0)
    else:
        print(
            f"[Error] Failed to flush {len(all_spans)} telemetry span(s) to {endpoint}: network or endpoint failure.",
            file=sys.stderr,
        )
        sys.exit(1)


def handle_telemetry_command(repo_root: Optional[str], args: List[str]):
    effective_root = repo_root or repo.find_repo_root() or os.getcwd()
    sub = args[0].lower() if args else "status"

    if sub in ("-h", "--help", "help"):
        print("Usage: along telemetry [status|flush] [options]")
        print("")
        print("Commands:")
        print("  status [--json] [--endpoint <url>]  Report pending WAL spool files and endpoint connectivity")
        print("  flush  [--endpoint <url>]           Export pending spans from WAL spool to OTLP endpoint")
        sys.exit(0)

    if sub == "status":
        _telemetry_status(effective_root, args[1:])
    elif sub == "flush":
        _telemetry_flush(effective_root, args[1:])
    else:
        print(f"[Error] Unknown telemetry subcommand: '{sub}'. Run 'along telemetry --help'.", file=sys.stderr)
        sys.exit(1)
