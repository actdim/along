#!/usr/bin/env python3
"""alongkit.webdev.mcp_server - Dedicated stdio Model Context Protocol (MCP) server for Along WebDev (REQ-13)."""

from __future__ import annotations

import base64
import json
import os
import sys
from typing import Any, Dict, List, Optional, Tuple

from .. import repo
from . import checklist, daemon, runner, services


SERVER_NAME = "along-webdev"
SERVER_VERSION = "1.0.0"
PROTOCOL_VERSION = "2024-11-05"


TOOLS_MANIFEST: List[Dict[str, Any]] = [
    {
        "name": "serve_up",
        "description": "Bring up declared application development services (REQ-1).",
        "inputSchema": {
            "type": "object",
            "properties": {
                "services": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Optional list of service names. Defaults to all declared services.",
                }
            },
        },
    },
    {
        "name": "serve_status",
        "description": "Inspect status and health of application services (REQ-1).",
        "inputSchema": {"type": "object", "properties": {}},
    },
    {
        "name": "serve_down",
        "description": "Stop running application development services (REQ-1).",
        "inputSchema": {
            "type": "object",
            "properties": {
                "services": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Optional list of service names to stop.",
                }
            },
        },
    },
    {
        "name": "session_start",
        "description": "Start an interactive browser session daemon (REQ-10).",
        "inputSchema": {
            "type": "object",
            "properties": {
                "issue": {"type": "string", "description": "Issue key attribution."},
                "headed": {"type": "boolean", "description": "Launch browser in headed visible mode."},
            },
        },
    },
    {
        "name": "session_step",
        "description": "Execute a single exploratory step in the active interactive browser session (REQ-10).",
        "inputSchema": {
            "type": "object",
            "properties": {
                "step": {"type": "object", "description": "Declarative step dictionary."}
            },
            "required": ["step"],
        },
    },
    {
        "name": "session_batch",
        "description": "Execute a batch of exploratory steps in the active browser session (REQ-10).",
        "inputSchema": {
            "type": "object",
            "properties": {
                "steps": {
                    "type": "array",
                    "items": {"type": "object"},
                    "description": "List of declarative step dictionaries.",
                }
            },
            "required": ["steps"],
        },
    },
    {
        "name": "session_save",
        "description": "Save active session transcript to a declarative scenario YAML file (REQ-10).",
        "inputSchema": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Output scenario file path."},
                "issue": {"type": "string", "description": "Issue slug to attribute."},
                "title": {"type": "string", "description": "Scenario title."},
            },
            "required": ["path"],
        },
    },
    {
        "name": "session_status",
        "description": "Check status of the active interactive browser session (REQ-10).",
        "inputSchema": {"type": "object", "properties": {}},
    },
    {
        "name": "session_stop",
        "description": "Stop the active interactive browser session (REQ-10).",
        "inputSchema": {"type": "object", "properties": {}},
    },
    {
        "name": "run",
        "description": "Execute a declarative YAML/JSON browser verification scenario (REQ-9).",
        "inputSchema": {
            "type": "object",
            "properties": {
                "scenario": {"type": "string", "description": "Path to scenario file or scenario content."},
                "issue": {"type": "string", "description": "Issue slug attribution."},
                "check": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Filter to specific check IDs.",
                },
                "file_failures": {"type": "boolean", "description": "Auto-file bug issues for failed checks."},
            },
            "required": ["scenario"],
        },
    },
    {
        "name": "checklist_compile",
        "description": "Compile natural-language Markdown checklist into scenario skeleton (REQ-10).",
        "inputSchema": {
            "type": "object",
            "properties": {
                "target": {"type": "string", "description": "Markdown checklist file path or issue key."},
                "out": {"type": "string", "description": "Output scenario YAML path."},
            },
            "required": ["target"],
        },
    },
    {
        "name": "screenshot",
        "description": "Capture visual proof screenshot of a web route (REQ-8).",
        "inputSchema": {
            "type": "object",
            "properties": {
                "url": {"type": "string", "description": "URL to capture."},
                "out": {"type": "string", "description": "Output screenshot file path."},
                "viewport": {"type": "string", "description": "Viewport preset or WxH dimension."},
                "theme": {"type": "string", "enum": ["light", "dark"], "description": "Color scheme."},
                "issue": {"type": "string", "description": "Issue slug attribution."},
            },
            "required": ["url", "out"],
        },
    },
    {
        "name": "eval",
        "description": "Evaluate JavaScript expression in active browser session (REQ-5).",
        "inputSchema": {
            "type": "object",
            "properties": {
                "expression": {"type": "string", "description": "JavaScript expression to evaluate."}
            },
            "required": ["expression"],
        },
    },
]


def dispatch_tool_call(repo_root: str, tool_name: str, arguments: Dict[str, Any]) -> Tuple[Dict[str, Any], bool, Optional[str]]:
    """Execute requested tool and return result payload, is_error flag, and optional image path."""
    try:
        if tool_name == "serve_up":
            res = services.serve_up(repo_root, service_names=arguments.get("services"))
            return {"status": "ok", "services": res}, False, None

        elif tool_name == "serve_status":
            res = services.serve_status(repo_root)
            return {"status": "ok", "services": res}, False, None

        elif tool_name == "serve_down":
            res = services.serve_down(repo_root, service_names=arguments.get("services"))
            return {"status": "ok", "services": res}, False, None

        elif tool_name == "session_start":
            res = daemon.session_start(
                repo_root,
                issue_key=arguments.get("issue") or "scratch",
                headed=bool(arguments.get("headed", False)),
            )
            return res, False, None

        elif tool_name == "session_step":
            res = daemon.session_step(repo_root, arguments["step"])
            return res, not res.get("ok", False), None

        elif tool_name == "session_batch":
            res = daemon.session_batch(repo_root, arguments["steps"])
            return res, not res.get("ok", False), None

        elif tool_name == "session_save":
            res = daemon.session_save(
                repo_root,
                output_path=arguments["path"],
                issue=arguments.get("issue"),
                title=arguments.get("title"),
            )
            return res, not res.get("ok", False), None

        elif tool_name == "session_status":
            res = daemon.session_status(repo_root)
            return res, False, None

        elif tool_name == "session_stop":
            res = daemon.session_stop(repo_root)
            return res, False, None

        elif tool_name == "run":
            code, rep = runner.run_scenario(
                repo_root,
                scenario_spec=arguments["scenario"],
                issue_key=arguments.get("issue"),
                check_filter=arguments.get("check"),
                file_failures=bool(arguments.get("file_failures", False)),
            )
            return rep, code != 0, None

        elif tool_name == "checklist_compile":
            scen = checklist.compile_checklist(
                repo_root,
                target=arguments["target"],
                output_path=arguments.get("out"),
            )
            return scen, False, None

        elif tool_name == "screenshot":
            out_path = runner.quick_screenshot(
                repo_root,
                url=arguments["url"],
                out_path=arguments["out"],
                viewport=arguments.get("viewport", "desktop-1440x900"),
                theme=arguments.get("theme", "light"),
                issue_key=arguments.get("issue"),
            )
            return {"status": "ok", "path": out_path}, False, out_path

        elif tool_name == "eval":
            res = daemon.session_step(repo_root, {"eval": arguments["expression"]})
            return res, not res.get("ok", False), None

        else:
            return {"error": f"Unknown tool: '{tool_name}'"}, True, None

    except (RuntimeError, AssertionError, ValueError, KeyError, TypeError, OSError, TimeoutError) as exc:
        return {"error": str(exc)}, True, None


def handle_jsonrpc_request(repo_root: str, request: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Process single JSON-RPC 2.0 request or notification."""
    req_id = request.get("id")
    method = request.get("method")
    params = request.get("params") or {}

    if method == "initialize":
        return {
            "jsonrpc": "2.0",
            "id": req_id,
            "result": {
                "protocolVersion": PROTOCOL_VERSION,
                "serverInfo": {
                    "name": SERVER_NAME,
                    "version": SERVER_VERSION,
                },
                "capabilities": {
                    "tools": {},
                },
            },
        }

    elif method == "notifications/initialized":
        # Client initialized notification; no response required
        return None

    elif method == "ping":
        return {"jsonrpc": "2.0", "id": req_id, "result": {}}

    elif method == "tools/list":
        return {
            "jsonrpc": "2.0",
            "id": req_id,
            "result": {
                "tools": TOOLS_MANIFEST,
            },
        }

    elif method == "tools/call":
        tool_name = params.get("name", "")
        arguments = params.get("arguments") or {}

        result_data, is_error, img_path = dispatch_tool_call(repo_root, tool_name, arguments)
        content_items: List[Dict[str, Any]] = [
            {"type": "text", "text": json.dumps(result_data, indent=2)}
        ]

        if img_path and os.path.isfile(img_path):
            try:
                with open(img_path, "rb") as f:
                    b64_data = base64.b64encode(f.read()).decode("ascii")
                content_items.append({
                    "type": "image",
                    "data": b64_data,
                    "mimeType": "image/png",
                })
            except OSError:
                pass

        resp_payload: Dict[str, Any] = {
            "content": content_items,
        }
        if is_error:
            resp_payload["isError"] = True

        return {
            "jsonrpc": "2.0",
            "id": req_id,
            "result": resp_payload,
        }

    else:
        if req_id is not None:
            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "error": {
                    "code": -32601,
                    "message": f"Method not found: {method}",
                },
            }
        return None


def run_stdio_server(repo_root: Optional[str] = None) -> int:
    """Run JSON-RPC stdio loop."""
    resolved_root = repo_root or repo.find_repo_root()

    for line in sys.stdin:
        line_clean = line.strip()
        if not line_clean:
            continue
        try:
            req_obj = json.loads(line_clean)
        except ValueError as err:
            err_resp = {
                "jsonrpc": "2.0",
                "id": None,
                "error": {"code": -32700, "message": f"Parse error: {err}"},
            }
            sys.stdout.write(json.dumps(err_resp) + "\n")
            sys.stdout.flush()
            continue

        if isinstance(req_obj, dict):
            resp_obj = handle_jsonrpc_request(resolved_root, req_obj)
            if resp_obj is not None:
                sys.stdout.write(json.dumps(resp_obj) + "\n")
                sys.stdout.flush()

    return 0
